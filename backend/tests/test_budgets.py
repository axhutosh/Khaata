import datetime as dt

from app import insights
from app.database import SessionLocal
from conftest import preview


def _spend(txns, category, month):
    return sum(t["amount"] for t in txns
               if t["category"] == category and t["type"] == "debit" and t["date"].startswith(month))


def _setup(client):
    client.post("/upload/commit", json={"token": preview(client).json()["token"]})
    txns = client.get("/transactions").json()
    category = next(t["category"] for t in txns if t["type"] == "debit" and t["category"] == "Food & Dining")
    client.put("/budgets", json={"category": category, "monthly_limit": 100000})
    return txns, category


def test_budget_uses_latest_month_not_all_time(client):
    txns, category = _setup(client)
    body = client.get("/budgets").json()
    latest = max(t["date"] for t in txns)[:7]
    assert body["month"] == latest
    [item] = body["items"]
    assert item["used"] == _spend(txns, category, latest)
    assert body["overall"]["used"] == item["used"]


def test_budget_for_explicit_month(client):
    txns, category = _setup(client)
    earliest = min(t["date"] for t in txns)[:7]
    [item] = client.get(f"/budgets?month={earliest}").json()["items"]
    assert item["used"] == _spend(txns, category, earliest)
    assert client.get("/budgets?month=2026-1").status_code == 422


def test_projection_is_linear_in_current_month(client):
    txns, _ = _setup(client)
    latest = max(t["date"] for t in txns)[:7]
    start = dt.date.fromisoformat(latest + "-01")
    with SessionLocal() as db:
        user_id = db.execute(insights.Transaction.__table__.select()).first().user_id
        past = insights.budget_status(db, user_id, latest, today=start + dt.timedelta(days=60))
        mid = insights.budget_status(db, user_id, latest, today=start.replace(day=10))
    item_past, item_mid = past["items"][0], mid["items"][0]
    assert item_past["projected"] == item_past["used"]
    end_day = ((start + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)).day
    assert item_mid["projected"] == round(item_mid["used"] * end_day / 10, 2)
