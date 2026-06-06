import { useState } from "react";
import { buildApiPath } from "../../bootstrap/backend-config";
import type { AgentSummary } from "../../lib/types/bootstrap";
import styles from "./agent-quiz.module.scss";

type QuizProps = {
  onClose: () => void;
  onCreated: (agent: AgentSummary) => void;
};

type QuizData = {
  designation: string;
  short_name: string;
  filename: string;
  narrative_identity: string;
  world_assumption: string;
  knowledge_sources: string;
  truth_criterion: string;
  rejected_defaults: string;
  temperament: string[];
  federation_description: string;
};

const TEMPERAMENT_SUGGESTIONS = [
  "racjonalny",
  "empiryczny",
  "sceptyczny",
  "analityczny",
  "syntetyczny",
  "spokojny",
  "surowy",
  "ciepły",
  "ironiczny",
  "poetycki",
  "precyzyjny",
  "intuicyjny",
  "abstrakcyjny",
  "konkretny",
  "pragmatyczny",
  "idealistyczny",
  "materialistyczny",
  "duchowy",
  "rewolucyjny",
  "konserwatywny",
  "krytyczny",
  "konstruktywny",
  "metodyczny",
  "chaotyczny",
  "emocjonalny",
  "zdystansowany",
];

const STEPS = [
  { id: "identity", label: "Krok 1/5", title: "Tożsamość" },
  { id: "narrative", label: "Krok 2/5", title: "Kim jesteś?" },
  { id: "worldview", label: "Krok 3/5", title: "Świat i wiedza" },
  { id: "character", label: "Krok 4/5", title: "Charakter i rola" },
  { id: "review", label: "Krok 5/5", title: "Przegląd" },
];

function slugify(text: string): string {
  return (
    text
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "nowy-agent"
  );
}

export function AgentQuiz({ onClose, onCreated }: QuizProps) {
  const [step, setStep] = useState(0);
  const [quiz, setQuiz] = useState<QuizData>({
    designation: "",
    short_name: "",
    filename: "",
    narrative_identity: "",
    world_assumption: "",
    knowledge_sources: "",
    truth_criterion: "",
    rejected_defaults: "",
    temperament: [],
    federation_description: "",
  });
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  function set<K extends keyof QuizData>(key: K, value: QuizData[K]) {
    setQuiz((prev) => ({ ...prev, [key]: value }));
  }

  function handleDesignationChange(val: string) {
    set("designation", val);
    if (
      !quiz.short_name ||
      quiz.short_name === slugify(quiz.designation).toUpperCase().slice(0, 12)
    ) {
      set(
        "short_name",
        val
          .toUpperCase()
          .replace(/[^A-Z0-9-]/g, "")
          .slice(0, 12),
      );
    }
    if (!quiz.filename || quiz.filename === slugify(quiz.designation)) {
      set("filename", slugify(val));
    }
  }

  function toggleTemperament(tag: string) {
    set(
      "temperament",
      quiz.temperament.includes(tag)
        ? quiz.temperament.filter((t) => t !== tag)
        : [...quiz.temperament, tag],
    );
  }

  async function generate() {
    setGenerating(true);
    setError(null);
    try {
      const res = await fetch(buildApiPath("/api/agents/create"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...quiz,
          temperament: quiz.temperament.join(", "),
        }),
      });
      const json = (await res.json()) as {
        error?: string;
        agent?: AgentSummary;
        name?: string;
      };
      if (!res.ok) throw new Error(json.error ?? `HTTP ${res.status}`);
      setDone(true);
      if (json.agent) onCreated(json.agent);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setGenerating(false);
    }
  }

  const canNext0 =
    quiz.designation.trim().length > 0 && quiz.filename.trim().length > 0;
  const canNext1 = quiz.narrative_identity.trim().length > 20;
  const canNext2 = quiz.world_assumption.trim().length > 0;
  const canNext3 = quiz.federation_description.trim().length > 0;
  const canNextMap = [canNext0, canNext1, canNext2, canNext3, true];

  return (
    <div
      className={styles.overlay}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className={styles.dialog}>
        <div className={styles.dialogHeader}>
          <span className={styles.dialogTitle}>Nowy agent epistemiczny</span>
          <button type="button" className={styles.closeBtn} onClick={onClose}>
            ×
          </button>
        </div>

        {!generating && !done && (
          <div className={styles.progress}>
            {STEPS.map((s, i) => (
              <div
                key={s.id}
                className={`${styles.progressDot} ${i < step ? styles.progressDotDone : ""} ${i === step ? styles.progressDotActive : ""}`}
              />
            ))}
          </div>
        )}

        <div className={styles.body}>
          {done ? (
            <div className={styles.generatingBlock}>
              <div className={styles.successIcon}>✅</div>
              <div className={styles.successTitle}>Agent gotowy!</div>
              <div className={styles.successDesc}>
                Profil <strong>{quiz.designation}</strong> został wygenerowany i
                zapisany.
                <br />
                Wróć do listy, żeby go zobaczyć.
              </div>
            </div>
          ) : generating ? (
            <div className={styles.generatingBlock}>
              <div className={styles.spinner} />
              <div className={styles.generatingText}>
                Generuję pełny profil epistemiczny…
              </div>
            </div>
          ) : step === 0 ? (
            <>
              <div className={styles.stepLabel}>{STEPS[0].label}</div>
              <div className={styles.stepTitle}>{STEPS[0].title}</div>
              <p className={styles.stepDesc}>
                Kogo lub co reprezentuje ten agent? Podaj postać, nurt
                filozoficzny, styl myślenia.
              </p>
              <div className={styles.field}>
                <label className={styles.label}>Kogo reprezentuje? *</label>
                <input
                  className={styles.input}
                  placeholder="np. Kartezjusz, marksizm, radykalny empirysta..."
                  value={quiz.designation}
                  onChange={(e) => handleDesignationChange(e.target.value)}
                />
              </div>
              <div className={styles.field}>
                <label className={styles.label}>
                  Skrócona nazwa (CAPS, max 12 znaków)
                </label>
                <input
                  className={styles.input}
                  placeholder="np. KARTEZJUSZ"
                  value={quiz.short_name}
                  maxLength={12}
                  onChange={(e) =>
                    set("short_name", e.target.value.toUpperCase())
                  }
                />
              </div>
              <div className={styles.field}>
                <label className={styles.label}>Nazwa pliku (slug)</label>
                <input
                  className={styles.input}
                  placeholder="np. kartezjusz"
                  value={quiz.filename}
                  onChange={(e) =>
                    set(
                      "filename",
                      slugify(e.target.value) || e.target.value.toLowerCase(),
                    )
                  }
                />
              </div>
            </>
          ) : step === 1 ? (
            <>
              <div className={styles.stepLabel}>{STEPS[1].label}</div>
              <div className={styles.stepTitle}>{STEPS[1].title}</div>
              <p className={styles.stepDesc}>
                Napisz w pierwszej osobie: kim jesteś, skąd patrzysz, co napędza
                twoje myślenie?
              </p>
              <div className={styles.field}>
                <label className={styles.label}>Tożsamość narracyjna *</label>
                <textarea
                  className={styles.textarea}
                  rows={5}
                  placeholder="Jestem agentem poznawczym inspirowanym..."
                  value={quiz.narrative_identity}
                  onChange={(e) => set("narrative_identity", e.target.value)}
                />
              </div>
            </>
          ) : step === 2 ? (
            <>
              <div className={styles.stepLabel}>{STEPS[2].label}</div>
              <div className={styles.stepTitle}>{STEPS[2].title}</div>
              <p className={styles.stepDesc}>
                Jak rozumiesz rzeczywistość i w jaki sposób zdobywasz wiedzę?
              </p>
              <div className={styles.field}>
                <label className={styles.label}>Założenie o świecie *</label>
                <textarea
                  className={styles.textarea}
                  rows={3}
                  placeholder="Świat jest/ma/działa..."
                  value={quiz.world_assumption}
                  onChange={(e) => set("world_assumption", e.target.value)}
                />
              </div>
              <div className={styles.field}>
                <label className={styles.label}>
                  Źródła wiedzy (przecinek lub enter)
                </label>
                <textarea
                  className={styles.textarea}
                  rows={3}
                  placeholder="np. rozum, doświadczenie zmysłowe, intuicja..."
                  value={quiz.knowledge_sources}
                  onChange={(e) => set("knowledge_sources", e.target.value)}
                />
              </div>
              <div className={styles.field}>
                <label className={styles.label}>Kryterium prawdy</label>
                <textarea
                  className={styles.textarea}
                  rows={2}
                  placeholder="Prawdziwe jest to, co..."
                  value={quiz.truth_criterion}
                  onChange={(e) => set("truth_criterion", e.target.value)}
                />
              </div>
            </>
          ) : step === 3 ? (
            <>
              <div className={styles.stepLabel}>{STEPS[3].label}</div>
              <div className={styles.stepTitle}>{STEPS[3].title}</div>
              <div className={styles.field}>
                <label className={styles.label}>
                  Temperament (zaznacz lub dopisz)
                </label>
                <div className={styles.chips}>
                  {TEMPERAMENT_SUGGESTIONS.map((tag) => (
                    <button
                      key={tag}
                      type="button"
                      className={`${styles.chip} ${quiz.temperament.includes(tag) ? styles.chipActive : ""}`}
                      onClick={() => toggleTemperament(tag)}
                    >
                      {tag}
                    </button>
                  ))}
                </div>
                <input
                  className={styles.input}
                  style={{ marginTop: 8 }}
                  placeholder="Dodaj własne cechy (przecinek)"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === ",") {
                      e.preventDefault();
                      const val = e.currentTarget.value.trim();
                      if (val && !quiz.temperament.includes(val)) {
                        set("temperament", [...quiz.temperament, val]);
                        e.currentTarget.value = "";
                      }
                    }
                  }}
                />
              </div>
              <div className={styles.field}>
                <label className={styles.label}>
                  Co odrzucasz jako domyślne założenia?
                </label>
                <textarea
                  className={styles.textarea}
                  rows={2}
                  placeholder="np. materializm redukcyjny, relatywizm moralny..."
                  value={quiz.rejected_defaults}
                  onChange={(e) => set("rejected_defaults", e.target.value)}
                />
              </div>
              <div className={styles.field}>
                <label className={styles.label}>
                  Kiedy aktywować w debacie wieloagentowej? *
                </label>
                <textarea
                  className={styles.textarea}
                  rows={2}
                  placeholder="Aktywuj gdy rozmowa..."
                  value={quiz.federation_description}
                  onChange={(e) =>
                    set("federation_description", e.target.value)
                  }
                />
              </div>
            </>
          ) : (
            <>
              <div className={styles.stepLabel}>{STEPS[4].label}</div>
              <div className={styles.stepTitle}>Przegląd i generowanie</div>
              <p className={styles.stepDesc}>
                GPT-5.5 wygeneruje pełny profil epistemiczny na podstawie twoich
                odpowiedzi.
              </p>
              {[
                ["Kogo reprezentuje", quiz.designation],
                ["Skrót", quiz.short_name],
                ["Plik", quiz.filename + ".json"],
                ["Tożsamość", quiz.narrative_identity],
                ["Świat", quiz.world_assumption],
                ["Wiedza", quiz.knowledge_sources],
                ["Prawda", quiz.truth_criterion],
                ["Odrzuca", quiz.rejected_defaults],
                ["Temperament", quiz.temperament.join(", ")],
                ["Federacja", quiz.federation_description],
              ]
                .filter(([, v]) => v)
                .map(([label, value]) => (
                  <div key={label} className={styles.reviewItem}>
                    <span className={styles.reviewLabel}>{label}</span>
                    <span className={styles.reviewValue}>{value}</span>
                  </div>
                ))}
              {error && <div className={styles.errorMsg}>⚠ {error}</div>}
            </>
          )}
        </div>

        {!generating && !done && (
          <div className={styles.footer}>
            {step > 0 && (
              <button
                type="button"
                className={styles.backStepBtn}
                onClick={() => setStep(step - 1)}
              >
                ← Wróć
              </button>
            )}
            {step < STEPS.length - 1 ? (
              <button
                type="button"
                className={styles.nextBtn}
                disabled={!canNextMap[step]}
                onClick={() => setStep(step + 1)}
              >
                Dalej →
              </button>
            ) : (
              <button
                type="button"
                className={styles.nextBtn}
                disabled={!canNext0}
                onClick={() => void generate()}
              >
                Generuj profil →
              </button>
            )}
          </div>
        )}

        {done && (
          <div className={styles.footer}>
            <button type="button" className={styles.nextBtn} onClick={onClose}>
              Zamknij
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
