/**
 * Live activity feed showing graph node execution during classification.
 *
 * Displays a vertical timeline of pipeline steps as they happen:
 * - Spinning loader for the currently active node
 * - Green checkmark for completed nodes
 * - Node name, elapsed time, and action details
 *
 * This component is the "left column" during streaming, giving the user
 * real-time visibility into what the classification agent is doing.
 *
 * REACT CONCEPT — AnimatePresence:
 * Framer Motion's AnimatePresence enables exit animations. Without it,
 * elements just disappear instantly. With it, they can fade/slide out.
 * `mode="popLayout"` prevents layout shifts during animations.
 */
"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Check, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { NODE_LABELS } from "@/lib/constants";
import type { StreamEvent } from "@/lib/types";

interface ActivityFeedProps {
  events: StreamEvent[];       // All SSE events from use-classification hook
  currentNode: string | null;  // Which node is currently executing
}

export function ActivityFeed({ events, currentNode }: ActivityFeedProps) {
  // Filter to only node_start events — these represent pipeline steps
  const nodeEvents = events.filter((e) => e.event_type === "node_start");

  if (nodeEvents.length === 0) return null;

  return (
    <div className="space-y-0">
      <AnimatePresence mode="popLayout">
        {nodeEvents.map((event, i) => {
          // Determine the visual state of each timeline node
          const isActive = event.node_name === currentNode;
          const isComplete = i < nodeEvents.length - 1 || (!isActive && event.node_name !== currentNode);
          // Look up human-readable label (e.g., "GatherInfo" → "Gathering Information")
          const label = NODE_LABELS[event.node_name || ""] || event.node_name || "Unknown";

          return (
            <motion.div
              key={`${event.node_name}-${i}`}
              initial={{ opacity: 0, x: -10 }}   // Slide in from left
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3 }}
              className="flex gap-3"
            >
              {/* Timeline connector — vertical line with status circles */}
              <div className="flex flex-col items-center">
                {/*
                  cn() is a utility that conditionally joins CSS class names.
                  Like: " ".join([base, active_cls if is_active else "", ...])
                  It comes from the shadcn/ui library (uses clsx + tailwind-merge).
                */}
                <div
                  className={cn(
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 transition-colors",
                    isActive && "border-primary bg-primary/10 animate-pulse",
                    isComplete && "border-emerald-500 bg-emerald-500/10",
                    !isActive && !isComplete && "border-muted-foreground/30 bg-muted"
                  )}
                >
                  {/* Show check for complete, spinner for active, number for pending */}
                  {isComplete ? (
                    <Check className="h-4 w-4 text-emerald-500" />
                  ) : isActive ? (
                    <Loader2 className="h-4 w-4 text-primary animate-spin" />
                  ) : (
                    <span className="text-xs text-muted-foreground">{i + 1}</span>
                  )}
                </div>
                {/* Vertical connecting line between nodes (skip for last item) */}
                {i < nodeEvents.length - 1 && (
                  <div className="w-0.5 grow bg-border" />
                )}
              </div>

              {/* Content — node label and metadata */}
              <div className="pb-6 pt-1">
                <div className="flex items-center gap-2">
                  <span className={cn(
                    "text-sm font-medium",
                    isActive && "text-primary",
                    isComplete && "text-muted-foreground"
                  )}>
                    {label}
                  </span>
                  {/* Elapsed time shown in monospace for alignment */}
                  <span className="text-xs text-muted-foreground font-mono">
                    {event.timestamp.toFixed(1)}s
                  </span>
                </div>

                {/*
                  Action detail — shows what tool the agent is using.
                  typeof check needed because event.data is Record<string, unknown>.
                  Without it, TypeScript doesn't know the value is a string.
                */}
                {typeof event.data.action_detail === "string" && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {String(event.data.action_type)}: {event.data.action_detail}
                  </p>
                )}

                {/* Questions asked count — shows investigation progress */}
                {typeof event.data.questions_asked === "number" && event.data.questions_asked > 0 && (
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    Questions asked: {event.data.questions_asked}
                  </p>
                )}
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
