/**
 * Workflow column -- renders the full list of investigation stages and questions.
 *
 * This is the "left column" in the classification UI. It groups questions by
 * pipeline stage (e.g., "Stage II - Research & Data Gathering") and renders
 * each question as a WorkflowQuestionCard with staggered animation.
 *
 * REACT CONCEPT -- Component composition:
 * This component doesn't render questions directly. Instead, it delegates to
 * `WorkflowQuestionCard`. This is composition -- building complex UIs from
 * small, focused components. Like Python classes that delegate to helpers
 * rather than doing everything in one giant method.
 *
 * REACT CONCEPT -- .map() for rendering lists:
 * React doesn't have a `for` loop in JSX. Instead, you call `.map()` on an array
 * to transform each item into a JSX element. This is like a Python list comprehension:
 *   [render_card(q) for q in questions]  <==>  questions.map(q => <Card ... />)
 *
 * Every mapped element needs a `key` prop -- a unique identifier so React can
 * efficiently update the DOM when items are added/removed/reordered. It's like
 * a primary key in a database table. Without it, React re-renders everything.
 *
 * REACT CONCEPT -- AnimatePresence:
 * Wrapping a list in `<AnimatePresence>` enables smooth enter/exit animations.
 * Without it, new items just pop in instantly. With it, they slide/fade in
 * using the `initial`/`animate` props on `motion.div` inside each card.
 * `mode="popLayout"` prevents layout jumps during animations.
 */
"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { STAGE_LABELS } from "@/lib/constants";
import type { WorkflowStage } from "@/lib/types";
import { WorkflowQuestionCard } from "./workflow-question-card";

interface WorkflowColumnProps {
  /** Array of stages, each containing an array of questions */
  stages: WorkflowStage[];
  /**
   * TS CONCEPT -- Optional props with `?`:
   * `className?` means the parent can omit this prop entirely.
   * Like Python's `def __init__(self, className: str | None = None)`.
   */
  className?: string;
}

/**
 * Running index counter for stagger delay.
 *
 * We want cards across ALL stages to stagger sequentially (Q1, Q2, Q3...),
 * not restart the stagger within each stage group. So we track a running
 * index and pass it to each WorkflowQuestionCard.
 */
export function WorkflowColumn({ stages, className }: WorkflowColumnProps) {
  const stageOffsets = stages.map((_, index) =>
    stages
      .slice(0, index)
      .reduce((sum, stage) => sum + stage.questions.length, 0)
  );

  return (
    <div className={cn("space-y-6", className)}>
      {/* Section heading — always visible so users know what this column is */}
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold">Investigation Workflow</h2>
        {stages.length === 0 && (
          <Loader2 className="h-3.5 w-3.5 text-muted-foreground animate-spin" />
        )}
      </div>

      {/* Placeholder when waiting for the first event */}
      {stages.length === 0 && (
        <div className="rounded-lg border border-dashed border-muted-foreground/25 p-8 text-center">
          <p className="text-sm text-muted-foreground/70">
            Starting classification pipeline...
          </p>
          <p className="text-xs text-muted-foreground/50 mt-1">
            Investigation steps will appear here as the agent works
          </p>
        </div>
      )}

      <AnimatePresence mode="popLayout">
        {stages.map((stage, stageIndex) => {
          /**
           * Look up the full stage label from constants.
           * Falls back to a constructed label if the stage key isn't in STAGE_LABELS.
           *
           * TS CONCEPT -- Nullish coalescing (`??`):
           * `a ?? b` means "use `a` if it's not null/undefined, otherwise use `b`".
           * Different from `||` which also treats `""`, `0`, `false` as falsy.
           * Python equivalent: `a if a is not None else b`.
           */
          const stageLabel =
            STAGE_LABELS[stage.stage] ?? `Stage ${stage.stage} - ${stage.stageName}`;

          return (
            /**
             * REACT CONCEPT -- Fragment-like grouping:
             * We need to return one element per stage, but we want both a heading
             * and a list of cards. We wrap them in a `motion.div` which also
             * gives us animation capabilities.
             *
             * motion.div animates the entire stage group (heading + cards) as a unit.
             */
            <motion.div
              key={stage.stage}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, ease: "easeOut" }}
              className="space-y-3"
            >
              {/* Stage heading -- e.g. "Stage II - Research & Data Gathering" */}
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {stageLabel}
              </h3>

              {/* Question cards within this stage */}
              <div className="space-y-2">
                {stage.questions.map((question, questionIndex) => {
                  const cardIndex = (stageOffsets[stageIndex] ?? 0) + questionIndex;

                  return (
                    <WorkflowQuestionCard
                      key={`q-${question.questionNumber}`}
                      question={question}
                      index={cardIndex}
                    />
                  );
                })}
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
