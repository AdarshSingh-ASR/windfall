import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  type ClerkRec,
  type Decision,
  type Opportunity,
  type ScenarioRec,
  type Turn,
} from "./api";

const KIND_TAG: Record<string, string> = {
  settlement: "CLASS SETTLEMENT",
  benefit_window: "BENEFIT WINDOW",
  discount_program: "DISCOUNT PROGRAM",
  refund_rule: "COMPENSATION RULE",
  unclaimed_property: "UNCLAIMED PROPERTY",
};

function clerkTag(side: string, clerks: ClerkRec[]): string {
  if (side.startsWith("clerk:")) {
    const c = clerks.find((x) => x.id === side.slice(6));
    return c ? c.org : side.slice(6);
  }
  if (side === "windfall") return "Windfall";
  if (side === "system") return "Pipeline";
  return side;
}

function fmtMoney(n: number): string {
  return "$" + Math.round(n).toLocaleString();
}

function fmtFields(f: Record<string, unknown>): string {
  const entries = Object.entries(f);
  if (!entries.length) return "";
  return entries
    .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
    .join(" · ")
    .slice(0, 170);
}

const STATUS_LABEL: Record<string, string> = {
  new: "surfaced",
  working: "scouting",
  triaged: "priced",
  filing: "filing",
  needs_consent: "needs your consent",
  awaiting: "in their queue",
  approved: "approved",
  denied: "denied",
  resolved: "closed",
  failed: "failed",
};

export default function App() {
  const [opps, setOpps] = useState<Opportunity[]>([]);
  const [clerks, setClerks] = useState<ClerkRec[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioRec[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [ledger, setLedger] = useState<Record<string, number>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<Opportunity | null>(null);
  const [seeding, setSeeding] = useState<string | null>(null);

  const refreshLists = useCallback(async () => {
    const [op, cl, sc, dc, lg] = await Promise.all([
      api.opportunities(),
      api.clerks(),
      api.scenarios(),
      api.decisions(),
      api.ledger(),
    ]);
    setOpps(op.opportunities);
    setClerks(cl.clerks);
    setScenarios(sc.scenarios);
    setDecisions(dc.decisions);
    setLedger(lg.totals);
    setSelected((cur) => cur ?? op.opportunities[0]?.id ?? null);
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
      api.opportunity(selected).then((d) => {
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
    () => decisions.find((d) => d.opportunity_id === selected && d.status === "pending"),
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
  const m = detail?.triage;

  return (
    <div className="app">
      <header className="masthead">
        <div className="wordmark">
          <span className="mark">W</span> Windfall
        </div>
        <div className="tagline">finds money you're owed · files it · fights denials</div>
        <div className="spacer" />
        <div className="found-pill">
          <span>
            recovered <b>{fmtMoney(ledger.recovered ?? 0)}</b>
          </span>
          <span>
            annualized <b>{fmtMoney(ledger.annualized ?? 0)}/yr</b>
          </span>
        </div>
      </header>

      {/* ------------------------------------------------- opportunities -- */}
      <aside className="sidebar">
        <div className="sidebar-fixed">
          <div className="section-label">Scouted opportunities</div>
        </div>
        <div className="opp-scroll">
          {opps.length === 0 && (
            <div style={{ color: "var(--muted-fg)", fontSize: 12.5 }}>
              Nothing on the docket. Surface an opportunity below — Windfall takes it from there.
            </div>
          )}
          {opps.map((o) => (
            <div
              key={o.id}
              className={`opp-item ${o.id === selected ? "active" : ""}`}
              onClick={() => setSelected(o.id)}
            >
              <div className="top">
                <span>
                  <span className={`status-dot status-${o.status}`} />
                  {STATUS_LABEL[o.status] ?? o.status}
                </span>
                <span>{KIND_TAG[o.kind] ?? o.kind}</span>
              </div>
              <div className="title">{o.title.slice(0, 70)}{o.title.length > 70 ? "…" : ""}</div>
              {(o.est_low > 0 || o.est_high > 0) && (
                <div className="value">
                  {o.est_low === o.est_high
                    ? fmtMoney(o.est_low)
                    : `${fmtMoney(o.est_low)}–${fmtMoney(o.est_high)}`}
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="sidebar-fixed">
          <div className="section-label">Surface an opportunity</div>
        </div>
        <div className="sidebar-fixed-bottom">
        {scenarios.map((s) => (
          <button
            key={s.id}
            className="seed-btn"
            disabled={seeding !== null}
            onClick={() => seed(s.id)}
          >
            {seeding === s.id ? <span className="spin">◌ </span> : "＋ "}
            {s.title.slice(0, 64)}{s.title.length > 64 ? "…" : ""}
            <div className="sub">{s.source}</div>
          </button>
        ))}
        </div>
      </aside>

      {/* ----------------------------------------------------------- main */}
      <main className="main">
        {!detail ? (
          <div className="empty">
            <div className="big">
              Money agents help you <em>spend less</em>.
              <br />
              Windfall gets back what's <em>already yours</em>.
            </div>
            <p>
              Unclaimed property. Class settlements nobody heard about. Utility
              discounts people qualify for but never file. Compensation rules that
              expired while the form sat in a drawer. Windfall's scouts watch it
              all, price it against your household, file the claim, and fight the
              denial if one comes back.
            </p>
            <p style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>
              surface an opportunity on the left to watch it work
            </p>
          </div>
        ) : (
          <>
            <div className="opp-head">
              <div className="kicker">
                <span>{KIND_TAG[detail.kind] ?? detail.kind}</span>
                <span>{detail.source}</span>
                <span>{STATUS_LABEL[detail.status] ?? detail.status}</span>
              </div>
              <h1>{detail.title}</h1>
              {detail.outcome && <div className="outcome">{detail.outcome}</div>}
              {m && (
                <div className="match-grid">
                  <div className="match-cell">
                    <div className="k">Est. value</div>
                    <div className="v accent">
                      {m.est_value_low === m.est_value_high
                        ? fmtMoney(m.est_value_low)
                        : `${fmtMoney(m.est_value_low)}–${fmtMoney(m.est_value_high)}`}
                    </div>
                  </div>
                  <div className="match-cell">
                    <div className="k">Deadline</div>
                    <div className="v">{m.deadline === "rolling" ? "rolling" : m.deadline.slice(0, 10)}</div>
                  </div>
                  <div className="match-cell">
                    <div className="k">Confidence</div>
                    <div className="v ok">{Math.round(m.confidence * 100)}%</div>
                    <div className="confidence-bar">
                      <i style={{ width: `${Math.round(m.confidence * 100)}%` }} />
                    </div>
                  </div>
                  <div className="match-cell">
                    <div className="k">Filing</div>
                    <div className="v">{m.needs_consent ? "needs consent" : "autonomous"}</div>
                  </div>
                </div>
              )}
            </div>
            <div className="transcript">
              {turns.map((t) => (
                <TurnView key={t.id} t={t} clerks={clerks} />
              ))}
              {["working", "new", "triaged", "filing"].includes(detail.status) && (
                <div className="turn system">
                  <span className="spin">◌</span> Windfall is working the file…
                </div>
              )}
            </div>
          </>
        )}
      </main>

      {/* ----------------------------------------------------------- rail */}
      <aside className="rail">
        <div className="section-label">Needs your signature</div>
        {anyPending.length === 0 && (
          <div className="quiet-note">
            Nothing needs you. Windfall files what it can on its own and
            interrupts you only for consent, opt-ins, or postage.
          </div>
        )}
        {anyPending.map((d) => (
          <div key={d.id} className="decision-card">
            <span className="stamp">{d.kind.replace("_", " ")}</span>
            <div className="q">{d.question}</div>
            {d.opportunity_id !== selected && (
              <div className="ctx">
                re: {opps.find((o) => o.id === d.opportunity_id)?.title.slice(0, 70)}
              </div>
            )}
            <div className="decision-actions">
              <button className="btn approve" onClick={() => answer(d.id, "approved")}>
                Authorize
              </button>
              <button className="btn decline" onClick={() => answer(d.id, "declined")}>
                Skip
              </button>
            </div>
          </div>
        ))}
        {pendingForSelected && (
          <div className="quiet-note" style={{ borderColor: "var(--tacet-orange)" }}>
            ⏸ This file is paused mid-claim, waiting on your authorization above.
          </div>
        )}

        <div className="section-label">Issuing bodies</div>
        {clerks.map((c) => (
          <div key={c.id} className="clerk-row">
            <div className="avatar">{c.org.slice(0, 1)}</div>
            <div>
              <div className="nm">{c.org}</div>
              <div className="ds">{c.role}</div>
            </div>
          </div>
        ))}

        <div className="quiet-note">
          Each issuing body here runs its own agent with its real internal rules —
          income thresholds, deadline enforcement, appeal rights. Windfall argues
          within them. Denials get appealed with the specific rule cited.
        </div>
      </aside>
    </div>
  );
}

function TurnView({ t, clerks }: { t: Turn; clerks: ClerkRec[] }) {
  const isSystem = t.side === "system";
  const isClerk = t.side.startsWith("clerk:");
  const cls = isSystem
    ? `turn system ${t.intent === "error" ? "error" : ""}`
    : isClerk
      ? `turn clerk ${t.intent}`
      : "turn windfall";
  return (
    <div className={cls}>
      <div className="who">
        <span>{clerkTag(t.side, clerks)}</span>
        <span>· {t.intent.replace("_", " ")}</span>
      </div>
      <div className="body">{t.message}</div>
      {Object.keys(t.fields ?? {}).length > 0 && (
        <div className="fields">{fmtFields(t.fields)}</div>
      )}
    </div>
  );
}
