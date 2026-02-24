"use client";

import { useCallback, useEffect, useState } from "react";
import { deleteHistoryRecord, fetchHistory } from "@/lib/api";
import type { ClassificationRecord } from "@/lib/types";

export function useHistory() {
  const [records, setRecords] = useState<ClassificationRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchHistory();
      setRecords(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load history");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const remove = useCallback(
    async (id: string) => {
      await deleteHistoryRecord(id);
      setRecords((prev) => prev.filter((r) => r.id !== id));
    },
    []
  );

  return { records, loading, error, refresh, remove };
}
