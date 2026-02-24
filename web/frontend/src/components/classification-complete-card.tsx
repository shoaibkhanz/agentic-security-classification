/**
 * Success card shown when the classification pipeline finishes.
 *
 * Displays a green "Classification Complete" banner with the final category,
 * confidence percentage, audit comment, and total duration. This is the
 * "happy path" end state -- the agent classified the security successfully.
 *
 * REACT CONCEPT -- Props interface design:
 * Notice we pick individual fields (`category`, `confidence`, etc.) instead of
 * passing the entire `ClassificationResult` object. This is intentional:
 * 1. The component only re-renders when these specific values change.
 * 2. It's clear exactly what data the component needs (explicit dependencies).
 * 3. The component is more reusable -- it doesn't depend on the full result shape.
 *
 * In Python terms: prefer `def show(category: str, confidence: float)` over
 * `def show(result: ClassificationResult)` when you only need a few fields.
 *
 * NEXT.JS CONCEPT -- "use client":
 * This directive marks the component as a Client Component. It runs in the
 * browser (not on the server). We need it because we use Framer Motion
 * animations which require browser APIs. Server Components (the default in
 * Next.js App Router) can't use hooks, event handlers, or browser-only libs.
 * Think of it like Python's `if __name__ == "__main__"` -- it declares the
 * execution context.
 */
"use client";

import { motion } from "framer-motion";
import { CheckCircle2, Clock } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { CATEGORY_CODES, CATEGORY_COLORS } from "@/lib/constants";
import type { SecurityCategory } from "@/lib/types";

interface ClassificationCompleteCardProps {
  /** The final classification category (e.g., "equity", "debt") */
  category: SecurityCategory;
  /** Confidence score from 0 to 1 (like Python's float in [0, 1]) */
  confidence: number;
  /** Short audit trail comment built from the agent's top reasoning steps */
  auditComment?: string | null;
  /** Total pipeline duration in seconds */
  totalDuration?: number | null;
  /** Optional extra CSS classes for the outer wrapper */
  className?: string;
}

export function ClassificationCompleteCard({
  category,
  confidence,
  auditComment,
  totalDuration,
  className,
}: ClassificationCompleteCardProps) {
  /**
   * Look up the category code (e.g., "A02") and label (e.g., "Debt Securities")
   * from our centralized constants. Falls back to "A99 - Unclassified" if the
   * category isn't found -- defensive coding against unexpected backend values.
   *
   * TS CONCEPT -- Optional chaining (`?.`):
   * `CATEGORY_CODES[category]?.code` safely accesses `.code` even if the lookup
   * returns `undefined`. Without `?.`, accessing `.code` on `undefined` would
   * throw a TypeError at runtime. Python equivalent: `getattr(obj, 'code', None)`.
   */
  const catInfo = CATEGORY_CODES[category];
  const code = catInfo?.code ?? "A99";
  const label = catInfo?.label ?? "Unclassified";
  const colors = CATEGORY_COLORS[category];
  const pct = Math.round(confidence * 100);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className={className}
    >
      {/*
       * SHADCN/UI CONCEPT -- Composing Card sub-components:
       * shadcn/ui provides Card, CardHeader, CardContent, CardFooter, etc.
       * You pick which sub-components you need. Here we only use Card + CardContent
       * because we want a compact layout. The Card provides the border, shadow,
       * and background; CardContent provides the padding.
       *
       * The green border and background tint come from Tailwind utility classes:
       * `border-emerald-500/40` = emerald border at 40% opacity
       * `bg-emerald-500/5` = very subtle emerald background wash
       */}
      <Card className="border-emerald-500/40 bg-emerald-500/5">
        <CardContent className="p-5">
          {/* Header row: checkmark icon + "Classification Complete" title */}
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-500/15">
              <CheckCircle2 className="h-5 w-5 text-emerald-500" />
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="text-sm font-semibold text-emerald-400">
                Classification Complete
              </h3>
              <p className="text-xs text-muted-foreground">
                Pipeline finished successfully
              </p>
            </div>
          </div>

          {/* Category + confidence row */}
          <div className="mt-4 flex items-center justify-between">
            {/*
             * SHADCN/UI CONCEPT -- Badge with dynamic styling:
             * We use `cn()` to merge the component's base classes with our
             * dynamic category-specific colors. This is a common pattern:
             * the Badge component defines its shape/size, we override its colors.
             */}
            <Badge
              variant="secondary"
              className={cn(
                "border px-3 py-1 text-sm font-semibold",
                colors?.bg,
                colors?.text,
                colors?.border
              )}
            >
              {code} &mdash; {label}
            </Badge>

            {/* Confidence percentage in bold monospace */}
            <span className="text-2xl font-bold font-mono tracking-tight text-emerald-400">
              {pct}%
            </span>
          </div>

          {/* Audit comment -- the agent's reasoning summary */}
          {auditComment && (
            <p className="mt-3 text-xs text-muted-foreground leading-relaxed">
              {auditComment}
            </p>
          )}

          {/* Duration footer */}
          {totalDuration != null && (
            <div className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
              {/*
               * TS CONCEPT -- != null (loose equality check):
               * `totalDuration != null` checks for both `null` AND `undefined`.
               * This is one of the few cases where loose equality (`!=`) is
               * preferred over strict (`!==`) in TypeScript. It's a common
               * idiom for "this optional value was actually provided".
               * Python equivalent: `total_duration is not None`.
               */}
              <Clock className="h-3.5 w-3.5" />
              <span>Completed in {totalDuration.toFixed(1)}s</span>
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}
