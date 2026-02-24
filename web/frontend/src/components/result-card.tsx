/**
 * Displays the final classification result after the pipeline completes.
 *
 * Shows: category badge (color-coded), confidence percentage,
 * summary text, alternative classifications, and metadata.
 *
 * REACT CONCEPT — children prop:
 * `children?: React.ReactNode` lets this component wrap other components.
 * Usage: <ResultCard result={...}><FeedbackSheet /></ResultCard>
 * The FeedbackSheet appears inside the card's footer area.
 * This is called "composition" — a core React pattern for flexible layouts.
 */
"use client";

import { motion } from "framer-motion";
import { Clock, HelpCircle, TrendingUp } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CATEGORY_COLORS, CATEGORY_LABELS } from "@/lib/constants";
import type { ClassificationResult, SecurityCategory } from "@/lib/types";

interface ResultCardProps {
  result: ClassificationResult;
  children?: React.ReactNode;  // Slot for feedback/action buttons
}

export function ResultCard({ result, children }: ResultCardProps) {
  // Look up display colors and label for the classified category
  const colors = CATEGORY_COLORS[result.category];
  const label = CATEGORY_LABELS[result.category];
  const pct = Math.round(result.confidence * 100);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}     // Slide up animation on appear
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
    >
      <Card className="overflow-hidden">
        <CardContent className="p-6">
          {/* Top row: Category badge (left) + Confidence % (right) */}
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              {/*
                Template literal for className — builds a dynamic class string.
                `${colors.bg} ${colors.text}` resolves to e.g.,
                "bg-blue-500/15 text-blue-400 border-blue-500/30"
              */}
              <Badge
                variant="secondary"
                className={`${colors.bg} ${colors.text} ${colors.border} border px-3 py-1 text-sm font-semibold`}
              >
                {label}
              </Badge>
              <p className="text-sm text-muted-foreground">Classification</p>
            </div>

            <div className="text-right">
              <div className="flex items-center gap-1.5">
                <TrendingUp className="h-4 w-4 text-muted-foreground" />
                {/* Large monospace number for the confidence percentage */}
                <span className="text-3xl font-bold font-mono tracking-tight">
                  {pct}%
                </span>
              </div>
              <p className="text-sm text-muted-foreground">Confidence</p>
            </div>
          </div>

          {/* Summary — the agent's plain-English explanation */}
          <p className="mt-4 text-sm text-muted-foreground leading-relaxed">
            {result.summary}
          </p>

          {/* Alternative classifications the agent also considered */}
          {result.alternative_classifications.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <HelpCircle className="h-3 w-3" />
                Also considered:
              </span>
              {result.alternative_classifications.map((alt) => {
                /*
                  Type assertion: `alt.category as SecurityCategory`
                  The backend sends a string, but we know it's one of our categories.
                  `as` tells TypeScript to treat it as the narrower type.
                  Like Python's cast(SecurityCategory, alt.category).
                */
                const altColors = CATEGORY_COLORS[alt.category as SecurityCategory];
                return (
                  <Badge
                    key={alt.category}
                    variant="outline"
                    className={`${altColors?.text || ""} text-[10px]`}
                  >
                    {CATEGORY_LABELS[alt.category as SecurityCategory] || alt.category}{" "}
                    {Math.round(alt.confidence * 100)}%
                  </Badge>
                );
              })}
            </div>
          )}

          {/* Footer: metadata + children (feedback button) */}
          <div className="mt-4 flex items-center justify-between border-t pt-3">
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <HelpCircle className="h-3 w-3" />
                {result.questions_asked} questions
              </span>
              {result.total_duration && (
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {result.total_duration.toFixed(1)}s
                </span>
              )}
            </div>
            {/* children renders here — typically the FeedbackSheet component */}
            {children}
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
