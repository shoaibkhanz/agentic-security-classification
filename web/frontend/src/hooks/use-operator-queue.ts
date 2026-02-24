/**
 * React hook for managing the operator review queue.
 *
 * When the classification agent isn't fully confident (< 100%), the result
 * goes into an operator queue for human review. This hook fetches and
 * manages that queue.
 *
 * REACT CONCEPT — Simple data-fetching hook:
 * This is a common pattern: useState for data + loading, useEffect to fetch
 * on mount, useCallback for a refresh function. It's the React equivalent
 * of a Python class with `__init__` that kicks off an async fetch.
 *
 * For production apps, you'd typically use a library like SWR or TanStack Query
 * instead of hand-rolling this. But for learning, it's clearer to see the pieces.
 */
"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchOperatorQueue } from "@/lib/api";
import type { ClassificationRecord } from "@/lib/types";

export function useOperatorQueue() {
  /**
   * REACT CONCEPT — useState with generics:
   * `useState<ClassificationRecord[]>([])` is like:
   *   self.queue: list[ClassificationRecord] = []
   * The generic `<ClassificationRecord[]>` tells TypeScript the type.
   * `setQueue` is the only way to update it (triggers a re-render).
   */
  const [queue, setQueue] = useState<ClassificationRecord[]>([]);
  const [loading, setLoading] = useState(true);

  /**
   * Fetch the operator queue from the backend.
   * Wrapped in useCallback so child components can call it
   * without causing infinite re-render loops.
   */
  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchOperatorQueue();
      setQueue(data);
    } catch {
      // On error, show empty queue rather than crashing
      setQueue([]);
    } finally {
      // `finally` runs whether the try succeeded or caught an error
      // — like Python's `finally` block
      setLoading(false);
    }
  }, []);

  /**
   * REACT CONCEPT — useEffect:
   * Runs side effects after render. The `[refresh]` dependency array
   * means "run this when `refresh` changes" (which is never, since
   * refresh is memoized with useCallback).
   *
   * This is roughly equivalent to calling an async method in Python's
   * `__init__` — it runs once when the component first mounts.
   */
  useEffect(() => {
    refresh();
  }, [refresh]);

  return {
    queue,              // The list of classifications needing review
    count: queue.length, // Convenience — used for badge counts like "Queue (3)"
    loading,            // True while fetching — show a spinner
    refresh,            // Call this to re-fetch (e.g., after submitting a review)
  };
}
