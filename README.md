# 🧺 Gleaner — the food-rescue agent

**Track: Good Neighbor Agents** · built with the [Strands Agents SDK](https://github.com/strands-agents)

Gleaner is a background coordination agent for small food-rescue networks —
food banks, pantries, community kitchens, volunteer drivers. It watches the
network's chaotic event stream (surplus crop offers, storm-meal surges,
cancelled drivers, cold-chain emergencies) and *handles the coordination
itself*: matching, rerouting, confirming, thanking. The human coordinator sees
exactly one thing — a **Decision Card** — and only when there's a real
judgment call: spend money, make a dignity/policy call, or resolve a conflict
niceness can't fix.

```
event in ──▶ TRIAGE GRAPH (Strands)          intake ─▶ research ─▶ plan
             │ urgency · category · plan
             │ needs_human?
             ├──── yes ──▶ 🟡 DECISION CARD ──▶ coordinator approves/declines
             ▼
      AUTONOMOUS EXECUTION
      Gleaner holds live conversations with the affected parties —
      each one is itself a small agent (donor, volunteer, pantry, partner)
      with private constraints and availability. Accepts, counters, declines.
             ▼
      outcome recorded ──▶ impact ledger (meals · kg saved · $ value)
```

## Why this is different

Most "agent dashboards" script the world. Gleaner **negotiates with it**: every
donor, volunteer, pantry, and partner in the simulation is an independent agent
that can say no, counter-offer, or flake — just like real people. Watch the
transcripts and you'll see Gleaner get declined by a food bank (24h notice
rule), reroute to a community kitchen, get a volunteer to accept an afternoon
window another driver couldn't cover, and close the loop with a thank-you —
without a single human instruction. When it genuinely hits a wall (needs $140
for a refrigerated courier), *that's* when your card appears.

Strands capabilities used:

| Capability | Where |
| --- | --- |
| **Multi-agent Graph** (`GraphBuilder`) | triage: intake → research → plan |
| **A2A-style structured protocol** | `Msg` / `ActorReply` — the same schema a real donor's agent or volunteer's calendar bot would speak; swap any simulated actor for a live one without touching the engine |
| **Structured output everywhere** | TriageCard, Msg, ActorReply — typed contracts end to end |
| **LiteLLM provider** | coordinator reasons on `gpt-oss-120b`, actors on `gpt-oss-20b` (separate rate-limit buckets); any vendor via one env var |
| **Tool use** | Tavily-backed `web_search` for food-safety/compliance leverage in the research node |
| **Human-in-the-loop gates** | Decision Cards block the runner thread until the coordinator answers |

## The problem

A typical small food-rescue network runs on one overwhelmed coordinator and a
group chat: a farmer offers 140 kg of surplus at 2pm, a driver cancels at 6pm,
a storm shelter needs 300 meals by 7. Every one of these is a dozen messages,
a schedule puzzle, and a guilt trip. The coordinator burns hours on logistics
instead of the work only humans can do — community, dignity, trust. Gleaner
takes the logistics. It pings the human only where the human matters.

## Run it

```bash
# backend (Python 3.12+)
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Windows
cp .env.example .env        # set GLEANER_MODEL + OPENROUTER_API_KEY (+ TAVILY_API_KEY, optional)

.venv/Scripts/python -m uvicorn app.main:app --port 8001

# frontend (Node 20+)
cd ../frontend
npm install
npm run dev                 # http://localhost:5174
```

Click any scenario under **Inject a live event** and watch the transcript:
triage → plan → live agent-to-agent coordination → resolution → ledger.

### Model configuration (any LiteLLM vendor)

```env
GLEANER_MODEL=openrouter/openai/gpt-oss-120b   + OPENROUTER_API_KEY=...
GLEANER_ACTOR_MODEL=openrouter/openai/gpt-oss-20b
TAVILY_API_KEY=...            # optional, powers the research node
```

## Seeded scenarios

1. **Surplus Sunday** — Greenfield Farms offers 140 kg of produce with a 3–6pm
   pickup window. Gleaner finds a driver whose availability actually matches,
   confirms the pantry, arranges the receipt, thanks the donor.
2. **Fridge shortfall** — 60 kg of dairy arrives but Hope Pantry has 25 kg of
   cold space left. Gleaner splits the load and reroutes the rest.
3. **Storm surge** — 300 hot meals tonight with the usual kitchen at half
   staff. Gleaner lines up cooking capacity, transport, and timing.
4. **Driver no-show** — Priya cancels the bakery run. Gleaner covers it
   without shaming anyone.
5. **Cold-chain emergency** (custom events welcome) — 400 kg of frozen meat,
   no freezer van in the fleet. Gleaner pings you: *approve $140 for a
   refrigerated courier?* — a real judgment call.

## Honest scope notes

- The stakeholders are simulated agents with realistic private constraints —
  the coordination, negotiation, rerouting, and escalation are real agent
  behavior, not scripts.
- Ledger entries record what was arranged; nothing moves real food or money.
- Every actor speaks the same structured protocol, so a real partner
  integration (email, WhatsApp, A2A) is a wrapper, not a rewrite.

## License

MIT — see [LICENSE](LICENSE).
