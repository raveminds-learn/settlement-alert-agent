# ⚡ RaveMinds Settlement Alert Agent
**RaveMinds Series 2 · Project 2 of 3**

> T+1 cut the time to resolve settlement fails in half — but ops teams are still managing them manually with the same human reaction time they had under T+2. This agent fixes that.

---

## The Problem

Since May 2024, US equity and bond markets operate on T+1 settlement. When a trade fails to settle, ops teams have one business day to resolve it before SEC Rule 204 closeouts, NSCC buy-ins, and FINRA scrutiny kick in.

The challenge: hundreds of failing trades, manual prioritisation, institutional knowledge locked in people's heads, and half the time to act compared to T+2.

**Wrong prioritisation = regulatory consequences.**  
**Right prioritisation = resolved before the deadline.**

---

## The Solution

An autonomous agent that:
- **Monitors** the settlement fail queue continuously — no human needs to ask
- **Scores** every fail across regulatory deadline, financial exposure, cascade risk, and counterparty behaviour
- **Prioritises** dynamically — the queue re-ranks as new fails arrive and old ones resolve
- **Recommends** specific actions with draft communications ready to send
- **Awaits** explicit human approval before executing anything
- **Logs** every decision for full audit trail

---

## AI Pattern: Autonomous Agents with Human in the Loop

This is the hero concept of this project — and what separates it from every Series 1 build.

| | Series 1 (AskOps etc.) | This project |
|---|---|---|
| **Trigger** | Human asks a question | Agent acts on its own initiative |
| **Loop** | Request → Response → Done | Monitor → Reason → Act → Loop forever |
| **Human role** | Questioner | Decision-maker (approve/reject) |
| **State** | Stateless per call | Stateful across cycles |
| **Pattern** | Reactive | Proactive |

The human-in-the-loop is not a limitation — it is the correct architecture for regulated environments where every consequential action needs human accountability.

---

## Architecture

```
Ops Analyst (human)
      ↕  approve / reject
Streamlit Workbench
      ↕
LangGraph Agentic Loop (agents/agent_loop.py)
  ├── Agent 1: Monitor     — ingests mock fail queue + Rule 204 context
  ├── Agent 2: Reason      — scores each fail (5 dimensions)
  ├── Agent 3: Prioritise  — ranks queue
  ├── Agent 4: Recommend   — Mistral 7B drafts comms (local Ollama)
  └── Agent 5: Execute     — applies approved/rejected actions in-cycle
      ↕                    ↕                    ↕
   Mock data            LanceDB             Mistral 7B
   (mock_dtcc)     Counterparty intel    via Ollama (local)
```

An alternate implementation in `agents/graph.py` uses **DuckDB** (`data/queue_manager.py`) and the **ollama** Python client; the Streamlit app uses **`agents/agent_loop.py`** (HTTP to Ollama). Langfuse is listed below as optional observability and is **not wired in this repository** yet.

---

## Priority Scoring Logic

Each fail is scored 0-100 across five dimensions:

| Dimension | Max Points | How scored |
|---|---|---|
| Rule 204 deadline proximity | 40 | Overdue=40, Today=35, Tomorrow=25, 2 days=15 |
| Notional value | 25 | $10m+=25, $5m+=20, $2m+=15, $1m+=10 |
| Cascade risk | 20 | Has downstream trades × multiplier |
| Days failing | 10 | Days × 2, capped at 10 |
| Counterparty resolution speed | 5 | Slow counterparties score higher urgency |

---

## New Concepts vs Series 1

- **Agentic loop** — graph runs continuously, never terminates
- **Human-in-the-loop architecture** — approval gate is first-class in the pipeline
- **Multi-dimensional autonomous prioritisation** — not routing, judgment
- **Continuous stateful memory** — queue state persists and evolves across cycles
- **Institutional knowledge encoding** — counterparty patterns in LanceDB

---

## Tech Stack

| Component | Technology | Cost |
|---|---|---|
| UI | Streamlit | $0 |
| Agent loop | LangGraph | $0 |
| LLM | Ollama + Mistral 7B | $0 |
| Fail data | In-memory mock (`mock_dtcc`) / optional DuckDB path | $0 |
| Institutional knowledge | LanceDB | $0 |
| Observability | Langfuse (optional, not integrated in code yet) | $0 |
| **Total** | | **$0** |

---

## Project Structure

```
settlement-alert-agent/
├── agents/
│   ├── agent_loop.py         # LangGraph pipeline used by the Streamlit UI
│   └── graph.py              # Alternate pipeline (DuckDB + ollama client)
├── data/
│   ├── mock_dtcc.py          # Mock settlement fails
│   ├── counterparty_patterns.py
│   └── queue_manager.py      # DuckDB queue (used by graph.py path)
├── memory/
│   └── knowledge_store.py    # LanceDB counterparty patterns
├── ui/
│   └── app.py                # Streamlit ops workbench
├── requirements.txt
├── start.bat                 # Windows: Ollama + deps + Streamlit
├── stop.bat
└── README.md
```

---

## Quick Start

**Prerequisites:** Python 3.11+, [Ollama](https://ollama.com/) installed, model `mistral` available (`ollama pull mistral`).

### Windows

Double-click `start.bat` (starts Ollama if needed, installs dependencies, opens `http://localhost:8501`). Use `stop.bat` to stop Streamlit and Ollama.

In the app: **Initialise Knowledge Store**, then **Run Agent Cycle**.

### macOS / Linux

```bash
cd settlement-alert-agent
pip install -r requirements.txt
ollama pull mistral
ollama serve   # separate terminal
streamlit run ui/app.py --server.port 8501
```

---

## Mock Data

Mock settlement fails across US equities, corporate bonds, named counterparties, varied fail reasons, and regulatory urgency levels. See `data/mock_dtcc.py`.

---

## Series Context

```
RaveMinds Series 2
├── Project 1: Trade Compliance Copilot   — RAG over private documents
├── Project 2: RaveMinds Settlement Alert Agent      — Autonomous agents + HITL  ← YOU ARE HERE
└── Project 3: TBD                        — Generative reporting
```

**Series arc:** Know → Act → Produce

---

*Built with ❤️ by RaveMinds | Local-first | Zero API cost | Enterprise FinTech*
