"use client";

import dynamic from "next/dynamic";
import type { ConfidencePoint } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const ConfidenceTracker = dynamic(() => import("./confidence-tracker"), {
  ssr: false,
  loading: () => (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Confidence</CardTitle>
      </CardHeader>
      <CardContent>
        <Skeleton className="h-[200px] w-full" />
      </CardContent>
    </Card>
  ),
});

export { ConfidenceTracker };
export type { ConfidencePoint };
