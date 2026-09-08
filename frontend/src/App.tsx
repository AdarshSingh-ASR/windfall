import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  type ActorRec,
  type Decision,
  type EventRec,
  type ScenarioRec,
  type Turn,
} from "./api";

const KIND_GLYPH: Record<string, string> = {
  gleaner: "🧺",
  system: "⚙",
};

function actorGlyph(side: string): string {
  if (side.startsWith("actor:")) {
    const id = side.slice(6);
    if (id.startsWith("donor")) return "🚜";
    if (id.startsWith("volunteer")) return "🚐";
    if (id.startsWith("pantry")) return "🏪";
    if (id.startsWith("kitchen")) return "🍲";
    if (id.startsWith("partner")) return "🤝";
  }
  return KIND_GLYPH[side] ?? "•";
}

function actorName(side: string, actors: ActorRec[]): string {
  if (side.startsWith("actor:")) {
    const a = actors.find((x) => x.id === side.slice(6));
    return a ? a.name : side.slice(6);
  }
  if (side === "gleaner") return "Gleaner";
  if (side === "system") return "System";
  return side;
}

function fmtFields(f: Record<string, unknown>): string {
  const entries = Object.entries(f);
  if (!entries.length) return "";
  return entries
    .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
    .join(" · ")
    .slice(0, 160);
}

const STATUS_LABEL: Record<string, string> = {
  new: "queued",
  working: "gleaning…",
  triaged: "planned",
  needs_human: "needs you",
  resolved: "resolved",
  failed: "failed",
};

export default function App() {
  const [events, setEvents] = useState<EventRec[]>([]);
  const [actors, setActors] = useState<ActorRec[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioRec[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [ledger, setLedger] = useState<Record<string, number>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<EventRec | null>(null);
  const [seeding, setSeeding] = useState<string | null>(null);

  const refreshLists = useCallback(async () => {
    const [ev, ac, sc, dc, lg] = await Promise.all([
      api.events(),
      api.actors(),
      api.scenarios(),
      api.decisions(),
      api.ledger(),
    ]);
    setEvents(ev.events);
    setActors(ac.actors);
    setScenarios(sc.scenarios);
    setDecisions(dc.decisions);
    setLedger(lg.totals);
    setSelected((cur) => cur ?? ev.events[0]?.id ?? null);
  }, []);

  useEffect(() => {
    refreshLists();
    const t = setInterval(refreshLists, 3000);
    return () => clearInterval(t);
  }, [refreshLists]);

  useEffect(() => {
    if (!selected) return setDetail(null);
    let live = true;
    const load = () =>
      api.event(selected).then((d) => {
        if (live) setDetail(d);
      });
    load();
    const t = setInterval(load, 2500);
    return () => {
      live = false;
      clearInterval(t);
    };
  }, [selected]);

  const pendingForSelected = useMemo(
    () => decisions.find((d) => d.event_id === selected && d.status === "pending"),
    [decisions, selected]
  );
  const anyPending = decisions.filter((d) => d.status === "pending");

  const seed = async (id: string) => {
    setSeeding(id);
    try {
      const r = await api.seed(id);
      if (r.id) setSelected(r.id);
      await refreshLists();
    } finally {
      setSeeding(null);
    }
  };

  const answer = async (did: string, status: "approved" | "declined") => {
    await api.answer(did, status);
    await refreshLists();
  };

  const turns: Turn[] = detail?.turns ?? [];

  return (
    <div className="app">
      <header className="masthead">
        <div className="wordmark">
          <span className="glyph">🧺</span> Gleaner
        </div>
        <div className="tagline">the food-rescue agent · riverside food network</div>
        <div className="spacer" />
        <div className="ledger-pill">
          <span>
            meals <b>{Math.round(ledger.meals ?? 0)}</b>
          </span>
          <span>
            kg saved <b>{Math.round(ledger.kg_saved ?? 0)}</b>
          </span>
          <span>
            value <b>${Math.round(ledger.usd_value ?? 0)}</b>
          </span>
        </div>
      </header>

      {/* ------------------------------------------------- event stream -- */}
      <aside className="sidebar">
        <div className="section-label">Event stream</div>
        {events.length === 0 && (
          <div className="ds" style={{ color: "var(--muted)", fontSize: 12 }}>
            Quiet. Seed a scenario below — Gleaner takes it from there.
          </div>
        )}
        {events.map((e) => (
          <div
            key={e.id}
            className={`event-item ${e.id === selected ? "active" : ""}`}
            onClick={() => setSelected(e.id)}
          >
            <div className="kind">
              <span>
                <span className={`status-dot status-${e.status}`} />
                {STATUS_LABEL[e.status] ?? e.status}
              </span>
              <span>{e.kind.replace("_", " ")}</span>
            </div>
            <div className="title">{e.title}</div>
          </div>
        ))}

        <div className="section-label">Inject a live event</div>
        {scenarios.map((s) => (
          <button
            key={s.id}
            className="seed-btn"
            disabled={seeding !== null}
            onClick={() => seed(s.id)}
          >
            {seeding === s.id ? <span className="spin">◌ </span> : "＋ "}
            {s.title.slice(0, 58)}
            {s.title.length > 58 ? "…" : ""}
            <div className="sub">{s.kind.replace("_", " ")}</div>
          </button>
        ))}
      </aside>

      {/* -------------------------------------------------------- main -- */}
      <main className="main">
        {!detail ? (
          <div className="empty">
            <div className="big">The quiet coordinator.</div>
            <p>
              Gleaner watches the network&apos;s event stream — surplus crops, storm
              surges, cancelled drivers — and handles the coordination itself.
              It only interrupts you when there&apos;s a real decision to make.
            </p>
            <p style={{ fontFamily: "var(--mono)", fontSize: 11 }}>
              seed an event on the left to watch it work
            </p>
          </div>
        ) : (
          <>
            <div className="event-head">
              <h1>{detail.title}</h1>
              <div style={{ fontFamily: "var(--mono)", fontSize: 10.5, color: "var(--muted)" }}>
                {detail.id} · {STATUS_LABEL[detail.status] ?? detail.status}
                {detail.outcome ? ` · ${detail.outcome}` : ""}
              </div>
              {detail.triage && (
                <div className="triage-box">
                  <div className="meta">
                    <span>urgency {detail.triage.urgency}/5</span>
                    <span>{detail.triage.category}</span>
                    <span>{detail.triage.needs_human ? "human needed" : "autonomous"}</span>
                  </div>
                  <div className="plan">{detail.triage.action_plan}</div>
                </div>
              )}
            </div>
            <div className="transcript">
              {turns.map((t) => (
                <TurnView key={t.id} t={t} actors={actors} />
              ))}
              {(detail.status === "working" || detail.status === "new" || detail.status === "triaged") && (
                <div className="turn system">
                  <span className="spin">◌</span> Gleaner is working…
                </div>
              )}
            </div>
          </>
        )}
      </main>

      {/* -------------------------------------------------------- rail -- */}
      <aside className="rail">
        <div className="section-label">Decisions</div>
        {anyPending.length === 0 && (
          <div className="quiet-note">
            Nothing needs you right now. Gleaner is handling the routine —
            this card appears only for real judgment calls.
          </div>
        )}
        {anyPending.map((d) => (
          <div key={d.id} className="decision-card">
            <span className="stamp">{d.kind.replace("_", " ")}</span>
            <div className="q">{d.question}</div>
            {d.event_id !== selected && (
              <div className="ctx">
                event: {events.find((e) => e.id === d.event_id)?.title.slice(0, 60)}
              </div>
            )}
            <div className="decision-actions">
              <button className="btn approve" onClick={() => answer(d.id, "approved")}>
                Approve
              </button>
              <button className="btn decline" onClick={() => answer(d.id, "declined")}>
                Decline
              </button>
            </div>
          </div>
        ))}
        {anyPending.some((d) => d.event_id === selected) && (
          <div className="quiet-note" style={{ borderColor: "var(--accent)" }}>
            ⚡ A decision is pending on the open event — Gleaner paused mid-plan,
            waiting for your answer.
          </div>
        )}

        <div className="section-label">The roster</div>
        {actors.map((a) => (
          <div key={a.id} className="actor-row">
            <div className="avatar">{actorGlyph(`actor:${a.id}`).replace("🧺", "•")}</div>
            <div>
              <div className="nm">{a.name}</div>
              <div className="ds">{Object.values(a.state).slice(0, 3).join(" · ").slice(0, 70)}</div>
            </div>
          </div>
        ))}

        <div className="quiet-note">
          Every donor, volunteer, pantry, and partner here is itself a small agent
          with its own constraints and availability. Gleaner doesn&apos;t script
          them — it negotiates with them, live.
        </div>
      </aside>
    </div>
  );
}

function TurnView({ t, actors }: { t: Turn; actors: ActorRec[] }) {
  const isSystem = t.side === "system";
  const cls = isSystem
    ? `turn system ${t.intent === "error" ? "error" : ""}`
    : t.side === "gleaner"
      ? "turn gleaner"
      : `turn actor ${t.intent}`;
  return (
    <div className={cls}>
      <div className="who">
        <span>{actorGlyph(t.side)} {actorName(t.side, actors)}</span>
        <span>· {t.intent}</span>
      </div>
      <div>{t.message}</div>
      {Object.keys(t.fields ?? {}).length > 0 && (
        <div className="fields">{fmtFields(t.fields)}</div>
      )}
    </div>
  );
}
