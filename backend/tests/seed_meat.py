import httpx

body = {
    "kind": "logistics",
    "title": "Regional food bank offers 400 kg of frozen meat - needs -18C freezer transport today or it is destroyed",
    "payload": {
        "quantity_kg": 400,
        "contents": "frozen meat, must stay at -18C",
        "deadline": "today 18:00",
        "note": "coordinator pre-approved $140 spend for a commercial refrigerated courier",
        "approved_spend_usd": 140,
    },
}
r = httpx.post("http://127.0.0.1:8001/api/events", json=body, timeout=30)
print(r.json())
