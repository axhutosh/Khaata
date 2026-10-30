"""With open sign-up, every account must be sealed off from every other one."""
from fastapi.testclient import TestClient

from app.main import app
from conftest import creds, preview


def _sign_in(c, email, _):
    assert c.post("/auth/signup", json=creds(email=email)).status_code == 200


def test_users_cannot_see_or_touch_each_others_data(anon):
    a = anon
    _sign_in(a, "alice@gmail.com", "a-1")
    token = preview(a).json()["token"]
    assert a.post("/upload/commit", json={"token": token}).status_code == 200
    a.put("/budgets", json={"category": "Food & Dining", "monthly_limit": 5000})
    a_txns = a.get("/transactions?limit=1000").json()
    a_txn = a_txns[0]
    a.patch(f"/transactions/{a_txn['id']}/category", json={"category": "Education"})
    [a_upload] = a.get("/uploads").json()

    with TestClient(app) as b:
        _sign_in(b, "bob@gmail.com", "b-1")
        # sees nothing of Alice's
        assert b.get("/transactions?limit=1000").json() == []
        assert b.get("/uploads").json() == []
        assert b.get("/insights/overview").json() == {"period": "month", "empty": True}
        assert b.get("/insights/recurring").json()["items"] == []
        assert b.get("/budgets").json()["items"] == []
        # can't change or delete Alice's things, even knowing their ids
        assert b.patch(f"/transactions/{a_txn['id']}/category", json={"category": "Shopping"}).status_code == 404
        assert b.delete(f"/uploads/{a_upload['id']}").status_code == 404
        # can't replay Alice's upload preview into his own account
        assert b.post("/upload/commit", json={"token": token}).status_code == 403
        # his own reclassify and budget don't reach her rows or budgets
        b.post("/transactions/reclassify")
        b.put("/budgets", json={"category": "Food & Dining", "monthly_limit": 1})
        # Bob uploading the same statement gets his own copy, not "duplicates" of hers
        r = b.post("/upload/commit", json={"token": preview(b).json()["token"]}).json()
        assert r["saved"] == len(a_txns) and r["duplicates"] == 0
        # and Alice's learned rule (-> Education) didn't leak into his categories
        assert {t["category"] for t in b.get("/transactions?limit=1000").json() if t["merchant"] == a_txn["merchant"]} != {"Education"}

    # Alice is untouched
    assert len(a.get("/transactions?limit=1000").json()) == len(a_txns)
    assert {t["category"] for t in a.get("/transactions?limit=1000").json() if t["merchant"] == a_txn["merchant"]} == {"Education"}
    assert a.get("/budgets").json()["items"][0]["limit"] == 5000
    assert len(a.get("/uploads").json()) == 1
