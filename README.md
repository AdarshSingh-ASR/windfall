# 💸 Windfall — the found-money agent

**Track: Good Neighbor Agents** · built with the [Strands Agents SDK](https://github.com/strands-agents)

Most money agents help you spend less. **Windfall gets back what's already
yours** — and fights the bureaucracy to do it.

Billions sit in unclaimed property, class-action settlements nobody heard
about, utility discount programs people qualify for but never file, and
compensation rules that expire while the form sits in a drawer. The burden
falls hardest on households without the paperwork stamina to chase it.

Windfall is not a dashboard. It's a claim pipeline that runs itself:

```
opportunity in ──▶ TRIAGE GRAPH (Strands)      intake ─▶ research ─▶ price
                   │ kind · value band · deadline
                   │ confidence · needs_consent?
                   ├──── yes ──▶ 🟡 CONSENT CARD ──▶ claimant authorizes
                   ▼
            CLAIM ASSEMBLY          packet built from the household profile —
                                    only what the claim needs, nothing invented
                   ▼
            FILING                  submitted to the issuing body's clerk-agent
                   ▼
            clerk: approved ──▶ 💸 Found-Money ledger (reference + amount)
                 / needs info ──▶ exact document supplied from profile
                 \ denied ──▶ APPEAL citing the specific rule ──▶ re-filed
```

## The demo moment

During QA, Meridian Air's clerk approved a flight-delay claim at the *bottom*
of the DOT band. Windfall replied citing **14 CFR Part 250**, filed a formal
appeal, and the appeal came back approved at the correct amount with a payment
reference — no human touched anything. That exchange is in the repo's demo
transcripts.

## What's agentic here

| Capability | Where |
| --- | --- |
| **Multi-agent Graph** (`GraphBuilder`) | triage: intake → research (Tavily) → price |
| **Adversarial clerk-agents** | each issuing body (utility, airline, comptroller, settlements admin) runs its own agent bound by its real internal rules — they approve, demand documents, and deny |
| **Structured output everywhere** | OpportunityMatch, FileMove, ProgramReply — typed contracts end to end |
| **Human-in-the-loop consent gates** | SSN, signatures, class opt-ins pause the pipeline for one card |
| **Appeals engine** | denials marked appealable get a rule-citing appeal filed automatically |
| **LiteLLM provider** | Windfall reasons on `gpt-oss-120b`, clerks on `gpt-oss-20b` (separate rate-limit buckets); any vendor via one env var |

The issuing bodies are simulated, but their rules are the real ones — DOT delay
bands, LIDR income thresholds, unclaimed-property address matching, settlement
class periods — and Windfall's arguments against them are unscripted agent
behavior. Swapping any clerk for a real claims portal is a wrapper, not a
rewrite.

## Run it

```bash
# backend (Python 3.12+)
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Windows
cp .env.example .env        # set WINDFALL_MODEL + OPENROUTER_API_KEY (+ TAVILY_API_KEY, optional)

.venv/Scripts/python -m uvicorn app.main:app --port 8001

# frontend (Node 20+)
cd ../frontend
npm install
npm run dev                 # http://localhost:5174
```

Surface any of the four seeded opportunities and watch the file work:
triage → pricing → filing → clerk negotiation → ledger.

## Seeded opportunities

1. **Utility discount (LIDR)** — 20% off the monthly bill for under-60%-SMI
   households; Windfall files with income proof + LIHEAP reference.
2. **Flight-delay compensation** — controllable 3h41m delay; DOT band applies.
3. **Unclaimed property** — $318.40 dormant account matched by former address.
4. **Class settlement** — water-rate overcharges, $85–$140 per account, strict
   deadline, opt-in consent required before filing.

## Honest scope notes

- The issuing bodies are faithful simulations of how these offices behave;
  dollar rules and appeal rights mirror the real programs.
- Ledger entries record what was approved; nothing moves real money.
- Windfall never invents documents — every filing references the household
  profile, and the engine blocks closing a file while a profile document
  remains unsupplied.

## License

MIT — see [LICENSE](LICENSE).
