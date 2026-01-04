// File: supabase/functions/mem0-dream/index.ts
// This Edge Function consolidates recent memories into summaries ("Dreaming").
// It is designed to be called by pg_cron on a schedule (e.g., nightly).

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

serve(async (req: Request) => {
    if (req.method === "OPTIONS") {
        return new Response("ok", { headers: corsHeaders });
    }

    try {
        const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
        const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
        const openaiKey = Deno.env.get("OPENAI_API_KEY");

        const supabase = createClient(supabaseUrl, supabaseKey);

        // 1. Fetch recent history entries (last 24 hours, limit 100)
        const oneDayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
        const { data: historyRecords, error: histError } = await supabase
            .from("history")
            .select("*")
            .gte("created_at", oneDayAgo)
            .limit(100);

        if (histError) {
            console.error("History fetch error:", histError);
            return new Response(JSON.stringify({ error: histError.message }), {
                status: 500,
                headers: { ...corsHeaders, "Content-Type": "application/json" },
            });
        }

        if (!historyRecords || historyRecords.length === 0) {
            return new Response(
                JSON.stringify({ message: "No recent history to consolidate." }),
                { headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
        }

        // 2. Summarize with OpenAI
        const textToSummarize = historyRecords
            .map((r) => `[${r.event}] ${r.new_memory || r.old_memory}`)
            .join("\n");

        const summaryResponse = await fetch("https://api.openai.com/v1/chat/completions", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${openaiKey}`,
            },
            body: JSON.stringify({
                model: "gpt-4o-mini",
                messages: [
                    {
                        role: "system",
                        content: "You are an AI memory consolidator. Summarize the following memory events into key insights for long-term storage. Be concise and extract only the most important facts.",
                    },
                    { role: "user", content: textToSummarize },
                ],
                max_tokens: 500,
            }),
        });

        const summaryData = await summaryResponse.json();
        const summary = summaryData.choices?.[0]?.message?.content || "No summary generated.";

        console.log("Consolidated Summary:", summary);

        // 3. (Optional) Store summary as a new "consolidated" memory
        // This part can be expanded to insert into vecs.memories with a special tag.

        return new Response(
            JSON.stringify({
                success: true,
                records_processed: historyRecords.length,
                summary: summary,
            }),
            { headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );

    } catch (err) {
        console.error("Dream Function Error:", err);
        return new Response(
            JSON.stringify({ error: String(err) }),
            { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
    }
});
