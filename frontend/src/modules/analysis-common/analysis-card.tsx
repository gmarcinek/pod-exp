type AnalysisCardProps = {
  data: unknown;
  agent1: string;
  agent2: string;
};

type AnalysisMap = Record<string, unknown>;

function isRecord(value: unknown): value is AnalysisMap {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readRecord(value: unknown): AnalysisMap | null {
  return isRecord(value) ? value : null;
}

function readText(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function readNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function readTextList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((entry): entry is string => typeof entry === "string" && entry.length > 0) : [];
}

function readRecordList(value: unknown): AnalysisMap[] {
  return Array.isArray(value) ? value.filter(isRecord) : [];
}

function readNumberList(value: unknown): number[] {
  return Array.isArray(value) ? value.map(readNumber).filter((entry): entry is number => entry !== null) : [];
}

function ReferenceList({ refs }: { refs: number[] }) {
  if (refs.length === 0) {
    return null;
  }

  return (
    <>
      {refs.map((ref) => (
        <span key={ref} className="ana-xref">
          #{ref}
        </span>
      ))}
    </>
  );
}

function Section({ title, children, className = "ana-sec" }: { title: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <div className={className}>
      <div className="ana-sec-title">{title}</div>
      {children}
    </div>
  );
}

function PillList({ items }: { items: string[] }) {
  if (items.length === 0) {
    return null;
  }

  return (
    <div>
      {items.map((item) => (
        <span key={item} className="ana-pill">
          {item}
        </span>
      ))}
    </div>
  );
}

function BulletList({ items }: { items: string[] }) {
  if (items.length === 0) {
    return null;
  }

  return (
    <ul className="ana-ul">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

export function AnalysisCard({ data, agent1, agent2 }: AnalysisCardProps) {
  const root = readRecord(data);

  if (!root) {
    return null;
  }

  const cartographerPosition = readText(root.cartographer_position);
  const interactionPattern = readRecord(root.interaction_pattern);
  const modeObservation = readRecord(root.mode_observation);
  const firstAgent = readRecord(root.agent_1);
  const secondAgent = readRecord(root.agent_2);
  const collisionPoints = readRecordList(root.collision_points);
  const interactionPatterns = readRecord(root.interaction_patterns) ?? readRecord(root.attack_patterns);
  const positionAsymmetries = readRecord(root.position_asymmetries) ?? readRecord(root.defense_asymmetries);
  const translationFailures = readRecordList(root.translation_failures);
  const maxTensionExchange = readRecord(root.max_tension_exchange);
  const unspoken = readTextList(root.unspoken);
  const relationStatus = readRecord(root.relation_status) ?? readRecord(root.spore_status);
  const trajectory = readRecord(root.trajectory);

  return (
    <div className="analysis-card">
      {cartographerPosition ? <p className="ana-cart-pos">📍 {cartographerPosition}</p> : null}

      {interactionPattern ? (
        <Section title="Układ relacji">
          <span className="ana-spore-type">{readText(interactionPattern.type, "—")}</span>
          <p>{readText(interactionPattern.rationale)}</p>
          {readNumberList(interactionPattern.exchange_refs).length > 0 ? (
            <div className="muted">
              <ReferenceList refs={readNumberList(interactionPattern.exchange_refs)} />
            </div>
          ) : null}
        </Section>
      ) : null}

      {modeObservation ? (
        <Section title="Tryb a przebieg">
          <span className="ana-spore-type">{readText(modeObservation.fit, "—")}</span>
          <p>Tryb zadany: {readText(modeObservation.declared_mode, "—")}</p>
          <p className="muted">{readText(modeObservation.rationale)}</p>
        </Section>
      ) : null}

      {firstAgent || secondAgent ? (
        <div className="ana-cols">
          {[
            { key: "agent-1", name: agent1, tone: "s1", data: firstAgent },
            { key: "agent-2", name: agent2, tone: "s2", data: secondAgent },
          ].map(({ key, name, tone, data: agent }) => {
            if (!agent) {
              return null;
            }

            const declaredFoundations = readTextList(agent.declared_foundations);
            const undeclaredFoundations = readTextList(agent.undeclared_foundations);

            return (
              <div key={key} className={`ana-agent-card ${tone}`}>
                <div className="ana-agent-title">{name}</div>
                {readText(agent.core_position) ? <p className="ana-core">{readText(agent.core_position)}</p> : null}
                <PillList items={readTextList(agent.attractors)} />
                {declaredFoundations.length > 0 ? (
                  <>
                    <div className="ana-lbl">Deklarowane:</div>
                    <BulletList items={declaredFoundations} />
                  </>
                ) : null}
                {undeclaredFoundations.length > 0 ? (
                  <>
                    <div className="ana-lbl muted">Milczące:</div>
                    <BulletList items={undeclaredFoundations} />
                  </>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : null}

      {collisionPoints.length > 0 ? (
        <Section title="Punkty styku i rozbieżności">
          {collisionPoints.map((point, index) => (
            <div key={`${readText(point.name, "punkt")}-${index}`} className="ana-cp">
              <div className="ana-cp-head">
                <strong>{readText(point.name)}</strong>
                <span className={`ana-incomm ${readText(point.incommensurability_type)}`}>{readText(point.incommensurability_type)}</span>
                <ReferenceList refs={readNumberList(point.exchange_refs)} />
              </div>
              <div className="ana-cp-claims">
                <span className="s1">{readText(point.agent_1_claim)}</span>
                <span className="vs">vs</span>
                <span className="s2">{readText(point.agent_2_claim)}</span>
              </div>
            </div>
          ))}
        </Section>
      ) : null}

      {interactionPatterns ? (
        <Section title="Wzorce interakcji">
          <div className="ana-cols">
            {[
              { key: "pattern-agent-1", name: agent1, tone: "s1", items: readRecordList(interactionPatterns.agent_1) },
              { key: "pattern-agent-2", name: agent2, tone: "s2", items: readRecordList(interactionPatterns.agent_2) },
            ].map(({ key, name, tone, items }) => (
              <div key={key} className="ana-attack-col">
                <div className={`ana-sub-title ${tone}`}>{name}</div>
                {items.map((item, index) => (
                  <div key={`${readText(item.type, "pattern")}-${index}`} className="ana-attack-item">
                    <div>
                      <em>{readText(item.type)}</em> <ReferenceList refs={readNumberList(item.exchanges)} />
                    </div>
                    <div className="muted">{readText(item.description)}</div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </Section>
      ) : null}

      {positionAsymmetries ? (
        <Section title="Asymetrie pozycji">
          <div className="ana-asym-grid">
            {[
              {
                label: "Najsłabszy gdy",
                first: readText(positionAsymmetries.agent_1_weakest_when, "—"),
                second: readText(positionAsymmetries.agent_2_weakest_when, "—"),
              },
              {
                label: "Najsilniejszy gdy",
                first: readText(positionAsymmetries.agent_1_strongest_when, "—"),
                second: readText(positionAsymmetries.agent_2_strongest_when, "—"),
              },
            ].map((row) => (
              <div key={row.label} className="asym-row">
                <div className="asym-lbl">{row.label}</div>
                <div className="asym-cell s1">{row.first}</div>
                <div className="asym-cell s2">{row.second}</div>
              </div>
            ))}
          </div>
        </Section>
      ) : null}

      {translationFailures.length > 0 ? (
        <Section title="Translation failures">
          {translationFailures.map((failure, index) => (
            <div key={`${readText(failure.term, "failure")}-${index}`} className="ana-tf">
              <div>
                <strong>{readText(failure.term)}</strong>{" "}
                {readNumber(failure.exchange) !== null ? <span className="ana-xref">#{readNumber(failure.exchange)}</span> : null}
              </div>
              <div className="ana-tf-reads">
                <span className="s1">{readText(failure.agent_1_reading)}</span>
                <span className="vs">≠</span>
                <span className="s2">{readText(failure.agent_2_reading)}</span>
              </div>
              <div className="muted">{readText(failure.description)}</div>
            </div>
          ))}
        </Section>
      ) : null}

      {maxTensionExchange ? (
        <Section
          title={
            <>
              Moment maksymalnego napięcia lub przełomu{" "}
              {readNumber(maxTensionExchange.exchange) !== null ? <span className="ana-xref">#{readNumber(maxTensionExchange.exchange)}</span> : null}
            </>
          }
          className="ana-sec ana-tension"
        >
          <p>{readText(maxTensionExchange.why)}</p>
        </Section>
      ) : null}

      {unspoken.length > 0 ? (
        <Section title="Przemilczane">
          <BulletList items={unspoken} />
        </Section>
      ) : null}

      {relationStatus ? (
        <Section title="Status relacji">
          <span className="ana-spore-type">{readText(relationStatus.type)}</span>
          <p>{readText(relationStatus.rationale)}</p>
        </Section>
      ) : null}

      {trajectory ? (
        <Section title="Trajektoria">
          <span className="ana-spore-type">{readText(trajectory.convergence, "—")}</span>
          <p>{readText(trajectory.depth_progression)}</p>
          <p className="muted">{readText(trajectory.exit_proximity)}</p>
        </Section>
      ) : null}
    </div>
  );
}