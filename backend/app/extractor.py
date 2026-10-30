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
    except pikepdf.PdfError:
        return False  # not a readable PDF; decrypt_to_bytes reports it


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
    except pikepdf.PdfError:
        raise ValueError("This file isn't a readable PDF.")


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

    @classmethod
    def from_dict(cls, d: dict) -> "ParsedTxn":
        return cls(**{**d, "txn_date": dt.date.fromisoformat(d["txn_date"]),
                      "amount": Decimal(d["amount"]), "balance": Decimal(d["balance"])})


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


@dataclass
class Layout:
    """What the extractor reads from a statement: every table (rows of cells) and the page text."""
    tables: list[list[list[str | None]]]
    text: str


def read_pdf(pdf_bytes: bytes) -> Layout:
    tables, text = [], []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            tables.extend(page.extract_tables())
            text.append(page.extract_text() or "")
    return Layout(tables=tables, text="\n".join(text))


def _unwrap(cell: str | None) -> str:
    """Rejoin a cell the PDF wrapped onto several lines. SBI breaks at spaces when it can
    and mid-word when it can't, so glue the pieces back without a space when the break
    sits inside a word ("Swigg|y"), inside a run of digits, or next to a '/'."""
    lines = [ln.strip() for ln in (cell or "").split("\n") if ln.strip()]
    out = lines[0] if lines else ""
    for ln in lines[1:]:
        a, b = out[-1], ln[0]
        glue = (a == "/" or b == "/" or (a.islower() and b.islower())
                or (a.isdigit() and b.isdigit()))
        out += ("" if glue else " ") + ln
    return out


def rows_from_tables(tables: list[list[list[str | None]]]) -> list[dict]:
    rows = []
    for table in tables:
        for r in table:
            cells = [_unwrap(c) for c in r]
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
# "UPI/DR/<ref>/<payee name>/<payee bank>/<payee VPA>/<note>", with or without a
# "TO TRANSFER-" / "WDL TFR" lead-in
_UPI = re.compile(r"UPI/(?:DR|CR)/\d+/(?P<name>[^/]*)/(?P<bank>[^/]*)/(?P<vpa>[^/]*)", re.I)
_NEFT = re.compile(r"TRANSFER-NEFT\*\d+\*([^*]+)\*", re.I)
# Google Pay personal handles, when the statement shows the full VPA
_PERSON_VPA = re.compile(r"@ok(sbi|hdfcbank|axis|icici)$", re.I)
# Real SBI statements append "<ref> AT <branch code> <branch name>" and prefix "WDL TFR"/"DEP TFR"
_SBI_TRAILER = re.compile(r"\s+\d{9,}\s+AT\s+\d+(\s+.*)?$", re.I)
_SBI_LEAD = re.compile(r"^(WDL|DEP)\s+[A-Z]{2,4}\s+(?=\S*/)", re.I)

# every category the pipeline can assign; the Review screen offers these
CATEGORIES = [
    "Food & Dining", "Groceries", "Shopping", "Bills & Utilities", "Entertainment",
    "Transport", "Insurance", "Cash", "Bank Fees",
    "Investments", "Income", "Cashback", "Transfer · Person", "Uncategorised",
]

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
    "netflix": ("Netflix", "Entertainment"),
    "spotify india": ("Spotify", "Entertainment"),
    "spotify": ("Spotify", "Entertainment"),
    "hotstar": ("Disney+ Hotstar", "Entertainment"),
    "youtube": ("YouTube", "Entertainment"),
    "bookmyshow": ("BookMyShow", "Entertainment"),
    "flipkart": ("Flipkart", "Shopping"),
    "myntra": ("Myntra", "Shopping"),
    "meesho": ("Meesho", "Shopping"),
    "ajio": ("AJIO", "Shopping"),
    "bigbasket": ("BigBasket", "Groceries"),
    "instamart": ("Swiggy Instamart", "Groceries"),
    "dmart": ("DMart", "Groceries"),
    "avenue supermarts": ("DMart", "Groceries"),
    "dominos": ("Domino's", "Food & Dining"),
    "mcdonalds": ("McDonald's", "Food & Dining"),
    "starbucks": ("Starbucks", "Food & Dining"),
    "airtel": ("Airtel", "Bills & Utilities"),
    "bsnl": ("BSNL", "Bills & Utilities"),
    "tata play": ("Tata Play", "Bills & Utilities"),
    "ola": ("Ola", "Transport"),
    "rapido": ("Rapido", "Transport"),
    "irctc": ("IRCTC", "Transport"),
    "zerodha": ("Zerodha", "Investments"),
    "upstox": ("Upstox", "Investments"),
    "lic": ("LIC", "Insurance"),
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
    # space-insensitive, because wrapped narrations gain or lose spaces ("SWIGG Y", "BUNDLTECH");
    # short tokens ("lic", "ola", "cred") must be whole words or they'd hit "click", "cola"
    squashed = key.replace(" ", "")
    for token, (merch, cat) in rules.items():
        flat = token.replace(" ", "")
        hit = (flat in squashed if len(flat) >= 5
               else re.search(rf"\b{re.escape(token)}\b", key))
        if hit:
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
    method, merchant, category, kind = _normalise(desc, rules)
    # a rule keyed on the cleaned merchant name (what a user correction writes) has the
    # final say, whichever narration token or branch produced that merchant
    hit = rules.get(_clean(merchant))
    if hit and hit[0] == merchant:
        category = hit[1]
    return method, merchant, category, kind


def _upi_kind(vpa: str) -> str:
    """Person or merchant, from the payee VPA. Real SBI statements drop the '@handle',
    leaving only the local part; a 10-digit phone number there is a person. Anything else
    counts as a merchant, so ambiguous payments stay in spend rather than vanishing into
    transfers."""
    local, _, handle = vpa.strip().partition("@")
    if handle:
        return "person" if _PERSON_VPA.search(vpa.strip()) else "merchant"
    return "person" if re.fullmatch(r"\d{10}", local) else "merchant"


def _upi(d: str, rules: dict) -> tuple[str, str, str, str] | None:
    m = _UPI.search(d)
    if not m:
        return None
    name, vpa = m.group("name").strip(), m.group("vpa").strip()
    kind = _upi_kind(vpa)
    if kind == "person":
        return "UPI", (name or vpa).title(), "Transfer · Person", kind
    if not name or name.isdigit():  # some payees show only a number; fall back to the VPA
        name = vpa or "UPI payment"
    merch, cat = _match(name, rules)
    if cat == "Uncategorised" and vpa:  # "netflix.pg", "zomato-order" ...
        hit = _match(vpa.replace(".", " ").replace("-", " "), rules)
        if hit[1] != "Uncategorised":
            merch, cat = hit
    return "UPI", merch, cat, kind


def _normalise(desc: str, rules: dict) -> tuple[str, str, str, str]:
    d = _SBI_LEAD.sub("", _SBI_TRAILER.sub("", desc.strip()))
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

    upi = _upi(d, rules)
    if upi:
        return upi

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
    return parse_tables(read_pdf(pdf_bytes).tables, rules)


def parse_tables(tables: list[list[list[str | None]]], rules: dict | None = None) -> list[ParsedTxn]:
    out = []
    for r in rows_from_tables(tables):
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


def opening_from_first_row(txns: list[ParsedTxn]) -> Decimal:
    """Back the opening balance out of the first row, when the statement doesn't state it."""
    t = txns[0]
    return t.balance - t.amount if t.txn_type == "credit" else t.balance + t.amount


def balance_check(txns: list[ParsedTxn], opening: Decimal, closing: Decimal | None = None) -> dict:
    """opening + credits - debits must equal closing. Pass the statement's own closing
    figure when it has one: comparing against the last row's balance can't catch a
    missing last row."""
    credits = sum((t.amount for t in txns if t.txn_type == "credit"), Decimal(0))
    debits = sum((t.amount for t in txns if t.txn_type == "debit"), Decimal(0))
    expected = opening + credits - debits
    if closing is None:
        closing = txns[-1].balance if txns else opening
    return {
        "opening": str(opening), "credits": str(credits), "debits": str(debits),
        "expected_closing": str(expected), "statement_closing": str(closing),
        "reconciles": abs(expected - closing) < Decimal("0.01"),
        "difference": str(expected - closing),
    }


_SIGNED = r"([\d,]+\.\d{2})\s*(CR|DR)?"


def _signed(amount: str, side: str | None) -> Decimal:
    v = _money(amount)
    return -v if (side or "").upper() == "DR" else v


def statement_summary(text: str) -> dict:
    """Opening and closing balance as the statement states them (None when absent).
    Real SBI: a 'Statement Summary' whose header row ('Brought Forward ... Closing Balance')
    sits above a row of figures, the first being the opening and the last the closing.
    Older layout: 'Opening Balance : N' / 'Closing Balance : N' in the header."""
    out = {"opening": None, "closing": None}
    m = re.search(r"Brought Forward.*?Closing Balance[^\n]*\n\s*([^\n]+)", text, re.I | re.S)
    if m:
        figures = re.findall(_SIGNED, m.group(1), re.I)
        if len(figures) >= 2:
            out["opening"], out["closing"] = _signed(*figures[0]), _signed(*figures[-1])
            return out
    for key, label in (("opening", "Opening Balance"), ("closing", "Closing Balance")):
        m = re.search(label + r"\s*:?\s*" + _SIGNED, text, re.I)
        if m:
            out[key] = _signed(m.group(1), m.group(2))
    return out
