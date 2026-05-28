import type { LiveNotes } from "../shared/home-types";
import styles from "./live-notes-panel.module.scss";

type LiveNotesPanelProps = {
  subtitle: string;
  liveNotes: LiveNotes | null;
  lastTurn: number | null;
};

export function LiveNotesPanel({ subtitle, liveNotes, lastTurn }: LiveNotesPanelProps) {
  const entries = liveNotes?.entries ?? [];
  const factCards = liveNotes?.fact_cards ?? [];

  return (
    <>
      <div className={styles.header}>
        <div className={styles.title}>Szybkie notatki</div>
        <div className={styles.subtitle}>{subtitle}</div>
      </div>

      <div className={styles.body}>
        {!liveNotes ? (
          <div className={styles.empty}>Po prawej pojawią się krótkie notatki 1-3 zdania na turę oraz żółte fiszki z rzeczami do sprawdzenia.</div>
        ) : (
          <>
            <div className={styles.section}>
              <div className={styles.sectionTitle}>Szybkie notatki</div>
              {entries.length > 0 ? (
                entries.map((entry, index) => (
                  <div key={`${entry.turn}-${entry.agent ?? "agent"}-${index}`} className={styles.noteCard}>
                    <div className={styles.kicker}>Tura {entry.turn} · {entry.agent ?? ""}</div>
                    <div className={styles.noteText}>{entry.note ?? ""}</div>
                  </div>
                ))
              ) : (
                <div className={styles.empty}>Brak notatek.</div>
              )}
            </div>

            <div className={styles.section}>
              <div className={`${styles.sectionTitle} ${styles.sectionTitleFacts}`}>Fiszki faktów do sprawdzenia</div>
              {factCards.length > 0 ? (
                <div className={styles.factGrid}>
                  {factCards.map((card, index) => (
                    <div key={`${card.turn}-${card.agent ?? "agent"}-${index}`} className={styles.factCard}>
                      <div className={styles.kicker}>Tura {card.turn} · {card.agent ?? ""}</div>
                      <div className={styles.factText}>{card.request ?? ""}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className={styles.empty}>Brak nowych fiszek faktów.</div>
              )}
            </div>

            {liveNotes.facts_error ? <div className={styles.meta}>Fiszki faktów pominięte w ostatniej turze: {liveNotes.facts_error}</div> : null}
            {lastTurn ? <div className={styles.meta}>Ostatnia aktualizacja: tura {lastTurn}</div> : null}
          </>
        )}
      </div>
    </>
  );
}