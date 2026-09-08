"""Seed scenarios: the living event stream of the Riverside Food Network."""
from __future__ import annotations

SCENARIOS: dict[str, dict] = {
    "surplus-sunday": dict(
        kind="donation_offer",
        title="Greenfield Farms: 140 kg surplus produce after Sunday market",
        payload=dict(
            donor="donor-greenfield",
            quantity_kg=140,
            window="today 15:00-18:00 pickup",
            contents="mixed produce: greens, tomatoes, squash, stone fruit",
            receipt_needed=True,
        ),
    ),
    "fridge-short": dict(
        kind="logistics",
        title="Hope Pantry cold fridge nearly full; 60 kg of dairy arriving from regional food bank",
        payload=dict(
            destination="pantry-hope",
            quantity_kg=60,
            contents="dairy: milk, yogurt, cheese",
            arrive_by="tomorrow 09:00",
            problem="only 25 kg cold capacity left; dairy spoils in 48h without cold chain",
        ),
    ),
    "surge-storm": dict(
        kind="surge_need",
        title="Storm shelter request: 300 hot meals tonight, usual kitchen at half staff",
        payload=dict(
            requester="partner-foodbank",
            meals_needed=300,
            deadline="tonight 19:00",
            complication="St. Mary's can cook but two volunteer drivers cancelled; shelter is 22 min away",
        ),
    ),
    "driver-no-show": dict(
        kind="volunteer_cancel",
        title="Priya cancelled tonight's pickup run — 90 kg of bakery rescue will be missed",
        payload=dict(
            run="bakery rescue, Tue 18:30, 90 kg from three bakeries",
            cancelled_by="volunteer-priya",
            backup="volunteer-marco (mornings only, truck)",
            fallback="partner-rideshare voucher ($18/run, 2h lead)",
        ),
    ),
}


def get(seed_id: str) -> dict:
    return SCENARIOS[seed_id]
