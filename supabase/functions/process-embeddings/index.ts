// File: supabase/functions/process-embeddings/index.ts
// Edge Function to process the embedding queue
// Called by pg_cron or manually to generate embeddings via OpenAI

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

interface QueueItem {
    id: number;
    memory_id: string;
    content: string;
}

serve(async (req: Request) => {
    const corsHeaders = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
    };

    if (req.method === "OPTIONS") {
        return new Response("ok", { headers: corsHeaders });
    }

    try {
        const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
        const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
        const openaiKey = Deno.env.get("OPENAI_API_KEY")!;

        const supabase = createClient(supabaseUrl, supabaseKey);

        // 1. Get pending items from queue
        const { data: queueItems, error: fetchError } = await supabase
            .from("embedding_queue")
            .select("id, memory_id, content")
            .eq("status", "pending")
            .order("created_at", { ascending: true })
            .limit(10);

        if (fetchError) {
            throw new Error(`Queue fetch error: ${fetchError.message}`);
        }

        if (!queueItems || queueItems.length === 0) {
            return new Response(
                JSON.stringify({ message: "No pending items in queue" }),
                { headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
        }

        const results: { id: number; success: boolean; error?: string }[] = [];

        // 2. Process each item
        for (const item of queueItems as QueueItem[]) {
            // Mark as processing
            await supabase
                .from("embedding_queue")
                .update({ status: "processing" })
                .eq("id", item.id);

            try {
                // Generate embedding via OpenAI
                const embeddingResponse = await fetch("https://api.openai.com/v1/embeddings", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        Authorization: `Bearer ${openaiKey}`,
                    },
                    body: JSON.stringify({
                        model: "text-embedding-3-small",
                        input: item.content,
                    }),
                });

                const embeddingData = await embeddingResponse.json();
                const embedding = embeddingData.data?.[0]?.embedding;

                if (!embedding) {
                    throw new Error("Failed to generate embedding");
                }

                // Update the memory with the new embedding
                const { error: updateError } = await supabase
                    .from("memories")
                    .update({ vec: embedding })
                    .eq("id", item.memory_id);

                if (updateError) {
                    throw new Error(`Memory update error: ${updateError.message}`);
                }

                // Mark as completed
                await supabase
                    .from("embedding_queue")
                    .update({
                        status: "completed",
                        processed_at: new Date().toISOString()
                    })
                    .eq("id", item.id);

                results.push({ id: item.id, success: true });

            } catch (err) {
                // Mark as failed
                await supabase
                    .from("embedding_queue")
                    .update({
                        status: "failed",
                        error_message: String(err)
                    })
                    .eq("id", item.id);

                results.push({ id: item.id, success: false, error: String(err) });
            }
        }

        return new Response(
            JSON.stringify({
                processed: results.length,
                successful: results.filter(r => r.success).length,
                failed: results.filter(r => !r.success).length,
                details: results,
            }),
            { headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );

    } catch (err) {
        console.error("Process Embeddings Error:", err);
        return new Response(
            JSON.stringify({ error: String(err) }),
            { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
    }
});
