"use client";

import { ClipboardList } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useOperatorQueue } from "@/hooks/use-operator-queue";
import { OperatorQueueList } from "@/components/operator-queue-list";
import type { ClassificationRecord } from "@/lib/types";

interface LandingTabsProps {
  children: React.ReactNode;
  onReview: (record: ClassificationRecord) => void;
  activeTab?: "workflows" | "queue";
  onTabChange?: (value: "workflows" | "queue") => void;
}

export function LandingTabs({
  children,
  onReview,
  activeTab,
  onTabChange,
}: LandingTabsProps) {
  const { count } = useOperatorQueue();

  return (
    <Tabs
      value={activeTab}
      onValueChange={(value) => onTabChange?.(value as "workflows" | "queue")}
      defaultValue="workflows"
      className="w-full"
    >
      <TabsList className="w-full">
        <TabsTrigger value="workflows" className="flex-1">
          Workspace
        </TabsTrigger>

        <TabsTrigger value="queue" className="flex-1 gap-1.5">
          <ClipboardList className="h-3.5 w-3.5" />
          Review Queue
          {count > 0 && (
            <Badge
              variant="secondary"
              className={cn(
                "ml-1 h-5 min-w-[20px] px-1.5 text-[10px] font-semibold",
                "bg-amber-500/15 text-amber-400"
              )}
            >
              {count}
            </Badge>
          )}
        </TabsTrigger>
      </TabsList>

      <TabsContent value="workflows" className="mt-4">
        {children}
      </TabsContent>

      <TabsContent value="queue" className="mt-4">
        <OperatorQueueList onReview={onReview} />
      </TabsContent>
    </Tabs>
  );
}
