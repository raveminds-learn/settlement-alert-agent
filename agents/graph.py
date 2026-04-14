"""
LangGraph Agentic Loop — RaveMinds Settlement Alert Agent
5 agents running in a continuous loop:
Monitor → Reason → Prioritise → Recommend → Await Approval → Execute → Loop
"""

import json
from datetime import date
from typing import TypedDict, Annotated
import operator

from langgraph.graph import StateGraph, END
import ollama

from data.queue_manager import (
    get_open_fails,
    get_critical_fails,
    get_queue_summary,
    update_priority_score,
    record_human_decision,
    get_fail_by_id,
)
from memory.knowledge_store import get_counterparty_profile

OLLAMA_MODEL = "mistral"


# ── State Schema ──────────────────────────────────────────────

class AgentState(TypedDict):
    fails: list[dict]
    critical_fails: list[dict]
    queue_summary: dict
    prioritised_fails: list[dict]
    recommendations: list[dict]
    pending_approvals: list[dict]
    approved_actions: list[dict]
    rejected_actions: list[dict]
    cycle_log: Annotated[list[str], operator.add]
    error: str | None


# ── Agent 1: Monitor ──────────────────────────────────────────

def monitor_agent(state: AgentState) -> AgentState:
    """
    Monitors the settlement fail queue continuously.
    Ingests all open fails and queue summary metrics.
    """
    try:
        fails = get_open_fails()
        critical_fails = get_critical_fails()
        summary = get_queue_summary()

        log_entry = (
            f"[MONITOR] Cycle complete. "
            f"Open fails: {len(fails)} | "
            f"Critical: {len(critical_fails)} | "
            f"Total exposure: ${summary.get('total_exposure', 0):,.0f} | "
            f"Daily penalty run rate: ${summary.get('daily_penalty_run_rate', 0):,.2f}"
        )

        return {
            **state,
            "fails": fails,
            "critical_fails": critical_fails,
            "queue_summary": summary,
            "cycle_log": [log_entry],
            "error": None,
        }
    except Exception as e:
        return {**state, "error": str(e), "cycle_log": [f"[MONITOR ERROR] {e}"]}


# ── Agent 2: Reason ───────────────────────────────────────────

def reason_agent(state: AgentState) -> AgentState:
    """
    Scores each fail across multiple dimensions:
    - Regulatory deadline proximity (Rule 204)
    - Financial penalty cost
    - Cascade risk
    - Counterparty resolution probability
    - Days failing
    """
    fails = state.get("fails", [])
    if not fails:
        return {**state, "cycle_log": ["[REASON] No open fails to score."]}

    today = date.today()
    scored_fails = []

    for fail in fails:
        score = 0.0

        # 1. Rule 204 deadline urgency (0-40 points)
        try:
            deadline = date.fromisoformat(str(fail.get("rule204_deadline", "")))
            days_to_deadline = (deadline - today).days
            if days_to_deadline < 0:
                score += 40  # Overdue — maximum urgency
            elif days_to_deadline == 0:
                score += 35  # Due today
            elif days_to_deadline == 1:
                score += 25  # Due tomorrow
            elif days_to_deadline == 2:
                score += 15  # Due in 2 days
            else:
                score += 5
        except Exception:
            score += 5

        # 2. Notional value / financial exposure (0-25 points)
        notional = float(fail.get("notional", 0))
        if notional >= 10000000:
            score += 25
        elif notional >= 5000000:
            score += 20
        elif notional >= 2000000:
            score += 15
        elif notional >= 1000000:
            score += 10
        else:
            score += 5

        # 3. Cascade risk (0-20 points)
        if fail.get("cascade_risk"):
            downstream = fail.get("downstream_trades", [])
            if isinstance(downstream, str):
                try:
                    downstream = json.loads(downstream)
                except Exception:
                    downstream = []
            score += min(20, 10 + len(downstream) * 3)

        # 4. Days failing (0-10 points)
        days_failing = int(fail.get("days_failing", 0))
        score += min(10, days_failing * 2)

        # 5. Counterparty resolution probability (0-5 points)
        profile = get_counterparty_profile(fail.get("counterparty", ""))
        if profile:
            fail_rate = float(profile.get("historical_fail_rate", 1.0))
            if fail_rate > 2.0:
                score += 5  # Slow counterparty — needs more urgency
            elif fail_rate > 1.0:
                score += 3
            else:
                score += 1

        fail["priority_score"] = round(score, 2)
        fail["counterparty_profile"] = profile
        scored_fails.append(fail)

    log_entry = f"[REASON] Scored {len(scored_fails)} fails. Top score: {max(f['priority_score'] for f in scored_fails):.1f}"

    return {
        **state,
        "fails": scored_fails,
        "cycle_log": [log_entry],
    }


# ── Agent 3: Prioritise ───────────────────────────────────────

def prioritise_agent(state: AgentState) -> AgentState:
    """
    Sorts fails by priority score descending.
    Persists scores to DuckDB.
    Returns top 5 for recommendation.
    """
    fails = state.get("fails", [])
    if not fails:
        return {**state, "cycle_log": ["[PRIORITISE] No fails to prioritise."]}

    sorted_fails = sorted(fails, key=lambda x: x.get("priority_score", 0), reverse=True)

    # Persist scores to DuckDB
    for fail in sorted_fails:
        update_priority_score(
            fail["fail_id"],
            fail.get("priority_score", 0),
            "",
            "",
        )

    top_fails = sorted_fails[:5]
    log_entry = (
        f"[PRIORITISE] Queue ranked. Top 5 fail IDs: "
        f"{[f['fail_id'] for f in top_fails]}"
    )

    return {
        **state,
        "prioritised_fails": top_fails,
        "cycle_log": [log_entry],
    }


# ── Agent 4: Recommend ────────────────────────────────────────

def recommend_agent(state: AgentState) -> AgentState:
    """
    For each top-priority fail, uses Mistral 7B to:
    - Determine the recommended action
    - Draft a counterparty communication
    - Explain the reasoning in plain English
    """
    prioritised_fails = state.get("prioritised_fails", [])
    if not prioritised_fails:
        return {**state, "cycle_log": ["[RECOMMEND] No prioritised fails."]}

    recommendations = []
    today = date.today()

    for fail in prioritised_fails:
        profile = fail.get("counterparty_profile", {})
        deadline = str(fail.get("rule204_deadline", ""))

        try:
            days_to_deadline = (date.fromisoformat(deadline) - today).days
        except Exception:
            days_to_deadline = 99

        prompt = f"""You are a senior settlements operations specialist at a US broker-dealer.
Analyze this settlement fail and provide a structured recommendation.

FAIL DETAILS:
- Fail ID: {fail['fail_id']}
- Security: {fail['security']} ({fail['asset_class']})
- Notional: ${fail['notional']:,.2f}
- Direction: {fail['direction']}
- Counterparty: {fail['counterparty']}
- Fail Reason: {fail['fail_reason']}
- Days Failing: {fail['days_failing']}
- Priority Score: {fail['priority_score']}
- Rule 204 Deadline: {deadline} ({days_to_deadline} days away)
- Cascade Risk: {fail['cascade_risk']}
- Accrued Penalties: ${fail['total_penalty_accrued']:,.2f}

COUNTERPARTY INTELLIGENCE:
- Avg Resolution Time: {profile.get('avg_resolution_hours', 'Unknown')} hours
- Best Contact Window: {profile.get('best_contact_window', 'Unknown')}
- Preferred Channel: {profile.get('preferred_channel', 'Unknown')}
- Partial Settlement Accepted: {profile.get('partial_settlement_accepted', 'Unknown')}
- Notes: {profile.get('notes', 'None')}

Respond ONLY with a valid JSON object in this exact format:
{{
  "action_type": "CHASE_COUNTERPARTY|PARTIAL_SETTLE|ESCALATE_INTERNAL|ESCALATE_TRADING_DESK|MONITOR_ONLY",
  "urgency": "CRITICAL|HIGH|MEDIUM|LOW",
  "plain_english_summary": "2-3 sentence explanation of what is happening and why this action is recommended",
  "draft_communication": "Ready-to-send message to counterparty or internal team",
  "escalation_contact": "Who to contact if this action is taken",
  "expected_resolution_hours": 4,
  "risk_if_no_action": "What happens if nothing is done"
}}"""

        try:
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.1},
            )
            raw = response["message"]["content"].strip()

            # Extract JSON from response
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                rec_data = json.loads(raw[start:end])
            else:
                raise ValueError("No JSON found in response")

        except Exception as e:
            rec_data = {
                "action_type": "MONITOR_ONLY",
                "urgency": "MEDIUM",
                "plain_english_summary": f"Unable to generate AI recommendation: {str(e)[:100]}",
                "draft_communication": "Manual review required.",
                "escalation_contact": "Settlements supervisor",
                "expected_resolution_hours": 8,
                "risk_if_no_action": "Fail may persist and accrue penalties.",
            }

        recommendation = {
            "fail_id": fail["fail_id"],
            "security": fail["security"],
            "counterparty": fail["counterparty"],
            "notional": fail["notional"],
            "priority_score": fail["priority_score"],
            "days_failing": fail["days_failing"],
            "rule204_deadline": deadline,
            "days_to_deadline": days_to_deadline,
            "cascade_risk": fail["cascade_risk"],
            "total_penalty_accrued": fail["total_penalty_accrued"],
            **rec_data,
        }
        recommendations.append(recommendation)

        # Persist recommendation to DuckDB
        update_priority_score(
            fail["fail_id"],
            fail["priority_score"],
            rec_data.get("action_type", ""),
            rec_data.get("plain_english_summary", ""),
        )

    log_entry = f"[RECOMMEND] Generated {len(recommendations)} recommendations."

    return {
        **state,
        "recommendations": recommendations,
        "pending_approvals": recommendations,
        "cycle_log": [log_entry],
    }


# ── Agent 5: Execute ──────────────────────────────────────────

def execute_agent(state: AgentState) -> AgentState:
    """
    Processes approved/rejected decisions.
    Records outcomes in DuckDB.
    Human approval happens in Streamlit UI — this agent
    processes decisions already made by the human.
    """
    approved = state.get("approved_actions", [])
    rejected = state.get("rejected_actions", [])

    executed = []
    for action in approved:
        fail_id = action.get("fail_id")
        record_human_decision(fail_id, "APPROVED")
        executed.append(fail_id)

    for action in rejected:
        fail_id = action.get("fail_id")
        record_human_decision(fail_id, "REJECTED")

    log_entry = (
        f"[EXECUTE] Approved: {len(approved)} actions executed. "
        f"Rejected: {len(rejected)} actions. "
        f"Fail IDs actioned: {executed}"
    )

    return {
        **state,
        "approved_actions": [],
        "rejected_actions": [],
        "cycle_log": [log_entry],
    }


# ── Build the Graph ───────────────────────────────────────────

def build_agent_graph():
    graph = StateGraph(AgentState)

    graph.add_node("monitor", monitor_agent)
    graph.add_node("reason", reason_agent)
    graph.add_node("prioritise", prioritise_agent)
    graph.add_node("recommend", recommend_agent)
    graph.add_node("execute", execute_agent)

    graph.set_entry_point("monitor")
    graph.add_edge("monitor", "reason")
    graph.add_edge("reason", "prioritise")
    graph.add_edge("prioritise", "recommend")
    graph.add_edge("recommend", "execute")
    graph.add_edge("execute", END)

    return graph.compile()


def run_agent_cycle(
    approved_actions: list = None,
    rejected_actions: list = None,
) -> AgentState:
    """Run one full cycle of the agentic loop."""
    graph = build_agent_graph()

    initial_state: AgentState = {
        "fails": [],
        "critical_fails": [],
        "queue_summary": {},
        "prioritised_fails": [],
        "recommendations": [],
        "pending_approvals": [],
        "approved_actions": approved_actions or [],
        "rejected_actions": rejected_actions or [],
        "cycle_log": [],
        "error": None,
    }

    result = graph.invoke(initial_state)
    return result


if __name__ == "__main__":
    from data.queue_manager import initialize_queue
    from memory.knowledge_store import seed_counterparty_knowledge

    print("Initializing queue...")
    initialize_queue()
    print("Seeding knowledge store...")
    seed_counterparty_knowledge()
    print("Running agent cycle...")
    result = run_agent_cycle()
    print("\n=== CYCLE LOG ===")
    for entry in result["cycle_log"]:
        print(entry)
    print("\n=== RECOMMENDATIONS ===")
    for rec in result["recommendations"]:
        print(f"\n{rec['fail_id']} | {rec['security']} | Score: {rec['priority_score']}")
        print(f"Action: {rec['action_type']} | Urgency: {rec['urgency']}")
        print(f"Summary: {rec['plain_english_summary']}")
