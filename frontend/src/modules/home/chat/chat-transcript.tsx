import { MarkdownContent } from "../../../components/markdown/markdown-content";
import type { ChatTranscriptEntry } from "../shared/home-types";
import styles from "./chat-transcript.module.scss";

type ChatTranscriptProps = {
  messages: ChatTranscriptEntry[];
  busy: boolean;
};

function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function ChatTranscript({ messages, busy }: ChatTranscriptProps) {
  if (messages.length === 0) {
    return (
      <div className={styles.empty}>
        <div className={styles.emptyTitle}>POD-EXP</div>
        <div className={styles.emptySubtitle}>Wybierz agenta i zadaj pytanie</div>
      </div>
    );
  }

  return (
    <>
      {messages.map((message) => (
        <div key={message.id} className={`${styles.message} ${styles[message.role]}`}>
          <div className={styles.messageRole}>
            {message.role === "user" ? "Ty" : message.role === "assistant" ? "Agent" : message.role === "tool" ? "Tool" : "Błąd"}
          </div>
          <div className={styles.messageBubble}>
            {message.role === "assistant" ? <MarkdownContent content={message.content} /> : null}
            {message.role === "tool" ? (
              <>
                {message.toolName ? <div className={styles.toolChip}>⚙ {message.toolName}</div> : null}
                <pre>{message.content}</pre>
              </>
            ) : null}
            {message.role === "user" || message.role === "error" ? (
              <p dangerouslySetInnerHTML={{ __html: escapeHtml(message.content).replace(/\n/g, "<br>") }} />
            ) : null}
          </div>
        </div>
      ))}

      {busy ? (
        <div className={styles.thinking}>
          <div className={styles.dot} />
          <div className={styles.dot} />
          <div className={styles.dot} />
          <span className={styles.thinkingLabel}>myśli…</span>
        </div>
      ) : null}
    </>
  );
}