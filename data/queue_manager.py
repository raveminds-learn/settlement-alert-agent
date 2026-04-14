"""
DuckDB fail queue manager.
Loads mock DTCC data into DuckDB for fast analytical queries.
Supports priority scoring, filtering, and status updates.
"""

import duckdb
import json
from datetime import datetime, date
from data.mock_dtcc import FAIL_QUEUE

DB_PATH = "./data/fail_queue.duckdb"


def get_connection():
    return duckdb.connect(DB_PATH)


def initialize_queue():
    """Load mock fail queue into DuckDB."""
    con = get_connection()

    con.execute("DROP TABLE IF EXISTS fails")
    con.execute("""
        CREATE TABLE fails (
            fail_id VARCHAR PRIMARY KEY,
            trade_ref VARCHAR,
            security VARCHAR,
            isin VARCHAR,
            asset_class VARCHAR,
            quantity BIGINT,
            price DOUBLE,
            notional DOUBLE,
            currency VARCHAR,
            counterparty VARCHAR,
            counterparty_lei VARCHAR,
            fail_date DATE,
            settlement_date DATE,
            direction VARCHAR,
            fail_reason TEXT,
            rule204_deadline DATE,
            days_failing INTEGER,
            daily_penalty DOUBLE,
            total_penalty_accrued DOUBLE,
            cascade_risk BOOLEAN,
            downstream_trades JSON,
            status VARCHAR,
            priority_score DOUBLE,
            recommended_action TEXT,
            agent_notes TEXT,
            human_decision VARCHAR,
            last_updated TIMESTAMP
        )
    """)

    for fail in FAIL_QUEUE:
        con.execute("""
            INSERT INTO fails VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, [
            fail["fail_id"],
            fail["trade_ref"],
            fail["security"],
            fail["isin"],
            fail["asset_class"],
            fail["quantity"],
            fail["price"],
            fail["notional"],
            fail["currency"],
            fail["counterparty"],
            fail["counterparty_lei"],
            fail["fail_date"],
            fail["settlement_date"],
            fail["direction"],
            fail["fail_reason"],
            fail["rule204_deadline"],
            fail["days_failing"],
            fail["daily_penalty"],
            fail["total_penalty_accrued"],
            fail["cascade_risk"],
            json.dumps(fail["downstream_trades"]),
            fail["status"],
            None,
            None,
            None,
            None,
            datetime.now(),
        ])

    con.close()
    print(f"Loaded {len(FAIL_QUEUE)} fails into DuckDB.")


def get_open_fails() -> list[dict]:
    """Get all open fails ordered by days failing descending."""
    con = get_connection()
    results = con.execute("""
        SELECT * FROM fails
        WHERE status IN ('OPEN', 'PARTIAL')
        ORDER BY days_failing DESC, notional DESC
    """).fetchdf()
    con.close()
    return results.to_dict(orient="records")


def get_critical_fails() -> list[dict]:
    """Get fails with Rule 204 deadline today or overdue."""
    con = get_connection()
    today = date.today()
    results = con.execute("""
        SELECT * FROM fails
        WHERE status IN ('OPEN', 'PARTIAL')
        AND rule204_deadline <= ?
        ORDER BY rule204_deadline ASC, notional DESC
    """, [today]).fetchdf()
    con.close()
    return results.to_dict(orient="records")


def get_fail_by_id(fail_id: str) -> dict:
    """Get a single fail by ID."""
    con = get_connection()
    result = con.execute(
        "SELECT * FROM fails WHERE fail_id = ?", [fail_id]
    ).fetchdf()
    con.close()
    if result.empty:
        return {}
    return result.to_dict(orient="records")[0]


def update_priority_score(fail_id: str, score: float, action: str, notes: str):
    """Update priority score and recommended action for a fail."""
    con = get_connection()
    con.execute("""
        UPDATE fails
        SET priority_score = ?,
            recommended_action = ?,
            agent_notes = ?,
            last_updated = ?
        WHERE fail_id = ?
    """, [score, action, notes, datetime.now(), fail_id])
    con.close()


def record_human_decision(fail_id: str, decision: str):
    """Record the human approval or rejection decision."""
    con = get_connection()
    status = "ACTIONED" if decision == "APPROVED" else "OPEN"
    con.execute("""
        UPDATE fails
        SET human_decision = ?,
            status = ?,
            last_updated = ?
        WHERE fail_id = ?
    """, [decision, status, datetime.now(), fail_id])
    con.close()


def get_queue_summary() -> dict:
    """Get high-level queue summary metrics."""
    con = get_connection()
    summary = con.execute("""
        SELECT
            COUNT(*) as total_open,
            SUM(notional) as total_exposure,
            SUM(total_penalty_accrued) as total_penalties,
            SUM(CASE WHEN rule204_deadline <= CURRENT_DATE THEN 1 ELSE 0 END) as rule204_critical,
            SUM(CASE WHEN cascade_risk = true THEN 1 ELSE 0 END) as cascade_risk_count,
            SUM(daily_penalty) as daily_penalty_run_rate
        FROM fails
        WHERE status IN ('OPEN', 'PARTIAL')
    """).fetchdf()
    con.close()
    return summary.to_dict(orient="records")[0]


if __name__ == "__main__":
    initialize_queue()
    summary = get_queue_summary()
    print(f"Queue summary: {summary}")
