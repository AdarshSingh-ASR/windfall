"""Seed scenarios: opportunities Windfall's scouts surface."""
from __future__ import annotations

SCENARIOS: dict[str, dict] = {
    "utility-discount": dict(
        kind="discount_program",
        source="Riverside Power & Light",
        title="LIDR: 20% monthly discount for households under 60% state median income",
        payload=dict(
            clerk_id="clerk-rpl-discounts",
            program="Low-Income Discount Rate",
            benefit="20% off monthly bill",
            window="rolling",
        ),
    ),
    "flight-delay": dict(
        kind="refund_rule",
        source="Meridian Air",
        title="Flight 2214 arrived 3h41m late — controllable delay, DOT compensation applies",
        payload=dict(
            clerk_id="clerk-airline-comp",
            flight="2214 RIV-DEN 2026-08-14",
            delay="3h41m",
            cause="crew scheduling",
        ),
    ),
    "unclaimed-property": dict(
        kind="unclaimed_property",
        source="State Controller",
        title="Dormant savings account ($318.40) matched to a former address of record",
        payload=dict(
            clerk_id="clerk-state-comptroller",
            amount=318.40,
            record_address="9 Corbin St, Riverside CA",
        ),
    ),
    "class-settlement": dict(
        kind="settlement",
        source="In re Riverside Water Rates Class Settlement",
        title="Water-rate overcharge settlement: $85-$140 per customer account, claims close soon",
        payload=dict(
            clerk_id="clerk-settlements-admin",
            class_period="2023-2025",
            deadline="2026-09-30",
        ),
    ),
}


def get(seed_id: str) -> dict:
    return SCENARIOS[seed_id]
