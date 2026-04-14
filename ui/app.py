"""
RaveMinds Settlement Alert Agent — Ops Workbench
RaveMinds Series 2, Project 2

Streamlit interface for the ops analyst.
Not a chat box — a workbench.
The agent runs, surfaces recommendations, the analyst approves or rejects.
"""

import streamlit as st
import sys
import os
import pandas as pd
from datetime import datetime
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.agent_loop import run_agent_cycle_with_progress, get_initial_state
from memory.knowledge_store import initialise_knowledge_store

st.set_page_config(
    page_title="RaveMinds Settlement Alert Agent — RaveMinds",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #f6f8fb; }
[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #d9e2ef; }
.fail-card { background:#ffffff; border:1px solid #d9e2ef; border-radius:8px; padding:16px; margin-bottom:12px; border-left:4px solid #8aa1bf; }
.fail-card.critical { border-left-color:#ef4444; }
.fail-card.urgent   { border-left-color:#f97316; }
.fail-card.warning  { border-left-color:#eab308; }
.fail-card.normal   { border-left-color:#3b82f6; }
.badge { display:inline-block; padding:2px 10px; border-radius:12px; font-size:11px; font-weight:600; margin-right:4px; }
.badge-red    { background:#fee2e2; color:#991b1b; }
.badge-orange { background:#ffedd5; color:#9a3412; }
.badge-yellow { background:#fef9c3; color:#854d0e; }
.badge-blue   { background:#dbeafe; color:#1e3a8a; }
.badge-green  { background:#dcfce7; color:#166534; }
.badge-gray   { background:#e5e7eb; color:#374151; }
.draft-comm { background:#f8fbff; border:1px solid #d9e2ef; border-radius:6px; padding:12px 16px; font-family:monospace; font-size:13px; color:#334155; margin:10px 0; }
.audit-row { font-size:12px; color:#334155; border-bottom:1px solid #e2e8f0; padding:6px 0; }
.section-hdr { font-size:11px; font-weight:600; letter-spacing:1.5px; color:#64748b; text-transform:uppercase; margin:20px 0 10px; }
.agent-flow-wrap { background:#ffffff; border:1px solid #d9e2ef; border-radius:10px; padding:14px; margin-bottom:14px; }
.agent-flow { display:flex; align-items:center; flex-wrap:wrap; gap:8px; margin-top:8px; }
.agent-node { background:#eef4ff; color:#1e3a8a; border:1px solid #bfd2f5; border-radius:8px; padding:8px 10px; font-size:12px; font-weight:600; }
.agent-arrow { color:#64748b; font-weight:700; font-size:13px; }
div[data-testid="stButton"] > button[kind="primary"] {
  background-color:#16a34a;
  color:#ffffff;
  border:1px solid #15803d;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
  background-color:#15803d;
  border-color:#166534;
}
div[data-testid="stButton"] > button[kind="secondary"] {
  background-color:#dc2626;
  color:#ffffff;
  border:1px solid #b91c1c;
}
div[data-testid="stButton"] > button[kind="secondary"]:hover {
  background-color:#b91c1c;
  border-color:#991b1b;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "agent_state"     not in st.session_state: st.session_state.agent_state = None
if "audit_log"       not in st.session_state: st.session_state.audit_log = []
if "all_decisions"   not in st.session_state: st.session_state.all_decisions = []
if "kb_ready"        not in st.session_state: st.session_state.kb_ready = False
if "cycle_count"     not in st.session_state: st.session_state.cycle_count = 0
if "cycle_requested" not in st.session_state: st.session_state.cycle_requested = False
if "last_decision"   not in st.session_state: st.session_state.last_decision = None

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚡ RaveMinds Settlement Alert Agent")
    st.markdown("<div style='font-size:11px;color:#475569;margin-bottom:20px'>RaveMinds Series 2 · Project 2<br>Autonomous Agents · Human in the Loop</div>", unsafe_allow_html=True)
    st.markdown('<div class="section-hdr">Agent Controls</div>', unsafe_allow_html=True)

    if not st.session_state.kb_ready:
        if st.button("🔧 Initialise Knowledge Store", use_container_width=True, type="primary"):
            with st.spinner("Loading counterparty knowledge into LanceDB..."):
                initialise_knowledge_store()
                st.session_state.kb_ready = True
            st.success("Knowledge store ready")
            st.rerun()
    else:
        st.success("✅ Knowledge store loaded")

    st.markdown("")
    is_running = st.session_state.cycle_requested
    run_label = "⏳ Agent Running" if is_running else "▶ Run Agent Cycle"
    run_btn = st.button(
        run_label,
        use_container_width=True,
        disabled=(not st.session_state.kb_ready) or is_running,
        type="primary",
    )

    st.markdown("")
    st.markdown('<div class="section-hdr">Session Stats</div>', unsafe_allow_html=True)
    s = st.session_state.agent_state
    if s:
        queue = s.get("prioritised_queue", [])
        st.metric("Open Fails", len(queue))
        st.metric("Critical (Rule 204)", sum(1 for f in queue if f.get("deadline_status") in ("EXPIRED","TODAY")))
        st.metric("Pending Approval", len([r for r in s.get("recommendations",[]) if r["status"]=="PENDING"]))
        st.metric("Daily Exposure", f"${sum(f.get('estimated_penalty_per_day',0) for f in queue):,.0f}")
        st.metric("Agent Cycles", st.session_state.cycle_count)
        approvals = len([d for d in st.session_state.all_decisions if d.get("decision") == "APPROVED"])
        rejections = len([d for d in st.session_state.all_decisions if d.get("decision") == "REJECTED"])
        st.metric("Approved Actions", approvals)
        st.metric("Rejected Actions", rejections)
    else:
        for label in ["Open Fails","Critical (Rule 204)","Pending Approval","Daily Exposure"]:
            st.metric(label, "—")

    st.markdown("")
    st.markdown('<div class="section-hdr">Audit Log</div>', unsafe_allow_html=True)
    for entry in reversed(st.session_state.audit_log[-20:]):
        st.markdown(f"<div class='audit-row'><b>{entry.get('agent','—')}</b> · {entry.get('action','')[:50]}</div>", unsafe_allow_html=True)

# ── Run cycle ─────────────────────────────────────────────────────────────────
if run_btn and not st.session_state.cycle_requested:
    st.session_state.cycle_requested = True
    st.rerun()

if st.session_state.cycle_requested:
    status_box = st.empty()
    progress_bar = st.progress(0)
    flow_box = st.empty()
    run_idx = st.session_state.cycle_count + 1

    def render_agent_flow(active_step: int = 0, completed_step: int = 0):
        labels = ["Monitor", "Reason", "Prioritise", "Recommend", "Execute"]
        parts = []
        for i, label in enumerate(labels, start=1):
            if i <= completed_step:
                parts.append(f"✅ {label}")
            elif i == active_step:
                parts.append(f"🔄 {label}")
            else:
                parts.append(f"⏳ {label}")
        flow_box.markdown(" **Agent progress:** " + "  →  ".join(parts))

    status_box.info(f"Running agent cycle {run_idx}...")
    render_agent_flow(active_step=1)

    current = st.session_state.agent_state or get_initial_state()
    current["approved_actions"] = []
    current["rejected_actions"] = []

    def on_progress(agent_name: str, step_index: int, total_steps: int):
        status_box.info(f"Cycle {run_idx}: Agent {step_index}/{total_steps} in progress — {agent_name}")
        progress_bar.progress(step_index / total_steps)
        render_agent_flow(active_step=step_index, completed_step=step_index - 1)
        time.sleep(0.15)

    new_state = run_agent_cycle_with_progress(current, on_progress)
    new_state["recommendations"] = [r for r in new_state.get("recommendations",[]) if r["status"]=="PENDING"]
    st.session_state.agent_state = new_state
    st.session_state.audit_log.extend(new_state.get("audit_log",[]))
    st.session_state.cycle_count += 1
    st.session_state.cycle_requested = False
    render_agent_flow(completed_step=5)
    status_box.success(f"Cycle {run_idx} complete.")
    progress_bar.progress(1.0)
    time.sleep(0.2)
    st.rerun()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("<h1 style='color:#0f172a;font-size:24px;font-weight:600;margin-bottom:4px'>⚡ RaveMinds Settlement Alert Agent</h1><div style='color:#64748b;font-size:13px;margin-bottom:24px'>Proactive fail management · T+1 US Markets · Human-in-the-Loop</div>", unsafe_allow_html=True)

if not st.session_state.agent_state:
    st.info("👈 Start by initialising the knowledge store, then run the first agent cycle.")
    st.stop()

state = st.session_state.agent_state
tab1, tab2, tab3 = st.tabs(["🔴 Recommendations", "📋 Fail Queue", "📊 Agent Reasoning"])

# ── Tab 1: Recommendations ────────────────────────────────────────────────────
with tab1:
    last = st.session_state.last_decision
    if last:
        msg = f"{last['decision']} — {last['fail_id']} ({last['security']})"
        if last["decision"] == "APPROVED":
            st.success(msg)
        else:
            st.error(msg)

    recs = [r for r in state.get("recommendations",[]) if r["status"]=="PENDING"]
    if not recs:
        st.success("No pending recommendations. Run the agent to generate new ones.")
    else:
        st.markdown(f"<div style='color:#475569;font-size:13px;margin-bottom:16px'>{len(recs)} recommendation(s) awaiting your approval.</div>", unsafe_allow_html=True)

    for i, rec in enumerate(recs):
        deadline = rec.get("deadline_status","UPCOMING")
        card_cls = {"EXPIRED":"critical","TODAY":"urgent","TOMORROW":"warning"}.get(deadline,"normal")
        b_cls,b_txt = {"EXPIRED":("badge-red","EXPIRED"),"TODAY":("badge-orange","TODAY"),"TOMORROW":("badge-yellow","TOMORROW"),"UPCOMING":("badge-blue","UPCOMING")}.get(deadline,("badge-gray",deadline))
        a_cls,a_txt = {"ESCALATE_TO_TRADING_DESK":("badge-red","ESCALATE"),"URGENT_COUNTERPARTY_CHASE":("badge-orange","URGENT CHASE"),"PARTIAL_SETTLEMENT":("badge-yellow","PARTIAL SETTLE"),"PRIORITY_COUNTERPARTY_CHASE":("badge-yellow","PRIORITY CHASE"),"COUNTERPARTY_CHASE":("badge-blue","CHASE"),"MONITOR_AND_CHASE":("badge-gray","MONITOR")}.get(rec["action_type"],("badge-gray",rec["action_type"]))

        st.markdown(f"<div class='fail-card {card_cls}'>", unsafe_allow_html=True)
        c1,c2,c3 = st.columns([3,2,1])
        with c1:
            st.markdown(f"<div style='font-size:16px;font-weight:600;color:#0f172a'>{rec['fail_id']} — {rec['security']}</div><div style='font-size:12px;color:#64748b;margin-top:2px'>{rec['counterparty']} · ${rec['notional']:,.0f}</div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<span class='badge {b_cls}'>{b_txt}</span><span class='badge {a_cls}'>{a_txt}</span>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div style='text-align:right;color:#475569;font-size:13px'>Score: <b>{rec['priority_score']}</b></div>", unsafe_allow_html=True)

        with st.expander("View reasoning & draft communication"):
            st.markdown("<div style='color:#64748b;font-size:12px;line-height:1.7'>" + "<br>".join(f"→ {r}" for r in rec["reasoning"].split(" | ")) + "</div>", unsafe_allow_html=True)
            st.markdown("<div style='color:#475569;font-size:11px;margin-top:12px;margin-bottom:4px'>DRAFT COMMUNICATION</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='draft-comm'>{rec['draft_communication']}</div>", unsafe_allow_html=True)

        ca, cr, _ = st.columns([1,1,4])
        with ca:
            if st.button("✅ Approve", key=f"app_{rec['fail_id']}_{i}", type="primary"):
                rec["status"] = "APPROVED"
                rec["approved_at"] = datetime.now().isoformat()
                st.session_state.all_decisions.append({**rec,"decision":"APPROVED"})
                st.session_state.last_decision = {"decision": "APPROVED", "fail_id": rec["fail_id"], "security": rec["security"]}
                st.toast(f"Approved {rec['fail_id']}", icon="✅")
                st.session_state.audit_log.append({"agent":"Human","timestamp":datetime.now().isoformat(),"action":f"APPROVED {rec['fail_id']} — {rec['action_type']}"})
                state["recommendations"] = [r for r in state["recommendations"] if r["fail_id"]!=rec["fail_id"]]
                st.rerun()
        with cr:
            if st.button("❌ Reject", key=f"rej_{rec['fail_id']}_{i}"):
                rec["status"] = "REJECTED"
                rec["rejected_at"] = datetime.now().isoformat()
                st.session_state.all_decisions.append({**rec,"decision":"REJECTED"})
                st.session_state.last_decision = {"decision": "REJECTED", "fail_id": rec["fail_id"], "security": rec["security"]}
                st.toast(f"Rejected {rec['fail_id']}", icon="❌")
                st.session_state.audit_log.append({"agent":"Human","timestamp":datetime.now().isoformat(),"action":f"REJECTED {rec['fail_id']} — {rec['action_type']}"})
                state["recommendations"] = [r for r in state["recommendations"] if r["fail_id"]!=rec["fail_id"]]
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.all_decisions:
        st.markdown('<div class="section-hdr">Decision History</div>', unsafe_allow_html=True)
        for d in reversed(st.session_state.all_decisions[-10:]):
            icon = "✅" if d["decision"]=="APPROVED" else "❌"
            ts = d.get("approved_at") or d.get("rejected_at","")
            st.markdown(f"<div class='audit-row'>{icon} {d['fail_id']} — {d['security']} — {d['action_type']} · {ts[:16]}</div>", unsafe_allow_html=True)

# ── Tab 2: Fail Queue ─────────────────────────────────────────────────────────
with tab2:
    queue = state.get("prioritised_queue",[])
    if not queue:
        st.info("Run the agent to populate the fail queue.")
    else:
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Total Fails", len(queue))
        m2.metric("Critical / Urgent", sum(1 for f in queue if f.get("deadline_status") in ("EXPIRED","TODAY")))
        m3.metric("Daily Exposure", f"${sum(f.get('estimated_penalty_per_day',0) for f in queue):,.0f}")
        m4.metric("High Cascade Risk", sum(1 for f in queue if f.get("cascade_risk")=="HIGH"))

        df = pd.DataFrame([{
            "Rank": f["queue_rank"],
            "Fail ID": f["fail_id"],
            "Security": f["security"],
            "Side": f["side"],
            "Notional ($)": f"{f['notional']:,.0f}",
            "Counterparty": f["counterparty"],
            "Age": f"{f['fail_age_days']}d",
            "Deadline": f["deadline_status"],
            "Cascade": f["cascade_risk"],
            "Penalty/Day": f"${f['estimated_penalty_per_day']:,.0f}",
            "Score": f["priority_score"],
        } for f in queue])
        st.dataframe(df, use_container_width=True, hide_index=True)

# ── Tab 3: Agent Reasoning ────────────────────────────────────────────────────
with tab3:
    st.markdown("<div style='color:#64748b;font-size:13px;margin-bottom:16px'>How the agent scores each fail — five dimensions of autonomous prioritisation.</div>", unsafe_allow_html=True)
    st.markdown("##### Agent Linkage Map")
    st.markdown("""
    <div class='agent-flow-wrap'>
      <div style='color:#334155;font-size:13px'>
        One cycle follows this linked flow. Human decisions shape the next run.
      </div>
      <div class='agent-flow'>
        <span class='agent-node'>1. Monitor</span>
        <span class='agent-arrow'>→</span>
        <span class='agent-node'>2. Reason</span>
        <span class='agent-arrow'>→</span>
        <span class='agent-node'>3. Prioritise</span>
        <span class='agent-arrow'>→</span>
        <span class='agent-node'>4. Recommend</span>
        <span class='agent-arrow'>→</span>
        <span class='agent-node'>Human Approval</span>
        <span class='agent-arrow'>→</span>
        <span class='agent-node'>5. Execute</span>
        <span class='agent-arrow'>→</span>
        <span class='agent-node'>Next Cycle</span>
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("##### Priority Scoring Model")
    st.dataframe(pd.DataFrame({
        "Dimension": ["Regulatory urgency","Financial cost","Cascade risk","Age of fail","Resolution ease"],
        "Max Points": [40, 25, 20, 10, 5],
        "What it measures": [
            "Days to Rule 204 closeout deadline",
            "Estimated penalty per day in USD",
            "Risk of blocking downstream settlements",
            "How long the fail has been open",
            "Counterparty historical resolution rate",
        ],
    }), use_container_width=True, hide_index=True)

    st.markdown("")
    st.markdown("##### Top 5 Scored Fails This Cycle")
    for fail in state.get("prioritised_queue",[])[:5]:
        knowledge = fail.get("counterparty_knowledge")
        with st.expander(f"#{fail['queue_rank']} {fail['fail_id']} — {fail['security']} (Score: {fail['priority_score']})"):
            c1,c2,c3 = st.columns(3)
            c1.metric("Regulatory Urgency", fail.get("deadline_status","—"))
            c2.metric("Daily Penalty", f"${fail.get('estimated_penalty_per_day',0):,.0f}")
            c3.metric("Cascade Risk", fail.get("cascade_risk","—"))
            if knowledge:
                st.markdown(f"**Counterparty Intel — {knowledge['counterparty']}**  \nAvg resolution: {knowledge['avg_resolution_hours']}h · Best window: {knowledge['best_contact_window']} · Success rate: {knowledge['resolution_rate_pct']}%  \n_{knowledge['notes']}_")
