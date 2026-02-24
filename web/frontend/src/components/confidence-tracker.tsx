/**
 * Confidence progression chart — shows how confidence changes over time.
 *
 * Uses Recharts (a React charting library) to render a line chart showing
 * the agent's confidence score at each investigation step. A dashed
 * reference line marks the confidence threshold.
 *
 * ARCHITECTURE NOTE — Dynamic import:
 * This component is imported via `confidence-tracker-wrapper.tsx` using
 * Next.js `dynamic()` with `ssr: false`. Recharts uses browser APIs
 * (canvas, DOM measurements) that don't exist on the server, so we
 * must skip server-side rendering. The wrapper handles this.
 *
 * RECHARTS PATTERNS:
 * - ResponsiveContainer: Makes the chart fill its parent's width
 * - LineChart: The chart type (could also be AreaChart, BarChart, etc.)
 * - XAxis/YAxis: Axis configuration (ticks, labels, domain)
 * - ReferenceLine: A fixed horizontal/vertical line (here: threshold)
 * - Tooltip: Popup on hover showing the data point's values
 * - Line: The actual data series (our confidence scores)
 */
"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ConfidencePoint } from "@/lib/types";

interface ConfidenceTrackerProps {
  data: ConfidencePoint[];  // Array of {step, score, category} from the hook
  threshold?: number;        // Confidence threshold (default 0.82 = 82%)
}

function ConfidenceTrackerInner({ data, threshold = 0.82 }: ConfidenceTrackerProps) {
  // Show placeholder while waiting for first confidence update
  if (data.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Confidence</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex h-[200px] items-center justify-center text-sm text-muted-foreground">
            Waiting for data...
          </div>
        </CardContent>
      </Card>
    );
  }

  // Transform 0-1 scores to 0-100 for display
  const chartData = data.map((d) => ({
    step: d.step,
    score: Math.round(d.score * 100),
    category: d.category,
  }));

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">
          Confidence Progression
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* ResponsiveContainer adapts to parent width, fixed 200px height */}
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: -20 }}>
            {/* X axis: investigation step numbers */}
            <XAxis
              dataKey="step"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            {/* Y axis: 0-100% range */}
            <YAxis
              domain={[0, 100]}
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `${v}%`}
            />
            {/* Dashed line showing the confidence threshold */}
            <ReferenceLine
              y={threshold * 100}
              stroke="hsl(var(--muted-foreground))"
              strokeDasharray="4 4"
              label={{ value: "Threshold", position: "right", fontSize: 10 }}
            />
            {/* Custom tooltip — shows score and category on hover */}
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const item = payload[0].payload;
                return (
                  <div className="rounded-md border bg-popover px-3 py-1.5 text-xs shadow-md">
                    <div className="font-medium">{item.score}%</div>
                    <div className="text-muted-foreground">{item.category}</div>
                  </div>
                );
              }}
            />
            {/* The confidence line — green color, 2px width */}
            <Line
              type="monotone"       // Smooth curve between points
              dataKey="score"
              stroke="hsl(142 69% 40%)"  // Green
              strokeWidth={2}
              dot={{ r: 4, fill: "hsl(142 69% 40%)" }}
              activeDot={{ r: 6 }}   // Larger dot on hover
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

export default ConfidenceTrackerInner;
