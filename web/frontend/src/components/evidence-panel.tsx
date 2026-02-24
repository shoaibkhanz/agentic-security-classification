/**
 * Tabbed panel showing all evidence sources gathered during classification.
 *
 * Groups evidence by source type (Database, SEC Filings, Web Search, etc.)
 * and displays each in a scrollable tab. Each evidence item shows the
 * source detail and content snippet.
 *
 * REACT CONCEPT — Derived/computed rendering:
 * Instead of storing grouped data in state, we compute the grouping
 * inline during render using `reduce()`. This is a functional programming
 * pattern — derive what you need from the source data.
 * Like Python's: `grouped = defaultdict(list); for s in sources: grouped[s.type].append(s)`
 *
 * SHADCN/UI CONCEPT — Tabs + ScrollArea:
 * Tabs switches between views. ScrollArea provides a styled scrollbar
 * container with a fixed height, preventing long evidence lists from
 * expanding the page infinitely.
 */
"use client";

import { Database, FileText, Globe, User } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { EvidenceSource } from "@/lib/types";

interface EvidencePanelProps {
  sources: EvidenceSource[];  // All evidence from the classification result
}

/**
 * TS CONCEPT — React.ReactNode as value type:
 * We store JSX elements (Lucide icons) as values in a Record.
 * React.ReactNode is the type for anything React can render.
 * This wouldn't work in Python — you'd use a factory function instead.
 */
const SOURCE_ICONS: Record<string, React.ReactNode> = {
  database: <Database className="h-3.5 w-3.5" />,
  sec_filing: <FileText className="h-3.5 w-3.5" />,
  web_search: <Globe className="h-3.5 w-3.5" />,
  user_answer: <User className="h-3.5 w-3.5" />,
};

const SOURCE_LABELS: Record<string, string> = {
  database: "Database",
  sec_filing: "SEC Filings",
  web_search: "Web Search",
  user_answer: "User Input",
};

export function EvidencePanel({ sources }: EvidencePanelProps) {
  if (sources.length === 0) return null;

  /**
   * Group evidence by source_type using reduce().
   *
   * JS CONCEPT — reduce():
   * Folds an array into a single value by applying a function to each element.
   * Like Python's: functools.reduce() or a manual loop with an accumulator.
   *
   * The `??=` operator (nullish coalescing assignment) creates the array
   * if it doesn't exist yet — like Python's `acc.setdefault(key, [])`.
   */
  const grouped = sources.reduce<Record<string, EvidenceSource[]>>((acc, s) => {
    (acc[s.source_type] ??= []).push(s);
    return acc;
  }, {});

  const tabs = Object.keys(grouped);

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium">Evidence Sources</CardTitle>
      </CardHeader>
      <CardContent>
        {/* First tab is selected by default */}
        <Tabs defaultValue={tabs[0]}>
          <TabsList>
            {tabs.map((type) => (
              <TabsTrigger key={type} value={type} className="gap-1.5 text-xs">
                {SOURCE_ICONS[type]}
                {SOURCE_LABELS[type] || type}
                {/* Count badge — shows how many items in this tab */}
                <Badge variant="secondary" className="ml-1 h-4 px-1 text-[10px]">
                  {grouped[type].length}
                </Badge>
              </TabsTrigger>
            ))}
          </TabsList>
          {tabs.map((type) => (
            <TabsContent key={type} value={type}>
              {/* ScrollArea with fixed height prevents page overflow */}
              <ScrollArea className="h-[250px]">
                <div className="space-y-3">
                  {grouped[type].map((source, i) => (
                    <div
                      key={i}
                      className="rounded-md border bg-muted/30 p-3 text-sm"
                    >
                      {/* Source detail (e.g., "Internal database - Atlas Notes") */}
                      <div className="mb-1 text-xs font-medium text-muted-foreground">
                        {source.source_detail}
                      </div>
                      {/* Evidence content snippet */}
                      <p className="text-sm leading-relaxed">{source.content}</p>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </TabsContent>
          ))}
        </Tabs>
      </CardContent>
    </Card>
  );
}
