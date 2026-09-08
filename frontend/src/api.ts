export interface TriageCard {
  event_id: string;
  event_type: string;
  urgency: number;
  category: string;
  headline: string;
  action_plan: string;
  needs_human: boolean;
  human_question: string;
  ttl_note: string;
}

export interface Turn {
  id: string;
  event_id: string;
  side: string;
  intent: string;
  message: string;
  fields: Record<string, unknown>;
  created_at: string;
}

export interface Decision {
  id: string;
  event_id: string;
  kind: string;
  question: string;
  options: string[];
  context: Record<string, unknown>;
  status: "pending" | "approved" | "declined";
  answer_note: string;
  created_at: string;
  answered_at: string | null;
}

export interface EventRec {
  id: string;
  kind: string;
  title: string;
  payload: Record<string, unknown>;
  status: "new" | "working" | "triaged" | "needs_human" | "resolved" | "failed";
  triage: TriageCard | null;
  outcome: string | null;
  created_at: string;
  updated_at: string;
  turn_count?: number;
  turns?: Turn[];
  decisions?: Decision[];
}

export interface ActorRec {
  id: string;
  kind: string;
  name: string;
  persona: string;
  state: Record<string, unknown>;
}

export interface ScenarioRec {
  id: string;
  kind: string;
  title: string;
  payload: Record<string, unknown>;
}

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json() as Promise<T>;
}

export const api = {
  events: () =>
    fetch("/api/events").then((r) => j<{ events: EventRec[] }>(r)),
  event: (id: string) =>
    fetch(`/api/events/${id}`).then((r) => j<EventRec>(r)),
  actors: () =>
    fetch("/api/actors").then((r) => j<{ actors: ActorRec[] }>(r)),
  scenarios: () =>
    fetch("/api/scenarios").then((r) => j<{ scenarios: ScenarioRec[] }>(r)),
  decisions: () =>
    fetch("/api/decisions").then((r) => j<{ decisions: Decision[] }>(r)),
  seed: (id: string) =>
    fetch(`/api/events/seed/${id}`, { method: "POST" }).then((r) =>
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
