import datetime as dt
from types import SimpleNamespace as T

from app import recurring

D = dt.date


def txn(merchant, day, amount, category="Uncategorised", txn_type="debit", method="UPI"):
    return T(merchant=merchant, txn_date=day, amount=amount, category=category, txn_type=txn_type, method=method)


def by(result, merchant):
    return next(i for i in result["items"] if i["merchant"] == merchant)


def test_monthly_subscription_with_price_rise_and_next_date():
    rows = [txn("Netflix", D(2026, m, 14), a, "Entertainment") for m, a in ((1, 199), (2, 199), (3, 249))]
    r = recurring.detect(rows)
    n = by(r, "Netflix")
    assert (n["cadence"], n["kind"], n["confidence"]) == ("Monthly", "subscription", "high")
    assert n["price_change"] == {"from": 199, "to": 249, "diff": 50}
    assert n["next_date"] == (D(2026, 3, 14) + dt.timedelta(days=n["interval_days"])).isoformat()
    assert r["totals"]["price_rises"] == 1


def test_known_service_seen_once_is_likely():
    r = recurring.detect([txn("Netflix", D(2026, 1, 14), 199, "Entertainment"), txn("Shop", D(2026, 1, 30), 5)])
    n = by(r, "Netflix")
    assert n["confidence"] == "likely" and n["cadence"] == "Monthly" and "seen once" in n["reason"]


def test_unknown_merchant_seen_once_is_not_recurring():
    r = recurring.detect([txn("Random Shop", D(2026, 1, 3), 120)])
    assert r["items"] == []


def test_irregular_amounts_are_not_a_subscription():
    rows = [txn("Grocer", D(2026, m, 5), a) for m, a in ((1, 100), (2, 900), (3, 300))]
    assert recurring.detect(rows)["items"] == []


def test_weekly_cadence():
    rows = [txn("Milkman", D(2026, 1, 1) + dt.timedelta(days=7 * i), 300) for i in range(5)]
    assert by(recurring.detect(rows), "Milkman")["cadence"] == "Weekly"


def test_stopped_when_overdue():
    rows = [txn("Gym", D(2026, m, 1), 999) for m in (1, 2, 3)]
    rows.append(txn("Other", D(2026, 6, 30), 10))  # data runs to end of June
    assert by(recurring.detect(rows), "Gym")["status"] == "stopped"


def test_regular_transfer_and_income_kinds():
    rows = [txn("Ramesh K", D(2026, m, 10), 2000, "P2P Transfer") for m in (1, 2, 3)]
    rows += [txn("Infosys (Salary)", D(2026, m, 1), 50000, "Income", "credit") for m in (1, 2, 3)]
    r = recurring.detect(rows)
    assert by(r, "Ramesh K")["kind"] == "transfer"
    assert by(r, "Infosys (Salary)")["kind"] == "income" and by(r, "Infosys (Salary)")["direction"] == "in"
    assert r["totals"]["transfers"] == 2000 and r["totals"]["income"] == 50000


def test_frequent_places_are_listed_separately():
    rows = [txn("Tea Stall", D(2026, 1, d), 15 + d % 3) for d in (2, 3, 7, 9, 15, 16, 22)]
    r = recurring.detect(rows)
    assert r["items"] == [] and r["frequent"][0]["merchant"] == "Tea Stall" and r["frequent"][0]["count"] == 7


def test_sip_and_ach_mandate():
    r = recurring.detect([txn("Groww SIP", D(2026, 1, 7), 5000, "Investments", method="INB"),
                          txn("Bajaj Finance", D(2026, 1, 5), 3200, method="ACH")])
    assert by(r, "Groww SIP")["kind"] == "investment" and by(r, "Bajaj Finance")["kind"] == "emi"
    assert r["totals"]["investments"] == 5000
