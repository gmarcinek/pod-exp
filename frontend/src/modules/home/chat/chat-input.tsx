import type { KeyboardEvent, RefObject } from "react";
import styles from "./chat-input.module.scss";

type ChatInputProps = {
  value: string;
  busy: boolean;
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  onChange: (value: string) => void;
  onSend: () => void;
  onResize: () => void;
};

export function ChatInput({ value, busy, textareaRef, onChange, onSend, onResize }: ChatInputProps) {
  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSend();
    }
  }

  return (
    <div className={styles.inputArea}>
      <div className={styles.inputRow}>
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          placeholder="Napisz wiadomość…"
          onChange={(event) => onChange(event.target.value)}
          onInput={onResize}
          onKeyDown={handleKeyDown}
        />
        <button type="button" className={styles.sendButton} title="Wyślij" disabled={busy} onClick={onSend}>
          ↑
        </button>
      </div>
      <div className={styles.hint}>Enter — wyślij · Shift+Enter — nowa linia</div>
    </div>
  );
}