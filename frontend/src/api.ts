export interface OpportunityMatch {
  event_id: string;
  kind: string;
  source: string;
  headline: string;
  est_value_low: number;
  est_value_high: number;
  deadline: string;
  confidence: number;
  what_it_takes: string;
  needs_consent: boolean;
  consent_question: string;
}

export interface Turn {
  id: string;
  opportunity_id: string;
  side: string;
  intent: string;
  message: string;
  fields: Record<string, unknown>;
  created_at: string;
}

export interface Decision {
  id: string;
  opportunity_id: string;
  kind: string;
  question: string;
  context: Record<string, unknown>;
  status: "pending" | "approved" | "declined";
  answer_note: string;
  created_at: string;
  answered_at: string | null;
}

export interface Opportunity {
  id: string;
  kind: string;
  source: string;
  title: string;
  payload: Record<string, unknown>;
  status:
    | "new" | "working" | "triaged" | "filing" | "needs_consent"
    | "awaiting" | "approved" | "denied" | "resolved" | "failed";
  triage: OpportunityMatch | null;
  est_low: number;
  est_high: number;
  outcome: string | null;
  created_at: string;
  turn_count?: number;
  turns?: Turn[];
  decisions?: Decision[];
}

export interface ClerkRec {
  id: string;
  org: string;
  role: string;
  persona: string;
  state: Record<string, unknown>;
}

export interface ScenarioRec {
  id: string;
  kind: string;
  source: string;
  title: string;
  payload: Record<string, unknown>;
}

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json() as Promise<T>;
}

export const api = {
  opportunities: () =>
    fetch("/api/opportunities").then((r) => j<{ opportunities: Opportunity[] }>(r)),
  opportunity: (id: string) =>
    fetch(`/api/opportunities/${id}`).then((r) => j<Opportunity>(r)),
  clerks: () => fetch("/api/clerks").then((r) => j<{ clerks: ClerkRec[] }>(r)),
  scenarios: () =>
    fetch("/api/scenarios").then((r) => j<{ scenarios: ScenarioRec[] }>(r)),
  decisions: () =>
    fetch("/api/decisions").then((r) => j<{ decisions: Decision[] }>(r)),
  seed: (id: string) =>
    fetch(`/api/opportunities/seed/${id}`, { method: "POST" }).then((r) =>
      j<{ id?: string; error?: string }>(r)
    ),
  answer: (did: string, status: "approved" | "declined", note = "") =>
    fetch(`/api/decisions/${did}/answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, note }),
    }).then((r) => j<{ ok?: boolean }>(r)),
  ledger: () =>
    fetch("/api/ledger").then((r) => j<{ totals: Record<string, number> }>(r)),
};
