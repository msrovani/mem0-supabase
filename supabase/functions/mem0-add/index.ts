// File: supabase/functions/mem0-add/index.ts
// This Edge Function provides an HTTP endpoint to add memories to the Supabase vector store.

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

serve(async (req: Request) => {
    // Handle CORS preflight
    if (req.method === "OPTIONS") {
        return new Response("ok", { headers: corsHeaders });
    }

    try {
        const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
        const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
        const openaiKey = Deno.env.get("OPENAI_API_KEY");

        const supabase = createClient(supabaseUrl, supabaseKey);

        const { content, user_id, metadata } = await req.json();

        if (!content || !user_id) {
            return new Response(
                JSON.stringify({ error: "Missing 'content' or 'user_id'" }),
                { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
        }

        // 1. Generate embedding via OpenAI
        const embeddingResponse = await fetch("https://api.openai.com/v1/embeddings", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${openaiKey}`,
            },
            body: JSON.stringify({
                model: "text-embedding-ada-002",
                input: content,
            }),
        });

        const embeddingData = await embeddingResponse.json();
        const embedding = embeddingData.data?.[0]?.embedding;

        if (!embedding) {
            return new Response(
                JSON.stringify({ error: "Failed to generate embedding" }),
                { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
        }

        // 2. Insert into vecs.memories (assumes table exists via setup_wizard)
        const { data, error } = await supabase.from("memories").insert({
            vec: embedding,
            metadata: {
                data: content,
                user_id: user_id,
                ...metadata,
                created_at: new Date().toISOString(),
            },
        }).select("id");

        if (error) {
            console.error("Supabase insert error:", error);
            return new Response(
                JSON.stringify({ error: error.message }),
                { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
        }

        return new Response(
            JSON.stringify({ success: true, memory_id: data?.[0]?.id }),
            { headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );

    } catch (err) {
        console.error("Edge Function Error:", err);
        return new Response(
            JSON.stringify({ error: String(err) }),
            { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
    }
});
