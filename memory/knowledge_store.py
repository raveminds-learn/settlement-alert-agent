"""
LanceDB institutional knowledge store.
Embeds counterparty resolution patterns so the agent can retrieve
relevant historical behaviour when reasoning about a fail.

This is the memory layer — institutional knowledge that never leaves
even when experienced ops staff do.
"""

import lancedb
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.counterparty_patterns import get_all_patterns

DB_PATH = os.path.join(os.path.dirname(__file__), "lancedb_store")
TABLE_NAME = "counterparty_knowledge"


def get_embedding(text: str) -> list:
    vec = [0.0] * 64
    for i, char in enumerate(text.lower()):
        vec[ord(char) % 64] += 1.0 / (i + 1)
    norm = sum(x**2 for x in vec) ** 0.5
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


def build_knowledge_text(pattern: dict) -> str:
    return (
        f"Counterparty: {pattern['counterparty']}. "
        f"Average resolution time: {pattern['avg_resolution_hours']} hours. "
        f"Best contact window: {pattern['best_contact_window']}. "
        f"Preferred channel: {pattern['preferred_channel']}. "
        f"Escalation threshold: ${pattern['escalation_threshold_usd']:,.0f}. "
        f"Accepts partial settlement: {pattern['partial_settlement_receptive']}. "
        f"Historical resolution rate: {pattern['resolution_rate_pct']}%. "
        f"Common fail reasons: {', '.join(pattern['common_fail_reasons'])}. "
        f"Operational notes: {pattern['notes']}"
    )


def initialise_knowledge_store():
    db = lancedb.connect(DB_PATH)
    patterns = get_all_patterns()
    records = []
    for pattern in patterns:
        text = build_knowledge_text(pattern)
        embedding = get_embedding(text)
        records.append({
            "counterparty": pattern["counterparty"],
            "lei": pattern["lei"],
            "text": text,
            "vector": embedding,
            "avg_resolution_hours": pattern["avg_resolution_hours"],
            "best_contact_window": pattern["best_contact_window"],
            "preferred_channel": pattern["preferred_channel"],
            "escalation_threshold_usd": float(pattern["escalation_threshold_usd"]),
            "partial_settlement_receptive": pattern["partial_settlement_receptive"],
            "resolution_rate_pct": float(pattern["resolution_rate_pct"]),
            "notes": pattern["notes"],
            "metadata": json.dumps({"common_fail_reasons": pattern["common_fail_reasons"]}),
        })
    if TABLE_NAME in db.table_names():
        db.drop_table(TABLE_NAME)
    table = db.create_table(TABLE_NAME, data=records)
    return table


def retrieve_counterparty_knowledge(counterparty: str) -> dict | None:
    try:
        db = lancedb.connect(DB_PATH)
        if TABLE_NAME not in db.table_names():
            initialise_knowledge_store()
            db = lancedb.connect(DB_PATH)
        table = db.open_table(TABLE_NAME)
        query_vec = get_embedding(f"counterparty resolution behaviour {counterparty}")
        results = (
            table.search(query_vec)
            .where(f"counterparty = '{counterparty}'")
            .limit(1)
            .to_list()
        )
        if results:
            r = results[0]
            metadata = json.loads(r.get("metadata", "{}"))
            return {
                "counterparty": r["counterparty"],
                "avg_resolution_hours": r["avg_resolution_hours"],
                "best_contact_window": r["best_contact_window"],
                "preferred_channel": r["preferred_channel"],
                "escalation_threshold_usd": r["escalation_threshold_usd"],
                "partial_settlement_receptive": r["partial_settlement_receptive"],
                "resolution_rate_pct": r["resolution_rate_pct"],
                "notes": r["notes"],
                "common_fail_reasons": metadata.get("common_fail_reasons", []),
            }
    except Exception as e:
        print(f"LanceDB retrieval error: {e}")
    return None


if __name__ == "__main__":
    print("Initialising LanceDB knowledge store...")
    initialise_knowledge_store()
    print("Done.")
    result = retrieve_counterparty_knowledge("Goldman Sachs")
    if result:
        print(f"Retrieved: {result['counterparty']} — {result['avg_resolution_hours']}h avg")
