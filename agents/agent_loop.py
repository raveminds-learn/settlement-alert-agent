"""
LangGraph Agentic Loop — RaveMinds Settlement Alert Agent
RaveMinds Series 2, Project 2

5-agent pipeline running continuously:
Monitor -> Reason -> Prioritise -> Recommend -> Execute -> loop

This is the hero of the project — the agentic loop pattern.
Unlike AskOps (question -> answer -> done), this loop runs forever,
maintains state, and proactively surfaces actions for human approval.
"""

import os
import sys
import json
import requests
from datetime import datetime, date
from typing import TypedDict, Annotated, Callable
from langgraph.graph import StateGraph, END
import operator

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.mock_dtcc import get_all_fails, get_fail_by_id
from memory.knowledge_store import retrieve_counterparty_knowledge, initialise_knowledge_store

OLLAMA_URL  = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"


def call_ollama(prompt: str, max_tokens: int = 300) -> str:
    try:
        r = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                  "options": {"num_predict": max_tokens, "temperature": 0.2}},
            timeout=60,
        )
        if r.status_code == 200:
            return r.json().get("response", "").strip()
        return f"[Ollama error {r.status_code}]"
    except Exception as e:
        return f"[Ollama unavailable: {e}]"


# ── Normalise field names from mock data ──────────────────────────────────────

def normalise(fail: dict) -> dict:
    """
    Normalise mock data field names to agent-internal names.
    mock_dtcc uses: rule204_deadline, daily_penalty, days_failing,
                    direction, cascade_risk (bool)
    agent uses:     rule_204_deadline, estimated_penalty_per_day, fail_age_days,
                    side, cascade_risk (str HIGH/MEDIUM/LOW)
    """
    cascade_raw = fail.get("cascade_risk", False)
    if isinstance(cascade_raw, bool):
        cascade_str = "HIGH" if cascade_raw else "LOW"
    else:
        cascade_str = str(cascade_raw)

    return {
        **fail,
        "rule_204_deadline":         fail.get("rule204_deadline", ""),
        "estimated_penalty_per_day": fail.get("daily_penalty", 0.0),
        "fail_age_days":             fail.get("days_failing", 0),
        "side":                      fail.get("direction", ""),
        "cascade_risk":              cascade_str,
        "partial_settlement_possible": bool(fail.get("downstream_trades")),
        "partial_qty_available":     0,
    }


# ── Agent State ───────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    cycle:            int
    timestamp:        str
    raw_fails:        list
    scored_fails:     list
    prioritised_queue: list
    recommendations:  list
    pending_approvals: list
    approved_actions: list
    rejected_actions: list
    audit_log:        Annotated[list, operator.add]
    loop_active:      bool


# ── Agent 1: Monitor ──────────────────────────────────────────────────────────

def monitor_agent(state: AgentState) -> AgentState:
    today = date.today()
    enriched = []
    for raw in get_all_fails():
        fail = normalise(raw)
        deadline_str = fail.get("rule_204_deadline", "")
        try:
            dl = datetime.strptime(deadline_str, "%Y-%m-%d").date()
            days_to = (dl - today).days
        except ValueError:
            days_to = 99

        status = (
            "EXPIRED"  if days_to < 0 else
            "TODAY"    if days_to == 0 else
            "TOMORROW" if days_to == 1 else
            "UPCOMING"
        )
        enriched.append({**fail, "days_to_rule_204": days_to, "deadline_status": status})

    critical = sum(1 for f in enriched if f["deadline_status"] in ("EXPIRED", "TODAY"))
    return {
        **state,
        "raw_fails":  enriched,
        "timestamp":  datetime.now().isoformat(),
        "audit_log": [{
            "cycle": state["cycle"], "agent": "Monitor",
            "timestamp": datetime.now().isoformat(),
            "action": f"Ingested {len(enriched)} failing trades — {critical} critical",
        }],
    }


# ── Agent 2: Reason ───────────────────────────────────────────────────────────

def reason_agent(state: AgentState) -> AgentState:
    scored = []
    for fail in state["raw_fails"]:
        knowledge = retrieve_counterparty_knowledge(fail["counterparty"])
        score     = _priority_score(fail, knowledge)
        scored.append({**fail, "priority_score": score, "counterparty_knowledge": knowledge})

    return {
        **state,
        "scored_fails": scored,
        "audit_log": [{
            "cycle": state["cycle"], "agent": "Reason",
            "timestamp": datetime.now().isoformat(),
            "action": f"Scored {len(scored)} fails across 5 dimensions",
        }],
    }


def _priority_score(fail: dict, knowledge: dict | None) -> float:
    """
    Multi-dimensional priority score (0-100).
    Encodes the judgment experienced ops staff apply manually.
    """
    score = 0.0

    # 1. Regulatory urgency (40 pts)
    days = fail.get("days_to_rule_204", 99)
    score += (40 if days < 0 else 35 if days == 0 else 25 if days == 1
              else 15 if days == 2 else max(0, 10 - days))

    # 2. Financial cost (25 pts)
    p = fail.get("estimated_penalty_per_day", 0)
    score += (25 if p >= 10000 else 20 if p >= 5000 else 15 if p >= 2000
              else 10 if p >= 1000 else 5)

    # 3. Cascade risk (20 pts)
    c = fail.get("cascade_risk", "LOW")
    score += (20 if c == "HIGH" else 12 if c == "MEDIUM" else 4)

    # 4. Age of fail (10 pts)
    score += min(10, fail.get("fail_age_days", 0) * 3)

    # 5. Resolution ease (5 pts)
    if knowledge:
        rate = knowledge.get("resolution_rate_pct", 70)
        score += (5 if rate >= 90 else 4 if rate >= 75 else 2 if rate >= 60 else 1)
    else:
        score += 2

    return round(score, 1)


# ── Agent 3: Prioritise ───────────────────────────────────────────────────────

def prioritise_agent(state: AgentState) -> AgentState:
    ranked = sorted(state["scored_fails"], key=lambda x: x["priority_score"], reverse=True)
    queue  = [{**f, "queue_rank": i+1} for i, f in enumerate(ranked)]
    top    = queue[0] if queue else {}
    return {
        **state,
        "prioritised_queue": queue,
        "audit_log": [{
            "cycle": state["cycle"], "agent": "Prioritise",
            "timestamp": datetime.now().isoformat(),
            "action": (f"Queue ranked. Top: {top.get('fail_id','?')} "
                       f"({top.get('security','?')}) score={top.get('priority_score','?')}"),
        }],
    }


# ── Agent 4: Recommend ────────────────────────────────────────────────────────

def recommend_agent(state: AgentState) -> AgentState:
    recs = [_make_recommendation(f, f.get("counterparty_knowledge"))
            for f in state["prioritised_queue"][:5]]
    return {
        **state,
        "recommendations":  recs,
        "pending_approvals": recs,
        "audit_log": [{
            "cycle": state["cycle"], "agent": "Recommend",
            "timestamp": datetime.now().isoformat(),
            "action": f"Generated {len(recs)} recommendations for human approval",
        }],
    }


def _action_type(fail: dict, knowledge: dict | None) -> str:
    deadline   = fail.get("deadline_status", "UPCOMING")
    cascade    = fail.get("cascade_risk", "LOW")
    partial    = fail.get("partial_settlement_possible", False)
    notional   = fail.get("notional", 0)
    threshold  = knowledge.get("escalation_threshold_usd", 5_000_000) if knowledge else 5_000_000

    if deadline in ("EXPIRED", "TODAY") and notional >= threshold:
        return "ESCALATE_TO_TRADING_DESK"
    if deadline in ("EXPIRED", "TODAY"):
        return "URGENT_COUNTERPARTY_CHASE"
    if cascade == "HIGH" and partial:
        return "PARTIAL_SETTLEMENT"
    if cascade == "HIGH":
        return "PRIORITY_COUNTERPARTY_CHASE"
    if deadline == "TOMORROW":
        return "COUNTERPARTY_CHASE"
    return "MONITOR_AND_CHASE"


def _draft_comm(fail: dict, knowledge: dict | None, action: str) -> str:
    channel = knowledge.get("preferred_channel", "direct ops line") if knowledge else "direct ops line"
    prompt = (
        f"You are a senior settlement operations professional at a US broker-dealer.\n"
        f"Draft a brief 3-sentence professional message to resolve a settlement fail.\n"
        f"Security: {fail['security']} ({fail.get('isin','')})\n"
        f"Trade ref: {fail['trade_ref']}\n"
        f"Fail reason: {fail['fail_reason']}\n"
        f"Settlement date: {fail['settlement_date']}\n"
        f"Rule 204 deadline: {fail.get('rule_204_deadline','')}\n"
        f"Action: {action} via {channel}\n"
        f"Output only the message body. No greeting or sign-off."
    )
    draft = call_ollama(prompt, 200)
    if draft.startswith("[Ollama"):
        draft = (
            f"Re: Settlement fail — {fail['trade_ref']} ({fail['security']}).\n"
            f"This trade remains unsettled as of {fail['settlement_date']}. "
            f"Reason on record: {fail['fail_reason']}. "
            f"Please confirm your position and provide a resolution timeline. "
            f"Rule 204 deadline: {fail.get('rule_204_deadline','TBD')}."
        )
    return draft


def _reasoning(fail: dict, knowledge: dict | None) -> str:
    parts = [f"Score {fail['priority_score']}/100 (rank #{fail['queue_rank']})"]
    d = fail.get("deadline_status"); days = fail.get("days_to_rule_204", 99)
    if d == "EXPIRED":   parts.append("CRITICAL: Rule 204 deadline passed")
    elif d == "TODAY":   parts.append("URGENT: Rule 204 deadline today")
    elif d == "TOMORROW":parts.append(f"WARNING: {days}d to Rule 204 deadline")
    else:                parts.append(f"{days}d to Rule 204 deadline")
    parts.append(f"Penalty: ${fail.get('estimated_penalty_per_day',0):,.0f}/day")
    if fail.get("cascade_risk") == "HIGH":
        parts.append("High cascade risk — may block downstream settlements")
    if knowledge:
        parts.append(
            f"{knowledge['counterparty']}: avg {knowledge['avg_resolution_hours']}h resolution, "
            f"best window {knowledge['best_contact_window']}"
        )
    return " | ".join(parts)


def _make_recommendation(fail: dict, knowledge: dict | None) -> dict:
    action = _action_type(fail, knowledge)
    return {
        "fail_id":             fail["fail_id"],
        "security":            fail["security"],
        "counterparty":        fail["counterparty"],
        "notional":            fail["notional"],
        "priority_score":      fail["priority_score"],
        "queue_rank":          fail["queue_rank"],
        "deadline_status":     fail["deadline_status"],
        "days_to_rule_204":    fail["days_to_rule_204"],
        "action_type":         action,
        "draft_communication": _draft_comm(fail, knowledge, action),
        "reasoning":           _reasoning(fail, knowledge),
        "status":              "PENDING",
        "recommended_at":      datetime.now().isoformat(),
        "approved_at":         None,
        "rejected_at":         None,
    }


# ── Agent 5: Execute ──────────────────────────────────────────────────────────

def execute_agent(state: AgentState) -> AgentState:
    executed = [
        {**a, "status": "EXECUTED", "executed_at": datetime.now().isoformat()}
        for a in state.get("approved_actions", [])
    ]
    return {
        **state,
        "approved_actions": executed,
        "cycle": state["cycle"] + 1,
        "audit_log": [{
            "cycle": state["cycle"], "agent": "Execute",
            "timestamp": datetime.now().isoformat(),
            "action": (f"Executed {len(executed)} approved actions, "
                       f"{len(state.get('rejected_actions',[]))} rejected"),
        }],
    }


# ── Graph ─────────────────────────────────────────────────────────────────────

def build_agent_graph():
    g = StateGraph(AgentState)
    g.add_node("monitor",    monitor_agent)
    g.add_node("reason",     reason_agent)
    g.add_node("prioritise", prioritise_agent)
    g.add_node("recommend",  recommend_agent)
    g.add_node("execute",    execute_agent)
    g.set_entry_point("monitor")
    g.add_edge("monitor",    "reason")
    g.add_edge("reason",     "prioritise")
    g.add_edge("prioritise", "recommend")
    g.add_edge("recommend",  "execute")
    g.add_edge("execute",    END)
    return g.compile()


def get_initial_state() -> AgentState:
    return AgentState(
        cycle=1, timestamp=datetime.now().isoformat(),
        raw_fails=[], scored_fails=[], prioritised_queue=[],
        recommendations=[], pending_approvals=[],
        approved_actions=[], rejected_actions=[],
        audit_log=[], loop_active=True,
    )


def run_agent_cycle(current_state: AgentState) -> AgentState:
    return build_agent_graph().invoke(current_state)


def run_agent_cycle_with_progress(
    current_state: AgentState,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> AgentState:
    """
    Run one cycle and emit progress updates per agent step.
    callback args: (agent_name, step_index, total_steps)
    """
    steps = [
        ("Monitor", monitor_agent),
        ("Reason", reason_agent),
        ("Prioritise", prioritise_agent),
        ("Recommend", recommend_agent),
        ("Execute", execute_agent),
    ]
    total_steps = len(steps)
    state = current_state

    for idx, (agent_name, agent_fn) in enumerate(steps, start=1):
        if progress_callback:
            progress_callback(agent_name, idx, total_steps)
        state = agent_fn(state)

    return state


if __name__ == "__main__":
    print("Initialising knowledge store...")
    initialise_knowledge_store()
    print("Running agent cycle...")
    state  = get_initial_state()
    result = run_agent_cycle(state)
    print(f"\nCycle complete — {len(result['recommendations'])} recommendations:")
    for r in result["recommendations"]:
        print(f"  [{r['queue_rank']}] {r['fail_id']} {r['security']} "
              f"— {r['action_type']} (score {r['priority_score']})")
        print(f"      {r['reasoning'][:100]}...")
