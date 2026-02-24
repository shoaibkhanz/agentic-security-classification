/**
 * Example security cards for the landing page.
 *
 * Displays curated example securities that users can click to start
 * a classification. Each card shows the security name, issuer,
 * description, and difficulty level.
 *
 * REACT CONCEPT — Component Props:
 * Components receive data through "props" (properties), defined as
 * a TypeScript interface. This is like a Python function's parameters
 * but for UI components. Props flow ONE WAY: parent → child.
 *
 * REACT CONCEPT — "use client":
 * Next.js renders components on the server by default (for SEO/performance).
 * "use client" tells Next.js this component needs browser features
 * (useState, useEffect, onClick handlers) and must run in the browser.
 * Think of it as marking code that needs the browser's DOM/event system.
 */
"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { fetchExamples } from "@/lib/api";
import { DIFFICULTY_COLORS } from "@/lib/constants";
import type { ExampleSecurity } from "@/lib/types";

/**
 * Props interface — defines what the parent must pass to this component.
 *
 * `onSelect: (description: string) => void` is a callback function prop.
 * The parent passes a function, and this component calls it when clicked.
 * Like Python's callable parameter: `on_select: Callable[[str], None]`.
 */
interface ExampleCardsProps {
  onSelect: (description: string) => void;
}

export function ExampleCards({ onSelect }: ExampleCardsProps) {
  // Fetch examples from the API on mount
  const [examples, setExamples] = useState<ExampleSecurity[]>([]);

  /**
   * useEffect with empty deps `[]` = run once on mount.
   * `.then(setExamples)` is shorthand for `.then(data => setExamples(data))`.
   * `.catch(() => {})` silently ignores errors (examples are non-critical).
   */
  useEffect(() => {
    fetchExamples().then(setExamples).catch(() => {});
  }, []);

  // Don't render anything until examples load
  if (examples.length === 0) return null;

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Or try an example:
      </p>
      {/*
        CSS Grid layout: 1 column on mobile, 2 on small screens, 3 on large.
        `gap-3` adds spacing between grid items.
      */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {/*
          REACT CONCEPT — List rendering with .map():
          In React, you render lists by mapping data to JSX elements.
          Like Python's list comprehension: [render(ex) for ex in examples].
          Each item needs a unique `key` prop for React's diffing algorithm.
        */}
        {examples.map((ex, i) => (
          <motion.div
            key={ex.name}
            initial={{ opacity: 0, y: 10 }}     // Start invisible and below
            animate={{ opacity: 1, y: 0 }}       // Animate to visible and in place
            transition={{ delay: i * 0.1, duration: 0.3 }}  // Stagger each card
          >
            <Card
              className="cursor-pointer p-4 transition-colors hover:bg-accent/50"
              onClick={() => onSelect(ex.description)}
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium truncate">{ex.name}</span>
                  {/* Difficulty badge with color from constants */}
                  <Badge
                    variant="secondary"
                    className={`text-[10px] ${DIFFICULTY_COLORS[ex.difficulty] || ""}`}
                  >
                    {ex.difficulty}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">{ex.issuer}</p>
                {/* line-clamp-2 truncates text to 2 lines with ellipsis */}
                <p className="text-xs text-muted-foreground line-clamp-2">
                  {ex.description}
                </p>
              </div>
            </Card>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
