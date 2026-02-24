"use client";

import { useCallback, useState } from "react";
import { motion } from "framer-motion";
import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ClassificationInput } from "@/components/classification-input";
import { LandingTabs } from "@/components/landing-tabs";
import { DetailHeaderBar } from "@/components/detail-header-bar";
import { ClassificationDetail } from "@/components/classification-detail";
import { useClassification } from "@/hooks/use-classification";
import type { ClassificationRecord } from "@/lib/types";

const DEMO_MODE = true;

export default function HomePage() {
  const {
    status,
    result,
    recordId,
    error,
    confidenceHistory,
    workflowStages,
    evidenceList,
    executionDetails,
    elapsedSeconds,
    classify,
    cancel,
    reset,
  } = useClassification();

  const [inputValue, setInputValue] = useState("");
  const [activeTab, setActiveTab] = useState<"workflows" | "queue">("workflows");

  const handleSubmit = useCallback(
    (description: string) => {
      setInputValue(description);
      setActiveTab("workflows");
      classify(description, undefined, DEMO_MODE);
    },
    [classify]
  );

  const handleReview = useCallback(
    (record: ClassificationRecord) => {
      setInputValue(record.description);
      setActiveTab("workflows");
      classify(record.description, undefined, DEMO_MODE);
    },
    [classify]
  );

  const handleReset = useCallback(() => {
    reset();
    setInputValue("");
  }, [reset]);

  const isIdle = status === "idle";
  const isStreaming = status === "streaming";
  const isComplete = status === "complete";
  const isError = status === "error";

  return (
    <div className="space-y-6">
      <div className="space-y-2 text-center">
        <h1 className="text-3xl font-bold tracking-tight">
          Automated Asset Classification
        </h1>
        <p className="text-muted-foreground max-w-2xl mx-auto">
          Classify private securities with auditable reasoning, live evidence tracking,
          and operator review controls.
        </p>
      </div>

      <div className="h-px w-full bg-border/70" />

      <LandingTabs
        onReview={handleReview}
        activeTab={activeTab}
        onTabChange={(value) => setActiveTab(value)}
      >
        <div className="space-y-6">
          <ClassificationInput
            onSubmit={handleSubmit}
            onCancel={cancel}
            isStreaming={isStreaming}
            defaultValue={inputValue}
          />

          {!isIdle && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-6"
            >
              <DetailHeaderBar
                description={inputValue}
                result={result}
                elapsedSeconds={elapsedSeconds}
                onReset={handleReset}
                resetLabel="Clear Run"
              />

              <ClassificationDetail
                workflowStages={workflowStages}
                result={result}
                recordId={recordId}
                evidenceList={evidenceList}
                executionDetails={executionDetails}
                confidenceHistory={confidenceHistory}
                status={status}
                elapsedSeconds={elapsedSeconds}
              />

              {isComplete && (
                <div className="flex justify-center">
                  <Button variant="outline" onClick={handleReset}>
                    <RotateCcw className="mr-1.5 h-4 w-4" />
                    Classify Another
                  </Button>
                </div>
              )}

              {isError && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm"
                >
                  <p className="font-medium text-destructive">
                    Classification failed
                  </p>
                  <p className="mt-1 text-muted-foreground">{error}</p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-3"
                    onClick={handleReset}
                  >
                    Try Again
                  </Button>
                </motion.div>
              )}
            </motion.div>
          )}
        </div>
      </LandingTabs>
    </div>
  );
}
