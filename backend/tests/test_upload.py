from conftest import preview, UNLOCKED


def test_locked_pdf_needs_password(client):
    assert preview(client, password=None).status_code == 422
    assert preview(client, password="WRONG").status_code == 401


def test_unlocked_pdf_needs_no_password(client):
    assert preview(client, path=UNLOCKED, password=None).status_code == 200


def test_preview_saves_nothing(client):
    r = preview(client)
    assert r.status_code == 200
    body = r.json()
    assert body["parsed"] > 0 and body["balance_check"]["reconciles"]
    assert body["duplicates"] == 0
    assert client.get("/transactions").json() == []
    assert client.get("/auth/me").json()["onboarded"] is False


def test_commit_saves_and_onboards(client):
    p = preview(client).json()
    r = client.post("/upload/commit", json={"token": p["token"]})
    assert r.status_code == 200
    assert r.json()["saved"] == p["parsed"]
    assert len(client.get("/transactions").json()) == p["parsed"]
    assert client.get("/auth/me").json()["onboarded"] is True


def test_reupload_is_all_duplicates(client):
    client.post("/upload/commit", json={"token": preview(client).json()["token"]})
    p = preview(client).json()
    assert p["duplicates"] == p["parsed"]
    r = client.post("/upload/commit", json={"token": p["token"]}).json()
    assert r["saved"] == 0 and r["duplicates"] == p["parsed"]


def test_correction_applies_and_is_learned(client):
    p = preview(client).json()
    # one merchant per counterparty kind: seed-token merchants, people, ATM/fees all must learn
    picks = {r["counterparty_kind"]: r["merchant"] for r in p["rows"]}
    assert {"merchant", "person"} <= picks.keys()
    corrections = {m: "Shopping" for m in picks.values()}
    client.post("/upload/commit", json={"token": p["token"], "corrections": corrections})

    saved = [t for t in client.get("/transactions").json() if t["merchant"] in corrections]
    assert saved and all(t["category"] == "Shopping" for t in saved)

    again = preview(client).json()  # rules learned -> next parse uses them
    assert all(r["category"] == "Shopping" for r in again["rows"] if r["merchant"] in corrections)


def test_correction_for_unknown_merchant_rejected(client):
    p = preview(client).json()
    r = client.post("/upload/commit", json={"token": p["token"], "corrections": {"Nobody": "Shopping"}})
    assert r.status_code == 422
    assert client.get("/transactions").json() == []


def test_tampered_token_rejected(client):
    token = preview(client).json()["token"]
    assert client.post("/upload/commit", json={"token": token[:-4] + "AAAA"}).status_code == 400


def test_delete_upload_removes_its_rows(client):
    client.post("/upload/commit", json={"token": preview(client).json()["token"]})
    [u] = client.get("/uploads").json()
    assert u["saved"] > 0 and u["reconciles"]

    assert client.delete(f"/uploads/{u['id']}").json()["removed"] == u["saved"]
    assert client.get("/transactions").json() == []
    assert client.get("/uploads").json() == []
    assert client.get("/auth/me").json()["onboarded"] is False
    assert client.delete(f"/uploads/{u['id']}").status_code == 404


def test_recategorise_missing_txn_is_404(client):
    r = client.patch("/transactions/nope/category", json={"category": "Shopping"})
    assert r.status_code == 404


def test_transaction_filters(client):
    client.post("/upload/commit", json={"token": preview(client).json()["token"]})
    every = client.get("/transactions?limit=1000").json()
    out = client.get("/transactions?type=debit&limit=1000").json()
    people = client.get("/transactions?kind=person&limit=1000").json()
    assert out and all(t["type"] == "debit" for t in out)
    assert people and all(t["kind"] == "person" for t in people)
    assert len(every) == len(out) + len(client.get("/transactions?type=credit&limit=1000").json())
    assert all("balance" in t for t in every)
    assert client.get("/transactions?type=sideways").status_code == 422
