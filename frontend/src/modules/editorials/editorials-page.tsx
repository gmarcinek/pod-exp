import { buildAppPath } from "../../bootstrap/backend-config";
import type { EditorialListItem } from "../../lib/types/bootstrap";
import styles from "./editorials-page.module.scss";

type EditorialsPageProps = {
  editorials: EditorialListItem[];
};

function formatTimestamp(timestamp: string) {
  const date = timestamp.slice(0, 10);
  const time = timestamp.length > 15 ? timestamp.slice(11, 16) : "";

  return `${date}  ${time} UTC`;
}

export function EditorialsPage({ editorials }: EditorialsPageProps) {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.logo}>POD-EXP</div>
        <div className={styles.subtitle}>Archiwum sesji redakcyjnych</div>
        <a href={buildAppPath("/editorial")} className={styles.backLink}>
          ← Nowa sesja redakcyjna
        </a>
      </header>

      <main className={styles.content}>
        <h1 className={styles.title}>Zapisane editoriale</h1>
        <p className={styles.pageSubtitle}>
          Lista zapisanych przebiegów modułu redakcyjnego. Na razie bez widoku
          szczegółowego, ale z pełnym identyfikatorem, modelem i liczbą
          iteracji.
        </p>

        {editorials.length === 0 ? (
          <div className={styles.emptyState}>
            <div className={styles.emptyIcon}>📝</div>
            <p>
              Brak zapisanych editoriali. Uruchom pierwszą sesję w module
              redakcyjnym.
            </p>
          </div>
        ) : (
          <div className={styles.list}>
            {editorials.map((editorial) => (
              <article key={editorial.id} className={styles.card}>
                <div className={styles.cardTop}>
                  <span className={styles.badge}>EDITORIAL</span>
                  <span>{editorial.id}</span>
                  <div className={styles.meta}>
                    {formatTimestamp(editorial.timestamp)}
                  </div>
                </div>
                <div className={styles.topic}>
                  {editorial.topic || "Bez tytułu"}
                </div>
                {editorial.snippet ? (
                  <div className={styles.snippet}>{editorial.snippet}</div>
                ) : null}
                <div className={styles.footer}>
                  <span>🤖 {editorial.model || "brak modelu"}</span>
                  <span>🔌 {editorial.provider || "brak providera"}</span>
                  <span>🔁 {editorial.cycles_completed} iteracji</span>
                </div>
              </article>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
