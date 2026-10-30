from conftest import preview


def _overview(client, period="month"):
    client.post("/upload/commit", json={"token": preview(client).json()["token"]})
    return client.get(f"/insights/overview?period={period}").json()


def test_empty_overview(client):
    assert client.get("/insights/overview").json()["empty"] is True


def test_money_in_and_out_add_up(client):
    o = _overview(client)
    txns = client.get("/transactions?limit=1000").json()
    k = o["kpis"]
    assert round(k["money_in"], 2) == round(sum(t["amount"] for t in txns if t["type"] == "credit"), 2)
    assert round(k["money_out"], 2) == round(sum(t["amount"] for t in txns if t["type"] == "debit"), 2)
    assert round(sum(f["amount"] for f in o["flows_out"]), 2) == round(k["money_out"], 2)
    assert round(sum(f["amount"] for f in o["flows_in"]), 2) == round(k["money_in"], 2)
    assert round(sum(b["money_out"] for b in o["buckets"]), 2) == round(k["money_out"], 2)
    assert k["p2p_sent"] == next(f["amount"] for f in o["flows_out"] if f["key"] == "people")


def test_people_weekday_balance_and_notes(client):
    o = _overview(client)
    assert all(p["sent"] + p["received"] > 0 for p in o["people"])
    assert [w["day"] for w in o["weekday"]] == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    assert round(sum(w["amount"] for w in o["weekday"]), 2) == round(o["kpis"]["spent"], 2)
    assert o["balance"] and o["low_balance"]["balance"] == min(b["balance"] for b in o["balance"])
    assert o["balance"][-1]["balance"] == 549381.53  # sample's stated closing balance
    assert o["largest"] == sorted(o["largest"], key=lambda x: -x["amount"])
    assert o["noticed"] and all(n["tone"] in ("info", "warn", "good") for n in o["noticed"])


def test_reclassify_keeps_user_corrections(client):
    _overview(client)
    t = next(t for t in client.get("/transactions").json() if t["kind"] == "merchant")
    client.patch(f"/transactions/{t['id']}/category", json={"category": "Education"})
    client.post("/transactions/reclassify")
    after = [x for x in client.get("/transactions?limit=1000").json() if x["merchant"] == t["merchant"]]
    assert after and all(x["category"] == "Education" for x in after)
