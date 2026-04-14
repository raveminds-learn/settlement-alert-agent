# ⚡ RaveMinds Settlement Alert Agent

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

## Human-in-the-loop

The agent proposes actions and draft communications; **you** approve or reject before anything is treated as executed. That keeps accountability explicit — important in regulated operations.

**Characteristics:** proactive monitoring (not only on-demand), state carried across cycles, multi-factor prioritisation, and counterparty context from LanceDB.

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

**Launcher scripts**

- **`start.bat`** — Verifies Python and Ollama, starts `ollama serve` if needed, pulls `mistral` when missing, installs `requirements.txt`, opens the browser, then runs Streamlit on port **8501**.
- **`stop.bat`** — Stops Streamlit and anything listening on **8501**, then stops the Ollama process.

Run `start.bat` from the project folder (or double-click it). In the app: **Initialise Knowledge Store**, then **Run Agent Cycle**.

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

*Built with ❤️ by RaveMinds | Local-first | Zero API cost | Enterprise FinTech*
