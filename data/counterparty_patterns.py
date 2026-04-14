"""
Counterparty institutional knowledge.
Behavioural patterns encoded from historical resolution experience.
This is the knowledge that lives in experienced ops heads — now in LanceDB.
"""

COUNTERPARTY_PATTERNS = [
    {
        "counterparty": "Goldman Sachs",
        "lei": "784F5XWPLTWKTBV3E584",
        "avg_resolution_hours": 3.5,
        "best_contact_window": "Before 10am EST",
        "preferred_channel": "Direct ops line",
        "escalation_threshold_usd": 5000000,
        "partial_settlement_receptive": True,
        "common_fail_reasons": ["Securities not located in time", "Late allocation"],
        "resolution_rate_pct": 87,
        "notes": "Goldman ops desk is responsive before 10am. After 10am escalate to VP level. They accept partial on equities above 10k shares. Always cc their compliance team on fails over $5m.",
    },
    {
        "counterparty": "Morgan Stanley",
        "lei": "9R7GPTSO7KV3URCAE383",
        "avg_resolution_hours": 6.0,
        "best_contact_window": "9am-11am EST",
        "preferred_channel": "Email with phone follow-up",
        "escalation_threshold_usd": 3000000,
        "partial_settlement_receptive": False,
        "common_fail_reasons": ["Collateral recall delays", "DTC account mismatch"],
        "resolution_rate_pct": 72,
        "notes": "Morgan Stanley requires email first then phone call. They do not accept partial settlement on bonds under any circumstances. Fails over $3m require VP escalation same day. Resolution typically takes 6+ hours.",
    },
    {
        "counterparty": "Citi",
        "lei": "E57ODZWZ7FF32TWEFA76",
        "avg_resolution_hours": 8.0,
        "best_contact_window": "8am-9am EST",
        "preferred_channel": "SWIFT MT599 free format message",
        "escalation_threshold_usd": 10000000,
        "partial_settlement_receptive": True,
        "common_fail_reasons": ["Wrong DTC account", "Funding gaps"],
        "resolution_rate_pct": 65,
        "notes": "Citi ops desk is slow to respond. Best results with SWIFT message plus phone. They frequently instruct wrong DTC accounts — always verify account number before chasing. Partial settlement accepted for ETFs above 5k lots.",
    },
    {
        "counterparty": "JP Morgan",
        "lei": "7H6GLXDRUGQFU57RNE97",
        "avg_resolution_hours": 4.0,
        "best_contact_window": "Any time before 2pm EST",
        "preferred_channel": "Direct phone to ops desk",
        "escalation_threshold_usd": 7500000,
        "partial_settlement_receptive": True,
        "common_fail_reasons": ["Funding gaps", "DTC participant issues"],
        "resolution_rate_pct": 81,
        "notes": "JP Morgan has a dedicated fails desk that is highly responsive. Phone call directly resolves most issues within 4 hours. They accept partial settlement on equities and ETFs. Escalate to Director level for fails over $7.5m.",
    },
    {
        "counterparty": "Citadel Securities",
        "lei": "549300IBKPAS7SDXUR27",
        "avg_resolution_hours": 2.0,
        "best_contact_window": "Any time during market hours",
        "preferred_channel": "Direct ops line",
        "escalation_threshold_usd": 20000000,
        "partial_settlement_receptive": True,
        "common_fail_reasons": ["Funding gaps", "Short locate issues"],
        "resolution_rate_pct": 94,
        "notes": "Citadel Securities has the fastest resolution of any counterparty. Their ops desk is automated and highly efficient. Most fails resolve within 2 hours of contact. Partial settlement always accepted. Escalation rarely needed.",
    },
    {
        "counterparty": "Barclays",
        "lei": "G5GSEF7VJP5I7OUK5573",
        "avg_resolution_hours": 10.0,
        "best_contact_window": "8am-9am EST (London overlap)",
        "preferred_channel": "Email to fails management team",
        "escalation_threshold_usd": 5000000,
        "partial_settlement_receptive": False,
        "common_fail_reasons": ["Fedwire issues", "Cross-border settlement delays"],
        "resolution_rate_pct": 58,
        "notes": "Barclays has frequent Fedwire connectivity issues. Best to contact during London-New York overlap (8-9am EST). They do not accept partial settlement. Resolution is slow — average 10 hours. Escalate to Head of Settlement Ops for fails over $5m. Consider NSCC buy-in process early for aging Barclays fails.",
    },
    {
        "counterparty": "Virtu Financial",
        "lei": "549300L0PPKZGQXBL260",
        "avg_resolution_hours": 5.0,
        "best_contact_window": "10am-12pm EST",
        "preferred_channel": "Email with trade reference",
        "escalation_threshold_usd": 15000000,
        "partial_settlement_receptive": True,
        "common_fail_reasons": ["AML holds", "Compliance review delays"],
        "resolution_rate_pct": 76,
        "notes": "Virtu fails are frequently AML-related and require compliance clearance — these cannot be expedited by ops contact alone. Email the fails team with full trade details. Partial settlement accepted in most cases. AML-related fails often take 24+ hours regardless of escalation.",
    },
]


def get_counterparty_pattern(counterparty: str):
    return next(
        (p for p in COUNTERPARTY_PATTERNS if p["counterparty"] == counterparty), None
    )


def get_all_patterns():
    return COUNTERPARTY_PATTERNS
