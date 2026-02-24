"use client";

import Link from "next/link";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { HistoryTable } from "@/components/history-table";
import { useHistory } from "@/hooks/use-history";

export default function HistoryPage() {
  const { records, loading, error, refresh, remove } = useHistory();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" asChild>
            <Link href="/" className="flex items-center gap-1.5">
              <ArrowLeft className="h-4 w-4" />
              Back
            </Link>
          </Button>
          <h1 className="text-2xl font-bold tracking-tight">
            Classification History
          </h1>
        </div>
        <Button variant="outline" size="sm" onClick={refresh} disabled={loading}>
          <RefreshCw className={`mr-1.5 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {loading && records.length === 0 ? (
        <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
          Loading history...
        </div>
      ) : (
        <HistoryTable records={records} onDelete={remove} />
      )}
    </div>
  );
}
