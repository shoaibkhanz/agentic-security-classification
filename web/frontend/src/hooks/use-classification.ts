/**
 * React hook for managing the classification streaming lifecycle.
 *
 * REACT CONCEPT — Custom Hooks:
 * A custom hook is a function starting with "use" that encapsulates
 * stateful logic. Think of it like a Python class that manages state,
 * but using React's functional primitives. Components call this hook
 * and get back { status, result, classify, reset, ... } — all the
 * state and actions they need, without knowing HOW it works internally.
 *
 * ARCHITECTURE — SSE (Server-Sent Events):
 * The classification pipeline runs on the backend via pydantic-graph.
 * As each graph node executes, the backend yields SSE events. This hook
 * opens that SSE connection, receives events in real-time, and maintains
 * a state machine that components can react to.
 *
 * Flow: User clicks "Classify" → classify() called → POST /api/classify →
 *       backend streams SSE events → onmessage() dispatches to reducer →
 *       React re-renders components with new state.
 */
"use client";

import { useCallback, useMemo, useReducer, useRef } from "react";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import type {
  ClassificationResult,
  ConfidencePoint,
  ReasoningStep,
  StreamEvent,
  WorkflowQuestion,
  WorkflowStage,
} from "@/lib/types";

// =============================================================================
// State Machine — manages the lifecycle of a classification run
// =============================================================================

/**
 * The four states of a classification:
 * idle → streaming → complete (happy path)
 * idle → streaming → error   (something went wrong)
 *
 * REACT CONCEPT — Discriminated union:
 * This is like Python's Literal["idle", "streaming", "complete", "error"].
 * Components can do `if (status === "streaming")` and TypeScript knows
 * exactly which state we're in.
 */
type Status = "idle" | "streaming" | "complete" | "error";

/** All the state we track during a classification run. */
interface State {
  status: Status;
  events: StreamEvent[];            // All SSE events received so far
  result: ClassificationResult | null;  // Final result (null until complete)
  recordId: string | null;          // Backend-assigned ID after save
  error: string | null;             // Error message if something failed
  startTime: number;                // When classification started (for elapsed time)
}

/**
 * Actions that can be dispatched to the reducer.
 *
 * REACT CONCEPT — useReducer:
 * This is the React equivalent of Python's state machine pattern.
 * Instead of calling `self.status = "streaming"` directly, you dispatch
 * an action like `{ type: "START" }`, and the reducer function computes
 * the new state. This makes state transitions predictable and debuggable.
 *
 * TS CONCEPT — Discriminated union:
 * Each action has a `type` field that TypeScript uses to narrow the type.
 * In the reducer, `case "COMPLETE"` lets TypeScript know that `action.result`
 * exists (because only COMPLETE actions have a result field).
 */
type Action =
  | { type: "START" }
  | { type: "EVENT"; event: StreamEvent }
  | { type: "COMPLETE"; result: ClassificationResult; recordId: string }
  | { type: "SAVED"; recordId: string }
  | { type: "ERROR"; error: string }
  | { type: "RESET" };

/** Initial state — no classification running, no data. */
const initialState: State = {
  status: "idle",
  events: [],
  result: null,
  recordId: null,
  error: null,
  startTime: 0,
};

/**
 * Pure reducer function — given current state and an action, returns new state.
 *
 * REACT CONCEPT — Immutability:
 * We never mutate the old state. `{ ...state, events: [...state.events, action.event] }`
 * creates a NEW object with the event appended. This is how React knows to re-render.
 * In Python terms: it's like returning a new dataclass instance instead of modifying in place.
 */
function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "START":
      // Reset everything and begin streaming
      return { ...initialState, status: "streaming", startTime: Date.now() };
    case "EVENT":
      // Append new SSE event to the list (immutable append)
      return { ...state, events: [...state.events, action.event] };
    case "COMPLETE":
      // Classification finished successfully
      return {
        ...state,
        status: "complete",
        result: action.result,
        recordId: action.recordId,
      };
    case "SAVED":
      // Backend saved the result and gave us a record ID
      return { ...state, recordId: action.recordId };
    case "ERROR":
      return { ...state, status: "error", error: action.error };
    case "RESET":
      // Go back to idle — ready for a new classification
      return initialState;
    default:
      return state;
  }
}

// =============================================================================
// Hook
// =============================================================================

export function useClassification() {
  /**
   * REACT CONCEPT — useReducer:
   * Like useState but for complex state with multiple sub-values.
   * `dispatch` is how we send actions to the reducer.
   * Think of it as: state = reducer(state, action) on each dispatch.
   */
  const [state, dispatch] = useReducer(reducer, initialState);

  /**
   * REACT CONCEPT — useRef:
   * A ref holds a mutable value that persists across renders but
   * does NOT trigger re-renders when changed. Perfect for the
   * AbortController — we need to access it to cancel, but changing
   * it shouldn't cause the UI to update.
   * In Python terms: it's like an instance variable on `self`.
   */
  const abortRef = useRef<AbortController | null>(null);

  /**
   * Main classification function — opens SSE connection and processes events.
   *
   * REACT CONCEPT — useCallback:
   * Memoizes the function so it's the same reference across renders.
   * Without this, every render would create a new function, which could
   * cause child components to re-render unnecessarily.
   * Think of it as `@functools.lru_cache` but for function identity.
   *
   * The `[]` dependency array means "never recreate this function".
   */
  const classify = useCallback(
    async (description: string, additionalContext?: string, demo?: boolean) => {
      // Cancel any running classification before starting a new one
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      dispatch({ type: "START" });

      // These variables track state across SSE callbacks.
      // They're declared here (not in state) because we need them
      // in the synchronous onmessage/onclose callbacks.
      let latestResult: ClassificationResult | null = null;
      let latestRecordId: string = "";
      let hadError = false;

      try {
        /**
         * fetchEventSource — Third-party library for SSE over POST.
         *
         * The browser's native EventSource only supports GET requests.
         * We need POST (to send the description in the body), so we use
         * Microsoft's fetchEventSource library which supports any HTTP method.
         *
         * This is similar to Python's `httpx_sse.aconnect_sse()`.
         */
        await fetchEventSource("/api/classify", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            description,
            additional_context: additionalContext || null,
            demo: demo ?? false,
          }),
          signal: controller.signal,  // Allows cancellation via AbortController

          /**
           * Called for each SSE event from the backend.
           * This fires every time `streaming.py` yields a `_serialize_event()`.
           */
          onmessage(msg) {
            if (!msg.data) return;
            try {
              // Parse the JSON payload from the SSE event
              const event = JSON.parse(msg.data) as StreamEvent;
              dispatch({ type: "EVENT", event });

              // Capture specific event types for post-stream processing
              if (event.event_type === "result") {
                // `as unknown as` is a type assertion — we're telling TypeScript
                // "trust me, this data matches ClassificationResult".
                // In Python, this is like a cast() call.
                latestResult = event.data as unknown as ClassificationResult;
              }
              if (event.event_type === "error") {
                hadError = true;
                const errMsg = (event.data.error as string) || "Classification failed";
                dispatch({ type: "ERROR", error: errMsg });
              }
              if (event.event_type === "saved") {
                latestRecordId = (event.data as { record_id: string }).record_id;
                dispatch({ type: "SAVED", recordId: latestRecordId });
              }
            } catch {
              // Skip malformed SSE events (invalid JSON, etc.)
            }
          },

          /** Called when the SSE stream closes normally. */
          onclose() {
            if (latestResult) {
              dispatch({
                type: "COMPLETE",
                result: latestResult,
                recordId: latestRecordId,
              });
            } else if (!hadError) {
              // Stream ended without ever sending a "result" event
              dispatch({ type: "ERROR", error: "Stream ended without a result" });
            }
          },

          /** Called on connection errors. Throwing stops retry attempts. */
          onerror(err) {
            if (controller.signal.aborted) return;  // User cancelled — ignore
            dispatch({
              type: "ERROR",
              error: err instanceof Error ? err.message : "Connection error",
            });
            throw err; // Stop retrying (fetchEventSource retries by default)
          },

          // Keep the connection alive even when the browser tab is hidden
          openWhenHidden: true,
        });

        // fetchEventSource resolves (returns) when stream closes normally
        if (latestResult) {
          dispatch({
            type: "COMPLETE",
            result: latestResult,
            recordId: latestRecordId,
          });
        }
      } catch {
        // Catch AbortError (user cancelled) and network errors
        if (!controller.signal.aborted) {
          dispatch({ type: "ERROR", error: "Classification failed" });
        }
      }
    },
    []  // No dependencies — this function never needs to be recreated
  );

  /** Cancel a running classification and reset to idle. */
  const cancel = useCallback(() => {
    abortRef.current?.abort();
    dispatch({ type: "RESET" });
  }, []);

  /** Reset to idle state (also cancels if still running). */
  const reset = useCallback(() => {
    abortRef.current?.abort();
    dispatch({ type: "RESET" });
  }, []);

  // =============================================================================
  // Derived state — computed from raw events, recalculated when events change
  // =============================================================================

  /**
   * REACT CONCEPT — useMemo:
   * Memoizes computed values. Only recalculates when dependencies change.
   * Like Python's `@cached_property` but with explicit dependency tracking.
   * The `[state.events]` array says "recalculate when events change".
   */

  /** Which graph node is currently executing (last node_start event). */
  const currentNode = useMemo(() => {
    const nodeEvents = state.events.filter((e) => e.event_type === "node_start");
    return nodeEvents.length > 0
      ? nodeEvents[nodeEvents.length - 1].node_name
      : null;
  }, [state.events]);

  /** Confidence scores over time — feeds the Recharts line chart. */
  const confidenceHistory = useMemo((): ConfidencePoint[] => {
    return state.events
      .filter((e) => e.event_type === "confidence_update")
      .map((e) => ({
        step: (e.data.step as number) || 0,
        score: (e.data.score as number) || 0,
        category: (e.data.top_category as string) || "unknown",
      }));
  }, [state.events]);

  /**
   * All evidence found during the classification, enriched with
   * tool/data source metadata from the backend.
   */
  const evidenceList = useMemo(() => {
    return state.events
      .filter((e) => e.event_type === "evidence_found")
      .map((e) => ({
        finding: e.data.finding as string,
        sourceType: e.data.source_type as string,
        sourceDetail: e.data.source_detail as string,
        content: e.data.content as string,
        relevance: e.data.relevance as string,
        questionNumber: (e.data.question_number as number) || 0,
        toolName: (e.data.tool_name as string) || null,
        dataSource: (e.data.data_source as string) || null,
      }));
  }, [state.events]);

  /** Elapsed time from the last SSE event's timestamp. */
  const elapsedSeconds = useMemo(() => {
    if (state.status === "idle") return 0;
    const lastEvent = state.events[state.events.length - 1];
    return lastEvent?.timestamp ?? 0;
  }, [state.status, state.events]);

  /**
   * Transform raw SSE events into structured workflow questions.
   *
   * The agent doesn't follow a predetermined set of questions — it dynamically
   * decides what to investigate at each step. We reconstruct the investigation
   * timeline by:
   * 1. Taking each `node_start` event as a "question" (an investigation step)
   * 2. Matching it with its `confidence_update` (how much we learned)
   * 3. Matching it with its `evidence_found` (what we found)
   *
   * The matching uses `question_number` — a counter the backend includes
   * in each event to correlate related events.
   */
  const workflowQuestions = useMemo((): WorkflowQuestion[] => {
    // Separate events by type for efficient lookup
    const nodeStarts = state.events.filter((e) => e.event_type === "node_start");
    const confidenceEvents = state.events.filter((e) => e.event_type === "confidence_update");
    const evidenceEvents = state.events.filter((e) => e.event_type === "evidence_found");

    return nodeStarts.map((e, idx) => {
      const qNum = (e.data.question_number as number) || idx + 1;
      const isLast = idx === nodeStarts.length - 1;

      // Find the confidence update that matches this question number
      const matchingConfidence = confidenceEvents.find(
        (c) => (c.data.step as number) === qNum
      );

      // Find the evidence that matches this question number
      const matchingEvidence = evidenceEvents.find(
        (ev) => (ev.data.question_number as number) === qNum
      );

      return {
        questionNumber: qNum,
        stage: (e.data.stage as string) || "",
        stageName: (e.data.stage_name as string) || "",
        actionType: (e.data.action_type as string) || null,
        actionDetail: (e.data.action_detail as string) || null,
        toolName: (e.data.tool_name as string) || null,
        dataSource: (e.data.data_source as string) || null,
        expectedInfoGain: (e.data.expected_info_gain as string) || null,
        // All past questions are "complete", only the latest might be "active"
        status: state.status === "complete" || !isLast ? "complete" : "active",
        confidenceDelta: matchingConfidence
          ? (matchingConfidence.data.confidence_delta as number)
          : null,
        confidenceDeltaPct: matchingConfidence
          ? (matchingConfidence.data.confidence_delta_pct as number)
          : null,
        finding: matchingEvidence
          ? (matchingEvidence.data.finding as string)
          : null,
        currentCategory: (e.data.current_category as string) || null,
        timestamp: e.timestamp,
      };
    });
  }, [state.events, state.status]);

  /**
   * Group workflow questions by pipeline stage.
   *
   * TS CONCEPT — Map<K, V>:
   * Like Python's dict but with ordered iteration and better typing.
   * We use it here to group questions by stage while preserving order.
   *
   * The `!` after `stageMap.get(key)` is the non-null assertion operator.
   * It tells TypeScript "I just checked with .has(), so this won't be null".
   * Use sparingly — it bypasses type safety.
   */
  const workflowStages = useMemo((): WorkflowStage[] => {
    const stageMap = new Map<string, WorkflowStage>();

    for (const q of workflowQuestions) {
      const key = q.stage || "unknown";
      if (!stageMap.has(key)) {
        stageMap.set(key, {
          stage: q.stage,
          stageName: q.stageName,
          questions: [],
        });
      }
      stageMap.get(key)!.questions.push(q);
    }

    return Array.from(stageMap.values());
  }, [workflowQuestions]);

  /**
   * Live execution details for the "reasoning chain" UI.
   *
   * While streaming, we synthesize lightweight reasoning steps from the
   * workflow timeline so users can see investigation details immediately.
   * Once the backend sends the final result, we switch to canonical
   * `result.reasoning` from the model output.
   */
  const executionDetails = useMemo((): ReasoningStep[] => {
    if (state.result?.reasoning?.length) {
      return state.result.reasoning;
    }

    return workflowQuestions.map((question, idx) => ({
      step: question.questionNumber || idx + 1,
      source:
        question.dataSource ??
        question.toolName ??
        question.actionType ??
        question.stageName ??
        "workflow",
      inference:
        question.finding ??
        question.actionDetail ??
        question.expectedInfoGain ??
        "Step in progress...",
      evidence:
        question.finding ??
        question.expectedInfoGain ??
        question.actionDetail ??
        "Waiting for evidence...",
      confidence_delta: question.confidenceDelta ?? 0,
    }));
  }, [state.result, workflowQuestions]);

  // Return everything components need — state, derived data, and actions
  return {
    // Raw state
    status: state.status,
    events: state.events,
    result: state.result,
    recordId: state.recordId,
    error: state.error,
    // Derived (computed from events)
    currentNode,
    confidenceHistory,
    evidenceList,
    elapsedSeconds,
    workflowQuestions,
    workflowStages,
    executionDetails,
    // Actions (functions components can call)
    classify,
    cancel,
    reset,
  };
}
