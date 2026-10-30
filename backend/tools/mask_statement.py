"""Mask a real bank statement so its layout can be shared without personal data.

    python tools/mask_statement.py samples/real/statement.pdf
    python tools/mask_statement.py samples/real/statement.xlsx    (also .xls)

Prompts for the PDF password (never stored, never echoed). Writes, next to the PDF:
  <name>.masked.json  - what the extractor sees: per page, the text lines, the tables
                        (row by row, cell by cell) and word positions, all masked
  <name>.masked.txt   - the same, readable, for you to check before sharing

Kept as-is: dates, amounts/balances (needed for the balance check), SBI layout
keywords (TRANSFER, UPI, NEFT, Opening Balance, ...) and well-known business names
(SWIGGY, ZEPTO, ...). Everything else is masked with the same length and shape:
letters -> X/x, digits -> 9. So names, account numbers, UPI IDs, reference numbers,
IFSC, address, email and phone all become placeholders.

Read the .txt before sharing. If something private is still visible, it's a bug here:
don't share, say so. If a business name you're happy to show got masked, re-run with
--keep WORD,WORD.
"""
from __future__ import annotations

import argparse
import getpass
import io
import json
import pathlib
import re
import sys

import pdfplumber
import pikepdf

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app import extractor  # noqa: E402  (spreadsheet reader)

# Layout and transaction-type words SBI statements use. Case-insensitive.
LAYOUT_WORDS = """
state bank of india sbi statement account accounts acct a/c details summary period from to page of
number
date txn value description narration particulars ref no cheque chq debit credit withdrawal withdrawals
deposit deposits balance opening closing total totals brought forward carried amount amt dr cr
transfer upi neft imps rtgs ach nach ecs inb atm wdl cash pos card debitcard pur purchase payment
charges charge sms gst incl int interest tds reversal rev refund return failed by mandate emi loan
sip nfs chg fee fees annual maintenance mab amc ser service tax cess clearing inward outward bulk
dep cdm csh self rs inr customer branch ifsc micr cif type nominee registered address email mobile
phone name currency available effective drawing power limit status as on generated computer this
is a does not require signature the and for in at with on you your please note any account-holder
jan feb mar apr may jun jul aug sep oct nov dec january february march april june july august
september october november december
""".split()

# Businesses, not people: useful for categorisation rules. Extend with --keep.
BUSINESS_WORDS = """
swiggy bundl technologies zomato amazon clicktech retail flipkart myntra meesho ajio nykaa zepto
blinkit grofers bigbasket dmart more supermarket reliance jio airtel vodafone vi bsnl tata play
netflix spotify hotstar disney prime youtube google apple microsoft uber ola rapido irctc makemytrip
redbus indigo bescom msedcl tneb electricity gas water insurance hdfc life lic icici prudential
bajaj allianz groww zerodha upstox kuvera paytm phonepe cred mutual fund infosys tcs wipro salary
""".split()

# UPI handle suffixes reveal the payer app/bank, which separates people from merchants.
VPA_HANDLES = """
oksbi okhdfcbank okaxis okicici ybl ibl axl paytm upi apl yapl sbi axisbank hdfcbank icici
""".split()

# money always carries paise in SBI statements; bare integers (PIN, house no.) get masked
AMOUNT = re.compile(r"^-?(\d{1,3}(,\d{2,3})*|\d+)\.\d{2}(\s?(Dr|Cr))?$", re.I)
MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()
# separators may differ when a cell wraps ("01 Jul\n2026")
DATE_ANY = re.compile(
    r"\b(\d{1,2})[\s/-](\d{1,2}|[A-Za-z]{3,9})[\s/-]+(\d{4}|\d{2})\b|\b(\d{4})-(\d{2})-(\d{2})\b")
YEAR = re.compile(r"^(19|20)\d{2}$")  # a lone year from a wrapped date reveals nothing


def _is_date(m: re.Match) -> bool:
    if m.group(4):
        y, mo, d = int(m.group(4)), int(m.group(5)), int(m.group(6))
    else:
        d, mo_s, y = int(m.group(1)), m.group(2), int(m.group(3))
        if mo_s.isdigit():
            mo = int(mo_s)
        elif mo_s[:3].lower() in MONTHS:
            mo = MONTHS.index(mo_s[:3].lower()) + 1
        else:
            return False
        y += 2000 if y < 100 else 0
    return 1 <= d <= 31 and 1 <= mo <= 12 and 1990 <= y <= 2100


def _shape(s: str) -> str:
    return re.sub(r"[A-Z]", "X", re.sub(r"[a-z]", "x", re.sub(r"\d", "9", s)))


class Masker:
    def __init__(self, keep: set[str]):
        self.keep = keep
        self.masked = 0
        self.visible: set[str] = set()

    def _token(self, tok: str) -> str:
        if not tok:
            return tok
        if AMOUNT.match(tok) or YEAR.match(tok):
            return tok
        if tok.lower() in self.keep:
            self.visible.add(tok.upper())
            return tok
        if any(c.isalnum() for c in tok):
            self.masked += 1
        return _shape(tok)

    def text(self, s: str | None) -> str | None:
        if s is None:
            return None
        # dates ("05 Jul 2026", "01-07-2026") span split characters; protect real ones first
        dates = {}
        def _stash(m):
            if not _is_date(m):
                return m.group(0)
            key = f"\x00{len(dates)}\x00"
            dates[key] = m.group(0)
            return key
        s = DATE_ANY.sub(_stash, s)

        def _part(p: str) -> str:
            if "\x00" in p:
                return p
            if "@" in p:  # email or UPI ID: mask the person part, keep a known handle
                local, _, handle = p.partition("@")
                h = handle.lower().strip(".,/)")
                return _shape(local) + "@" + (handle if h in VPA_HANDLES else _shape(handle))
            if AMOUNT.match(p):
                return p
            return "".join(self._token(t) for t in re.split(r"([^A-Za-z0-9,.]+|[.,](?!\d))", p))

        out = "".join(_part(p) for p in re.split(r"(\s+|/|\*|-(?=[A-Za-z]))", s))
        for key, val in dates.items():
            out = out.replace(key, val)
        return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pdf", type=pathlib.Path)
    ap.add_argument("--keep", default="", help="extra words to leave visible, comma-separated")
    args = ap.parse_args()

    data = args.pdf.read_bytes()
    extra = {w.strip().lower() for w in args.keep.split(",") if w.strip()}
    m = Masker(set(LAYOUT_WORDS) | set(BUSINESS_WORDS) | extra)

    if data[:5] != b"%PDF-":  # spreadsheet: dump every raw row, so the real columns show
        try:
            rows = extractor.sheet_rows(data)
        except Exception as e:
            print(f"Couldn't read this file: {e}", file=sys.stderr)
            return 1
        masked = [[m.text(c) for c in r] for r in rows]
        pages = [{"number": 1, "kind": "sheet", "size": None, "lines": [" | ".join(r) for r in masked],
                  "tables": [masked], "words": []}]
        return write(args.pdf, pages, m)

    password = ""
    try:
        pikepdf.open(io.BytesIO(data)).close()
    except pikepdf.PasswordError:
        password = getpass.getpass("PDF password (not shown, not stored): ")
    try:
        with pikepdf.open(io.BytesIO(data), password=password) as pdf:
            buf = io.BytesIO()
            pdf.save(buf)
    except pikepdf.PasswordError:
        print("Wrong password.", file=sys.stderr)
        return 1
    del password

    pages = []
    with pdfplumber.open(io.BytesIO(buf.getvalue())) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append({
                "number": page.page_number,
                "size": [round(page.width, 1), round(page.height, 1)],
                "lines": [m.text(line) for line in text.splitlines()],
                "tables": [[[m.text(c) for c in row] for row in table] for table in page.extract_tables()],
                "words": [{"text": m.text(w["text"]), "x0": round(w["x0"], 1), "x1": round(w["x1"], 1),
                           "top": round(w["top"], 1)} for w in page.extract_words()],
            })

    return write(args.pdf, pages, m)


def write(src: pathlib.Path, pages: list, m: Masker) -> int:
    stem = src.with_suffix("")
    json_path = stem.with_name(stem.name + ".masked.json")
    txt_path = stem.with_name(stem.name + ".masked.txt")
    json_path.write_text(json.dumps({"source": "masked", "pages": pages}, ensure_ascii=False, indent=1),
                         encoding="utf-8")

    with txt_path.open("w", encoding="utf-8") as f:
        for p in pages:
            f.write(f"===== page {p['number']} — text =====\n")
            f.write("\n".join(p["lines"]) + "\n")
            for i, table in enumerate(p["tables"], 1):
                f.write(f"\n----- page {p['number']} — table {i} ({len(table)} rows) -----\n")
                for row in table:
                    f.write(" | ".join((c or "").replace("\n", "⏎") for c in row) + "\n")
            f.write("\n")
        f.write("===== words left visible (check these) =====\n")
        f.write(", ".join(sorted(m.visible)) + "\n")

    print(f"Pages: {len(pages)} · tables: {sum(len(p['tables']) for p in pages)} · "
          f"tokens masked: {m.masked}")
    print(f"Words left visible: {', '.join(sorted(m.visible)) or '(none)'}")
    print(f"\nWrote {txt_path}\n      {json_path}")
    print("Open the .txt and check nothing private is visible before sharing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
