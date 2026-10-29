"""Khaata — SBI statement extractor.

Pipeline:  decrypt (pikepdf) -> extract table (pdfplumber) -> parse rows
           -> normalise SBI narration into method + merchant + category
           -> balance check (opening + credits - debits == closing)

Add a new bank by writing another narration normaliser and table reader;
everything downstream (storage, insights) is bank-agnostic.
"""
from __future__ import annotations
import io, re, datetime as dt
from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation

import pikepdf
import pdfplumber


# --------------------------------------------------------------------------- #
# 1. Decrypt
# --------------------------------------------------------------------------- #
def is_encrypted(path_or_bytes) -> bool:
    try:
        src = io.BytesIO(path_or_bytes) if isinstance(path_or_bytes, (bytes, bytearray)) else path_or_bytes
        with pikepdf.open(src):
            return False
    except pikepdf.PasswordError:
        return True


def decrypt_to_bytes(path_or_bytes, password: str | None) -> bytes:
    """Open a (possibly encrypted) PDF and return decrypted bytes in memory.
    The password is used once here and never persisted."""
    src = io.BytesIO(path_or_bytes) if isinstance(path_or_bytes, (bytes, bytearray)) else path_or_bytes
    try:
        with pikepdf.open(src, password=password or "") as pdf:
            buf = io.BytesIO()
            pdf.save(buf)
            return buf.getvalue()
    except pikepdf.PasswordError:
        raise ValueError("Wrong or missing password for this PDF.")


# --------------------------------------------------------------------------- #
# 2. Data model
# --------------------------------------------------------------------------- #
@dataclass
class ParsedTxn:
    txn_date: dt.date
    raw_narration: str
    txn_type: str          # debit / credit
    amount: Decimal        # positive magnitude
    balance: Decimal
    merchant: str
    category: str
    method: str            # UPI / NEFT / ATM / ACH / INB / FEE / OTHER
    counterparty_kind: str # merchant / person / self / bank

    def as_dict(self):
        d = asdict(self)
        d["txn_date"] = self.txn_date.isoformat()
        d["amount"] = f"{self.amount:.2f}"
        d["balance"] = f"{self.balance:.2f}"
        return d


# --------------------------------------------------------------------------- #
# 3. Extract rows from the PDF table
# --------------------------------------------------------------------------- #
_DATE = re.compile(r"^\d{1,2}[\s/-][A-Za-z0-9]{2,3}[\s/-]\d{2,4}$")


def _money(s: str) -> Decimal | None:
    s = (s or "").strip().replace(",", "")
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _parse_date(s: str) -> dt.date:
    for fmt in ("%d %b %Y", "%d-%b-%Y", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date: {s!r}")


def extract_rows(pdf_bytes: bytes) -> list[dict]:
    rows = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for r in table:
                    cells = [(c or "").strip().replace("\n", " ") for c in r]
                    if len(cells) < 7:
                        continue
                    txn_date, _value_date, desc, ref, debit, credit, balance = cells[:7]
                    if not _DATE.match(txn_date):
                        continue
                    rows.append({"date": txn_date, "desc": desc, "ref": ref,
                                 "debit": debit, "credit": credit, "balance": balance})
    return rows


# --------------------------------------------------------------------------- #
# 4. Normalise SBI narration
# --------------------------------------------------------------------------- #
_UPI = re.compile(r"TRANSFER-UPI/(?:DR|CR)/\d+/([^/]+)/[^/]*/([^/]+)/", re.I)
_NEFT = re.compile(r"TRANSFER-NEFT\*\d+\*([^*]+)\*", re.I)
_PERSON_VPA = re.compile(r"@ok(sbi|hdfcbank|axis|icici)$", re.I)

# seed dictionary: cleaned-token -> (merchant, category). Grows from user corrections.
SEED_RULES = {
    "swiggy": ("Swiggy", "Food & Dining"),
    "bundl technologies": ("Swiggy", "Food & Dining"),
    "zomato": ("Zomato", "Food & Dining"),
    "clicktech retail": ("Amazon", "Shopping"),
    "amazon": ("Amazon", "Shopping"),
    "zepto": ("Zepto", "Groceries"),
    "blinkit": ("Blinkit", "Groceries"),
    "more supermarket": ("More", "Groceries"),
    "reliance jio": ("Jio", "Bills & Utilities"),
    "netflix entmnt": ("Netflix", "Entertainment"),
    "spotify india": ("Spotify", "Entertainment"),
    "bescom": ("BESCOM", "Bills & Utilities"),
    "uber india": ("Uber", "Transport"),
    "groww": ("Groww SIP", "Investments"),
    "hdfc life insurance premium": ("HDFC Life", "Insurance"),
    "infosys ltd": ("Infosys (Salary)", "Income"),
    "cred": ("CRED", "Cashback"),
}


def _clean(token: str) -> str:
    return re.sub(r"\s+", " ", token).strip().lower()


def _match(name: str, rules: dict) -> tuple[str, str]:
    key = _clean(name)
    if key in rules:
        return rules[key]
    for token, (merch, cat) in rules.items():
        if token in key:
            return merch, cat
    try:
        from rapidfuzz import process, fuzz
        hit = process.extractOne(key, rules.keys(), scorer=fuzz.token_sort_ratio)
        if hit and hit[1] >= 88:
            return rules[hit[0]]
    except Exception:
        pass
    return name.strip().title(), "Uncategorised"


def normalise(desc: str, rules: dict | None = None) -> tuple[str, str, str, str]:
    """Return (method, merchant, category, counterparty_kind)."""
    rules = rules or SEED_RULES
    d = desc.strip()
    up = d.upper()

    if up.startswith(("ATM WDL", "ATM CASH")):
        return "ATM", "ATM Withdrawal", "Cash", "self"
    if "SMS CHARGES" in up or "CHARGES INCL GST" in up:
        return "FEE", "SBI Charges", "Bank Fees", "bank"
    if "ACH" in up:
        m = re.search(r"ACH/\d+/(.+)$", d, re.I)
        name = m.group(1).strip() if m else d
        merch, cat = _match(name, rules)
        return "ACH", merch, cat, "merchant"

    mu = _UPI.search(d)
    if mu:
        name, vpa = mu.group(1), mu.group(2)
        kind = "person" if _PERSON_VPA.search(vpa) else "merchant"
        merch, cat = _match(name, rules)
        if kind == "person":
            merch, cat = name.strip().title(), "Transfer · Person"
        return "UPI", merch, cat, kind

    mn = _NEFT.search(d)
    if mn:
        merch, cat = _match(mn.group(1), rules)
        return "NEFT", merch, cat, "merchant"

    if up.startswith("TO TRANSFER-INB"):
        m = re.search(r"INB/\d+/([^/]+)", d, re.I)
        name = m.group(1).strip() if m else d
        merch, cat = _match(name, rules)
        return "INB", merch, cat, "merchant"

    return "OTHER", d[:40], "Uncategorised", "merchant"


# --------------------------------------------------------------------------- #
# 5. Assemble + balance check
# --------------------------------------------------------------------------- #
def parse(pdf_bytes: bytes, rules: dict | None = None) -> list[ParsedTxn]:
    out = []
    for r in extract_rows(pdf_bytes):
        debit, credit, balance = _money(r["debit"]), _money(r["credit"]), _money(r["balance"])
        if balance is None or (debit is None and credit is None):
            continue
        txn_type = "debit" if debit is not None else "credit"
        amount = debit if debit is not None else credit
        method, merchant, category, kind = normalise(r["desc"], rules)
        out.append(ParsedTxn(
            txn_date=_parse_date(r["date"]), raw_narration=r["desc"],
            txn_type=txn_type, amount=amount, balance=balance,
            merchant=merchant, category=category, method=method, counterparty_kind=kind,
        ))
    return out


def balance_check(txns: list[ParsedTxn], opening: Decimal) -> dict:
    credits = sum((t.amount for t in txns if t.txn_type == "credit"), Decimal(0))
    debits = sum((t.amount for t in txns if t.txn_type == "debit"), Decimal(0))
    expected = opening + credits - debits
    closing = txns[-1].balance if txns else opening
    return {
        "opening": str(opening), "credits": str(credits), "debits": str(debits),
        "expected_closing": str(expected), "statement_closing": str(closing),
        "reconciles": abs(expected - closing) < Decimal("0.01"),
        "difference": str(expected - closing),
    }


def extract_opening(pdf_bytes: bytes) -> Decimal | None:
    """Read the 'Opening Balance : N' line from the statement header, if present."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = pdf.pages[0].extract_text() or ""
    m = re.search(r"Opening Balance\s*:?\s*([\d,]+\.\d{2})", text, re.I)
    return _money(m.group(1)) if m else None
