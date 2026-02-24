/**
 * Individual evidence card showing a single piece of evidence gathered
 * by the classification agent. Displays source type icon, key metadata
 * fields, a content snippet, and a signal-strength badge.
 *
 * TS CONCEPT — Discriminated unions and lookup maps:
 * The `source_type` field is a string literal union ("database" | "sec_filing" | ...).
 * We use it as a key to look up the matching icon, label, and signal color.
 * In Python, you'd do this with a dict: `ICONS = {"database": DatabaseIcon, ...}`.
 * In TypeScript, `Record<string, T>` is the same idea, but the compiler
 * checks that you handle every key if the key type is a finite union.
 *
 * REACT CONCEPT — Props interface and destructuring:
 * React components receive data through "props" — an object of named values
 * passed from the parent component (like **kwargs in Python).
 * We define the shape with a TypeScript interface and destructure in the
 * function signature: `({ source, toolName, relevance })`.
 * This is equivalent to Python's:
 *   def evidence_item_card(*, source: EvidenceSource, tool_name: str | None, relevance: float):
 *
 * REACT CONCEPT — Conditional rendering with `&&`:
 * `{toolName && <span>{toolName}</span>}` renders the span only if toolName
 * is truthy. This replaces Python's `if tool_name: render(...)`.
 * It works because `false && <JSX>` evaluates to `false`, and React skips
 * rendering `false`, `null`, and `undefined`.
 */
"use client";

import { Database, FileText, Globe, User } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { EvidenceSource } from "@/lib/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

/**
 * TS CONCEPT — Extending types with extra fields:
 * EvidenceItemCardProps takes the core EvidenceSource data plus optional
 * display hints that the parent computes (tool name, relevance score).
 * In Python/Pydantic you'd inherit: `class Props(EvidenceSource): tool_name: str | None`
 */
interface EvidenceItemCardProps {
  /** The evidence data from the classification result */
  source: EvidenceSource;
  /** Pretty tool name from the workflow (e.g. "Securities Database Query") */
  toolName?: string | null;
  /**
   * Relevance score 0-1 — determines the signal-strength badge.
   * Computed by the parent from confidence_delta or defaulted.
   */
  relevance?: number;
}

// ---------------------------------------------------------------------------
// Icon lookup — maps source_type strings to Lucide icon components
// ---------------------------------------------------------------------------

/**
 * TS CONCEPT — Storing JSX elements in a Record:
 * JSX elements like <Database .../> are values you can store in variables
 * and data structures, just like any other value. `React.ReactNode` is the
 * type that covers all renderable values (elements, strings, numbers, null).
 * In Python, you'd store factory callables instead: `{"database": lambda: DatabaseIcon()}`.
 */
const SOURCE_ICONS: Record<string, React.ReactNode> = {
  database: <Database className="h-4 w-4" />,
  sec_filing: <FileText className="h-4 w-4" />,
  web_search: <Globe className="h-4 w-4" />,
  user_answer: <User className="h-4 w-4" />,
};

const SOURCE_LABELS: Record<string, string> = {
  database: "Database",
  sec_filing: "SEC Filing",
  web_search: "Web Search",
  user_answer: "User Input",
};

// ---------------------------------------------------------------------------
// Signal-strength helpers
// ---------------------------------------------------------------------------

/**
 * Classify a 0-1 relevance score into a human-readable signal strength.
 *
 * TS CONCEPT — `as const` return type inference:
 * The `as const` assertions below narrow the return type from `string`
 * to the literal string (e.g. "Strong Signal"). This is like Python's
 * `Literal["Strong Signal", "Partial Match", "Weak Signal"]`.
 */
function getSignalStrength(relevance: number) {
  if (relevance >= 0.7) return { label: "Strong Signal", variant: "strong" as const };
  if (relevance >= 0.4) return { label: "Partial Match", variant: "partial" as const };
  return { label: "Weak Signal", variant: "weak" as const };
}

/**
 * Tailwind classes for each signal strength variant.
 * Uses the same opacity-modifier pattern as CATEGORY_COLORS in constants.ts.
 */
const SIGNAL_COLORS: Record<string, string> = {
  strong: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  partial: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  weak: "bg-slate-500/15 text-slate-400 border-slate-500/30",
};

// ---------------------------------------------------------------------------
// Truncation helper
// ---------------------------------------------------------------------------

/** Truncate long content to `maxLen` characters with an ellipsis. */
function truncate(text: string, maxLen: number = 180): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen).trimEnd() + "\u2026"; // unicode ellipsis
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * REACT CONCEPT — Named export:
 * `export function EvidenceItemCard(...)` is a named export.
 * The parent imports it as: `import { EvidenceItemCard } from "./evidence-item-card"`.
 * Named exports are like Python's `from module import EvidenceItemCard`.
 * (A "default export" would be like Python's `import module` — only one per file.)
 */
export function EvidenceItemCard({
  source,
  toolName,
  relevance = 0.5,
}: EvidenceItemCardProps) {
  const icon = SOURCE_ICONS[source.source_type] ?? <FileText className="h-4 w-4" />;
  const label = toolName || SOURCE_LABELS[source.source_type] || source.source_type;
  const signal = getSignalStrength(relevance);

  return (
    /*
     * REACT CONCEPT — className string composition with cn():
     * cn() merges Tailwind classes safely. It comes from shadcn/ui and wraps
     * `clsx` + `tailwind-merge`. It's like building a CSS class list but with
     * deduplication so "p-3 p-4" resolves to just "p-4".
     */
    <Card className={cn("border bg-card/50")}>
      <CardContent className="p-3 space-y-2">
        {/* ---- Header row: icon + title + signal badge ---- */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            {/*
              The icon from our lookup. `text-muted-foreground` makes it
              a subtle gray that adapts to light/dark theme.
            */}
            <span className="text-muted-foreground shrink-0">{icon}</span>
            <span className="text-sm font-medium truncate">{label}</span>
          </div>

          {/* Signal strength badge */}
          <Badge
            variant="outline"
            className={cn(
              "shrink-0 border text-[10px] px-1.5 py-0",
              SIGNAL_COLORS[signal.variant],
            )}
          >
            {signal.label}
          </Badge>
        </div>

        {/* ---- Key-value metadata fields ---- */}
        {/*
          REACT CONCEPT — Inline array mapping for repeated UI:
          Instead of a for-loop, React renders lists by mapping an array
          to JSX elements. Each element needs a unique `key` prop so React
          can efficiently update the DOM when items change.
          Python equivalent: [render_row(k, v) for k, v in fields]
        */}
        <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
          <span className="text-muted-foreground">Data Source</span>
          <span>{SOURCE_LABELS[source.source_type] || source.source_type}</span>

          <span className="text-muted-foreground">Source Detail</span>
          <span className="truncate">{source.source_detail}</span>
        </div>

        {/* ---- Content snippet ---- */}
        <p className="text-xs text-muted-foreground leading-relaxed">
          {truncate(source.content)}
        </p>
      </CardContent>
    </Card>
  );
}
