/**
 * Inline chat-like feedback input for submitting corrections or comments.
 *
 * This is a lightweight alternative to the full FeedbackSheet. It shows an
 * input field with a send button, and displays previously sent messages in
 * a simple list. Think of it as a mini chat widget embedded in the results area.
 *
 * REACT CONCEPT -- Controlled input + form submission:
 * The text input is "controlled" -- its value comes from React state (`message`),
 * and every keystroke updates that state via `onChange`. This is the standard
 * React pattern for form inputs.
 *
 * In Python, you'd read the input value when the form is submitted:
 *   message = input_field.get_value()
 * In React, the value is always in state, and you read it at submit time:
 *   const [message, setMessage] = useState("")
 *   // message is always current, read it in handleSend()
 *
 * REACT CONCEPT -- useRef for focus management:
 * `useRef` creates a mutable reference that persists across re-renders.
 * We use it to hold a reference to the input DOM element so we can call
 * `.focus()` on it after sending a message. This is one of the few cases
 * where React code directly touches the DOM.
 *
 * Python analogy: it's like keeping a `self._input_widget` reference in a
 * GUI framework (tkinter, Qt) so you can programmatically focus it.
 *
 * TS CONCEPT -- `React.KeyboardEvent`:
 * TypeScript provides typed event objects for all DOM events. This gives you
 * autocomplete for properties like `event.key`, `event.ctrlKey`, etc.
 * Python's tkinter equivalent: `event.keysym` in a `<Key>` binding.
 */
"use client";

import { useState, useRef } from "react";
import { Send, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { submitChat } from "@/lib/api";
import { toast } from "sonner";

interface InlineFeedbackProps {
  /** The classification record ID for the API call */
  recordId: string;
  /** Placeholder text for the input field */
  placeholder?: string;
  /** Optional extra CSS classes */
  className?: string;
}

/**
 * TS CONCEPT -- Interface for internal data:
 * `SentMessage` is a private type (not exported) used only within this file.
 * It tracks the messages the user has sent, similar to a dataclass in Python:
 *   @dataclass
 *   class SentMessage:
 *       text: str
 *       timestamp: datetime
 */
interface SentMessage {
  text: string;
  timestamp: Date;
}

export function InlineFeedback({
  recordId,
  placeholder = "Describe what should be different...",
  className,
}: InlineFeedbackProps) {
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  /**
   * REACT CONCEPT -- useState with array type:
   * `useState<SentMessage[]>([])` initializes state as an empty array.
   * The generic `<SentMessage[]>` tells TypeScript what the array holds.
   * Python equivalent: `self.sent_messages: list[SentMessage] = []`.
   */
  const [sentMessages, setSentMessages] = useState<SentMessage[]>([]);

  /**
   * REACT CONCEPT -- useRef<HTMLInputElement>:
   * `useRef` returns a mutable object `{ current: ... }` that persists across
   * re-renders. Initially `null`, it gets assigned to the actual DOM element
   * when the input renders (via the `ref` prop on the <input> element below).
   *
   * The generic `<HTMLInputElement>` tells TypeScript what DOM element type
   * to expect, so `inputRef.current?.focus()` is properly typed.
   */
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSend = async () => {
    const trimmed = message.trim();
    if (!trimmed) return;

    setSending(true);
    try {
      await submitChat(recordId, trimmed);

      /**
       * REACT CONCEPT -- Immutable state updates:
       * React requires new array/object references for state updates to
       * trigger re-renders. We use the spread operator `[...prev, newItem]`
       * to create a new array with the new message appended.
       *
       * WRONG: `sentMessages.push(newMsg)` -- mutates in place, React won't re-render.
       * RIGHT: `setSentMessages(prev => [...prev, newMsg])` -- new array reference.
       *
       * Python equivalent of spread: `[*old_list, new_item]`.
       *
       * The function form `prev => ...` is called "functional update". It receives
       * the current state value as an argument. This is safer than reading
       * `sentMessages` directly because React batches state updates and the
       * closure might have a stale value.
       */
      setSentMessages((prev) => [
        ...prev,
        { text: trimmed, timestamp: new Date() },
      ]);
      setMessage("");

      toast.success("Feedback sent");

      /**
       * Re-focus the input after sending so the user can immediately type
       * another message without clicking. `?.` handles the case where the
       * ref isn't attached yet (shouldn't happen, but defensive coding).
       */
      inputRef.current?.focus();
    } catch {
      toast.error("Failed to send feedback. Please try again.");
    } finally {
      setSending(false);
    }
  };

  /**
   * Handle Enter key press to submit.
   * We check for Enter without Shift (Shift+Enter would be for newlines
   * in a textarea, but we're using a single-line input here).
   */
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      /**
       * TS CONCEPT -- Event.preventDefault():
       * Prevents the browser's default behavior for this event.
       * For Enter in an input, the default would submit a surrounding <form>.
       * We handle submission ourselves via handleSend().
       */
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={cn("space-y-3", className)}>
      {/* Previously sent messages */}
      {sentMessages.length > 0 && (
        <div className="space-y-2">
          {sentMessages.map((msg, i) => (
            /**
             * REACT CONCEPT -- Key prop for lists:
             * Each rendered list item needs a unique `key`. We use the index `i`
             * here because messages are append-only (never reordered or deleted).
             * For dynamic lists, a stable ID is preferred.
             */
            <div
              key={i}
              className="flex justify-end"
            >
              <div className="max-w-[85%] rounded-lg bg-primary/10 px-3 py-2 text-xs text-primary">
                {msg.text}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Input row: text field + send button */}
      <div className="flex items-center gap-2">
        {/*
         * REACT CONCEPT -- ref prop:
         * `ref={inputRef}` connects the `useRef` hook to this DOM element.
         * After rendering, `inputRef.current` points to this <input> element,
         * letting us call `.focus()` on it programmatically.
         *
         * Note: we use a plain <input> instead of shadcn/ui's Input component
         * for simplicity. In a production app, you might use the shadcn Input
         * for consistent styling, but a plain input works fine here.
         */}
        <input
          ref={inputRef}
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={sending}
          className={cn(
            "flex-1 rounded-md border border-input bg-transparent px-3 py-2 text-sm",
            "placeholder:text-muted-foreground",
            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
            "disabled:cursor-not-allowed disabled:opacity-50"
          )}
        />
        <Button
          size="sm"
          onClick={handleSend}
          disabled={!message.trim() || sending}
          className="shrink-0"
        >
          {sending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </Button>
      </div>

      {/* Hint text */}
      <p className="text-[10px] text-muted-foreground">
        Press Enter to send
      </p>
    </div>
  );
}
