/**
 * Individual question card in the workflow visualization column.
 *
 * Each card represents one "investigation step" the classification agent took:
 * what question it asked, which tool it called, what it expected to learn,
 * what it found, and how that changed its confidence.
 *
 * ARCHITECTURE — Card anatomy:
 * ┌──────────────────────────────────────────┐
 * │ [Q1] Stage II - Research      [+8%] [✓] │  ← Header row
 * │                                          │
 * │ "Search for Atlas Infrastructure Corp    │  ← Investigation query
 * │  SEC filings to determine offering type" │     (actionDetail)
 * │                                          │
 * │ ┌─ 🔍 Tool Call ──────────────────────┐  │
 * │ │  SEC EDGAR Data Parser               │  │  ← Tool call block
 * │ │  Data source: SEC EDGAR              │  │     (toolName + dataSource)
 * │ └─────────────────────────────────────┘  │
 * │                                          │
 * │ 💡 Expected: Determine if registered    │  ← Expected info gain
 * │                                          │
 * │ ✅ Found: Atlas filed Form D under Reg  │  ← Finding (when complete)
 * │    D 506(b), $25M offering...           │
 * └──────────────────────────────────────────┘
 *
 * TS CONCEPT — Interface props:
 * In React, every component receives a single "props" object (like **kwargs).
 * We define its shape with an `interface`. TypeScript will error at compile
 * time if you pass the wrong props — similar to Pydantic model validation,
 * but at build time rather than runtime.
 *
 * REACT CONCEPT — Conditional rendering:
 * JSX uses `{condition && <Element />}` instead of Python's
 * `if condition: render()`. The `&&` operator short-circuits:
 * if the left side is falsy, React renders nothing.
 */
"use client";

import { motion } from "framer-motion";
import {
  Check,
  Loader2,
  Database,
  FileText,
  Globe,
  User,
  Search,
  Lightbulb,
  MessageSquare,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { WorkflowQuestion } from "@/lib/types";

/**
 * Map data source names to Lucide icon components.
 *
 * TS CONCEPT — Record<string, ComponentType>:
 * This maps string keys to React component types, like a Python dict
 * mapping strings to classes. We use it to dynamically pick an icon
 * component based on the data source name from the backend.
 */
const DATA_SOURCE_ICON_MAP: Record<string, typeof Database> = {
  "Internal Database": Database,
  "SEC EDGAR": FileText,
  "Public Web": Globe,
  "Human Input": User,
};

/**
 * Map action types to human-readable verbs for the investigation label.
 *
 * When the agent decides to use a tool, we show a descriptive label
 * like "Querying database..." or "Searching SEC EDGAR..." rather than
 * the raw action type like "query_db".
 */
const ACTION_LABELS: Record<string, string> = {
  query_db: "Querying securities database",
  search_sec: "Searching SEC EDGAR filings",
  search_web: "Searching the web",
  ask_question: "Asking analyst",
};

interface WorkflowQuestionCardProps {
  question: WorkflowQuestion;
  /** Animation delay index — used by parent to stagger card appearances */
  index?: number;
}

export function WorkflowQuestionCard({ question, index = 0 }: WorkflowQuestionCardProps) {
  const {
    questionNumber,
    stageName,
    actionType,
    actionDetail,
    toolName,
    dataSource,
    expectedInfoGain,
    status,
    confidenceDeltaPct,
    finding,
    currentCategory,
  } = question;

  /**
   * Pick the right icon for this data source.
   *
   * TS CONCEPT — Dynamic component rendering:
   * In React, components are just values (functions). You can store them in
   * variables and render them with JSX: `<IconComponent />`. This is like
   * Python's first-class functions: `fn = my_func; fn()`.
   */
  const IconComponent = dataSource
    ? DATA_SOURCE_ICON_MAP[dataSource] ?? Database
    : Database;

  /** Format confidence delta for display. */
  const deltaText =
    confidenceDeltaPct !== null
      ? `${confidenceDeltaPct >= 0 ? "+" : ""}${confidenceDeltaPct}%`
      : null;
  const deltaIsPositive = (confidenceDeltaPct ?? 0) >= 0;

  /** Build a human-readable action label from the action type and detail. */
  const actionLabel = actionType ? ACTION_LABELS[actionType] ?? actionType : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.08 }}
    >
      <Card
        className={cn(
          "transition-colors",
          status === "active" && "border-primary/50 shadow-sm shadow-primary/10",
          status === "complete" && "border-border"
        )}
      >
        <CardContent className="p-4 space-y-3">
          {/* ============================================================
              HEADER ROW: Q badge + stage + confidence delta + status
              ============================================================ */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-xs font-mono px-1.5 py-0.5">
                Q{questionNumber}
              </Badge>
              <span className="text-xs text-muted-foreground">{stageName}</span>
              {/* Current category guess at this point */}
              {currentCategory && (
                <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                  {currentCategory}
                </Badge>
              )}
            </div>

            <div className="flex items-center gap-2">
              {deltaText && (
                <Badge
                  variant="secondary"
                  className={cn(
                    "text-[10px] font-mono px-1.5 py-0",
                    deltaIsPositive
                      ? "bg-emerald-500/15 text-emerald-400"
                      : "bg-red-500/15 text-red-400"
                  )}
                >
                  {deltaText}
                </Badge>
              )}
              {status === "complete" && (
                <div className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/15">
                  <Check className="h-3 w-3 text-emerald-500" />
                </div>
              )}
              {status === "active" && (
                <Loader2 className="h-4 w-4 text-primary animate-spin" />
              )}
            </div>
          </div>

          {/* ============================================================
              INVESTIGATION QUERY — What the agent is asking/doing
              This is the main text of the card. Shows either:
              - The action label + detail (e.g., "Searching SEC EDGAR
                for Atlas Infrastructure Corp")
              - The stage name as fallback for non-GatherInfo nodes
              ============================================================ */}
          {actionDetail ? (
            <div className="space-y-1">
              {/* Action verb label (e.g., "Searching SEC EDGAR filings") */}
              {actionLabel && (
                <p className="text-xs font-medium text-primary/80 flex items-center gap-1.5">
                  <Search className="h-3 w-3" />
                  {actionLabel}
                </p>
              )}
              {/* The specific query — this is the most important text */}
              <p className="text-sm leading-relaxed">
                {actionDetail}
              </p>
            </div>
          ) : (
            /* For non-tool nodes (InitialAssessment, Classify, Verify),
               show a descriptive label based on stage */
            <p className="text-sm text-muted-foreground">
              {stageName === "Initial Assessment" && "Analyzing security description and planning investigation..."}
              {stageName === "Confidence Assessment" && "Re-evaluating confidence with new evidence..."}
              {stageName === "Action Planning" && "Planning next investigation step..."}
              {stageName === "Classification" && "Producing final classification with reasoning chain..."}
              {stageName === "Verification" && "Verifying reasoning for logical consistency..."}
              {!stageName && "Processing..."}
            </p>
          )}

          {/* ============================================================
              TOOL CALL BLOCK — Shows which tool is being invoked
              Visually distinct block with icon, tool name, and data source.
              Only shown when we have tool/data source info.
              ============================================================ */}
          {(toolName || dataSource) && (
            <div className="rounded-md border border-dashed border-muted-foreground/25 bg-muted/30 px-3 py-2">
              <div className="flex items-center gap-2">
                <IconComponent className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium truncate">
                    {toolName}
                  </p>
                  {dataSource && (
                    <p className="text-[10px] text-muted-foreground">
                      Data source: {dataSource}
                    </p>
                  )}
                </div>
                {status === "active" && (
                  <Badge variant="outline" className="text-[10px] px-1.5 py-0 animate-pulse border-primary/30 text-primary">
                    Running...
                  </Badge>
                )}
              </div>
            </div>
          )}

          {/* ============================================================
              EXPECTED INFO GAIN — What the agent hopes to learn
              Shows the agent's reasoning for choosing this action.
              ============================================================ */}
          {expectedInfoGain && (
            <div className="flex items-start gap-1.5 text-xs text-muted-foreground/70">
              <Lightbulb className="h-3 w-3 mt-0.5 shrink-0 text-amber-500/60" />
              <span className="italic">{expectedInfoGain}</span>
            </div>
          )}

          {/* ============================================================
              FINDING — What the agent actually found
              Only shown for completed investigation steps.
              ============================================================ */}
          {finding && status === "complete" && (
            <div className="rounded-md bg-emerald-500/5 border border-emerald-500/20 px-3 py-2">
              <div className="flex items-start gap-1.5">
                <MessageSquare className="h-3 w-3 mt-0.5 shrink-0 text-emerald-500/70" />
                <p className="text-xs leading-relaxed text-emerald-200/80 line-clamp-3">
                  {finding}
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}
