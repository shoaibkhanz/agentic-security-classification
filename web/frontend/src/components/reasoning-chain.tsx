/**
 * Inline reasoning chain showing live execution details as cards.
 *
 * Each step shows: step number, source badge, inference text,
 * confidence delta, and the current evidence text.
 */
"use client";

import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { ReasoningStep } from "@/lib/types";

interface ReasoningChainProps {
  steps: ReasoningStep[];  // Ordered list of reasoning steps from the result
}

/** Color-coded badges for each evidence source type. */
const SOURCE_COLORS: Record<string, string> = {
  database: "bg-blue-500/15 text-blue-400",
  sec_filing: "bg-amber-500/15 text-amber-400",
  web_search: "bg-violet-500/15 text-violet-400",
  user_answer: "bg-emerald-500/15 text-emerald-400",
};

export function ReasoningChain({ steps }: ReasoningChainProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium">Execution Details</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {steps.length === 0 && (
          <div className="rounded-lg border border-dashed border-muted-foreground/25 p-4 text-sm text-muted-foreground/70">
            Reasoning, planned questions, and findings will appear here as the run executes.
          </div>
        )}

        {steps.map((step, i) => (
          <motion.div
            key={`${step.step}-${i}`}
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08, duration: 0.25 }}
            className="rounded-lg border p-3 space-y-2"
          >
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium">
                {step.step}
              </span>
              <Badge
                variant="secondary"
                className={cn("text-[10px]", SOURCE_COLORS[step.source] || "")}
              >
                {step.source}
              </Badge>
              <span
                className={cn(
                  "ml-auto shrink-0 font-mono text-xs",
                  step.confidence_delta >= 0 ? "text-emerald-400" : "text-rose-400"
                )}
              >
                {step.confidence_delta >= 0 ? "+" : ""}
                {step.confidence_delta.toFixed(2)}
              </span>
            </div>
            <p className="text-sm">{step.inference}</p>
            <p className="text-xs text-muted-foreground">
              <span className="font-medium text-foreground/80">Evidence:</span>{" "}
              {step.evidence}
            </p>
          </motion.div>
        ))}
      </CardContent>
    </Card>
  );
}
