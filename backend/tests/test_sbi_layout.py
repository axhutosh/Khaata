"""The real SBI statement layout (account-statement download, 2026).

Rows here are made up but copy the real structure cell for cell: dd/mm/yyyy dates, '-' in
empty columns, descriptions wrapped across lines (sometimes mid-word), a "WDL TFR"/"DEP TFR"
lead-in, "<ref> AT <branch code> <branch>" trailer, VPAs without their @handle, and the
Statement Summary at the end. Real (masked) statements in samples/real/ are tested too,
but only locally: that folder is never committed.
"""
import json
import pathlib
from decimal import Decimal

import pytest

from app import extractor

TRAILER = "0097681162021 AT 00123\nKORAMANGALA"
HEADER = [None, None, None, None, None, None, "Balance"]
TABLE = [
    HEADER,
    ["01/01/2026", "01/01/2026", f"WDL TFR\nUPI/DR/600112233441/Ramesh\nK/YESB/paytm.s1ab/UPI\n{TRAILER}",
     "-", "20.00", "-", "434.94"],
    ["02/01/2026", "02/01/2026", f"WDL TFR\nUPI/DR/600112233442/Swigg\ny/YESB/swiggy.stores/UPI\n{TRAILER}",
     "-", "34.94", "-", "400.00"],
    ["06/01/2026", "06/01/2026", f"DEP TFR\nUPI/CR/600112233443/Priya\nS/SBIN/9876543210/Sent\n{TRAILER}",
     "-", "-", "2,000.00", "2,400.00"],
    ["07/01/2026", "07/01/2026", f"WDL TFR\nUPI/DR/600112233444/Priya\nS/SBIN/9876543210/UPI\n{TRAILER}",
     "-", "500.00", "-", "1,900.00"],
    ["14/01/2026", "14/01/2026", f"WDL TFR\nUPI/DR/600112233445/Netflix/utib\n0/netflix.pg/Recur\n{TRAILER}",
     "-", "199.00", "-", "1,701.00"],
    ["15/01/2026", "15/01/2026", f"WDL TFR\nUPI/DR/600112233446/87654321\n/YESB/q123456789/UPI\n{TRAILER}",
     "-", "1.00", "-", "1,700.00"],
    [None, None, None, None, None, None, None],
]
TEXT = """Statement From :01-01-2026 to 31-01-2026
Statement Summary : 01-01-2026 To 31-01-2026
Brought Forward( ) Dr Count Cr Count Total Debits( ) Total Credits( ) Closing Balance( )
454.94CR 5 1 754.94 2,000.00 1,700.00CR
"""


def _parse():
    return extractor.parse_tables([TABLE])


def test_every_row_is_read():
    txns = _parse()
    assert len(txns) == 6
    assert [t.txn_type for t in txns] == ["debit", "debit", "credit", "debit", "debit", "debit"]
    assert txns[2].amount == Decimal("2000.00")


def test_summary_gives_opening_and_closing():
    s = extractor.statement_summary(TEXT)
    assert s == {"opening": Decimal("454.94"), "closing": Decimal("1700.00")}


def test_reconciles_against_the_statement_summary():
    s = extractor.statement_summary(TEXT)
    assert extractor.balance_check(_parse(), s["opening"], s["closing"])["reconciles"]


def test_missing_last_row_is_caught():
    s = extractor.statement_summary(TEXT)
    check = extractor.balance_check(_parse()[:-1], s["opening"], s["closing"])
    assert not check["reconciles"] and check["difference"] == "1.00"


def test_dr_balance_is_negative():
    s = extractor.statement_summary(TEXT.replace("454.94CR", "454.94DR"))
    assert s["opening"] == Decimal("-454.94")


def test_lead_in_and_trailer_are_stripped():
    for t in _parse():
        assert not t.merchant.upper().startswith(("WDL", "DEP", "UPI/"))
        assert "KORAMANGALA" not in t.merchant and " AT " not in t.merchant


def test_mid_word_wrap_is_rejoined():
    assert extractor._unwrap("UPI/DR/1/Swigg\ny/YESB") == "UPI/DR/1/Swiggy/YESB"
    assert extractor._unwrap("UPI/DR/1/Ramesh\nK/YESB") == "UPI/DR/1/Ramesh K/YESB"
    assert extractor._unwrap("WDL TFR\nUPI/DR/1/X/") == "WDL TFR UPI/DR/1/X/"
    assert extractor._unwrap("UPI/DR/1/NAME/\nYESB/x") == "UPI/DR/1/NAME/YESB/x"


def test_merchants_people_and_fallbacks():
    by_amount = {t.amount: t for t in _parse()}
    swiggy = by_amount[Decimal("34.94")]
    assert (swiggy.merchant, swiggy.category, swiggy.counterparty_kind) == ("Swiggy", "Food & Dining", "merchant")
    netflix = by_amount[Decimal("199.00")]
    assert (netflix.merchant, netflix.category) == ("Netflix", "Entertainment")
    priya = by_amount[Decimal("500.00")]  # 10-digit phone VPA -> a person
    assert (priya.counterparty_kind, priya.category) == ("person", "P2P Transfer")
    shop = by_amount[Decimal("20.00")]  # paytm merchant QR -> stays in spend
    assert shop.counterparty_kind == "merchant"
    numeric = by_amount[Decimal("1.00")]  # payee shown only as a number -> named by its VPA
    assert numeric.merchant == "Q123456789"


def test_short_rule_tokens_need_whole_words():
    rules = {"ola": ("Ola", "Transport"), "lic": ("LIC", "Insurance")}
    assert extractor._match("COCA COLA", rules)[1] == "Uncategorised"
    assert extractor._match("CLICK STORE", rules)[1] == "Uncategorised"
    assert extractor._match("OLA CABS", rules) == ("Ola", "Transport")


REAL = sorted((pathlib.Path(__file__).resolve().parent.parent / "samples" / "real").glob("*.masked.json"))


@pytest.mark.parametrize("path", REAL, ids=[p.stem for p in REAL])
def test_real_masked_statement_reconciles(path):
    pages = json.loads(path.read_text(encoding="utf-8"))["pages"]
    if pages[0].get("kind") == "sheet":  # masked spreadsheet: raw rows, map columns first
        layout = extractor.layout_from_rows(pages[0]["tables"][0])
        tables, text = layout.tables, layout.text
    else:
        tables = [t for p in pages for t in p["tables"]]
        text = "\n".join("\n".join(p["lines"]) for p in pages)
    txns = extractor.parse_tables(tables)
    dated_rows = sum(1 for t in tables for r in t if r and r[0] and extractor._DATE.match(extractor._unwrap(r[0])))
    assert len(txns) == dated_rows > 0
    s = extractor.statement_summary(text)
    assert s["opening"] is not None and s["closing"] is not None
    check = extractor.balance_check(txns, s["opening"], s["closing"])
    assert check["reconciles"], check
    assert all(t.category in extractor.CATEGORIES for t in txns)
    assert not any(t.merchant.upper().startswith(("WDL", "DEP", "UPI/")) for t in txns)


# --------------------------------------------------------------------------- #
# Spreadsheet downloads: same rows, found by header names wherever they sit
# --------------------------------------------------------------------------- #
SHEET = [
    ["Account Name", ":", "Mr. Test User"],
    ["Account Number", ":", "00000000000"],
    [],
    ["Txn Date", "Value Date", "Description", "Ref No./Cheque No.", "Debit", "Credit", "Balance"],
    *[[c.replace("\n", " ") if isinstance(c, str) else c for c in r] for r in TABLE[1:-1]],
    [],
    ["Statement Summary : 01-01-2026 To 31-01-2026"],
    ["Brought Forward( )", "Dr Count", "Cr Count", "Total Debits( )", "Total Credits( )", "Closing Balance( )"],
    ["454.94CR", "5", "1", "754.94", "2,000.00", "1,700.00CR"],
]


def _check_sheet(data: bytes):
    layout = extractor.load_statement(data)
    txns = extractor.parse_tables(layout.tables)
    assert len(txns) == 6
    s = extractor.statement_summary(layout.text)
    assert extractor.balance_check(txns, s["opening"], s["closing"])["reconciles"]
    assert {t.merchant for t in txns} >= {"Swiggy", "Netflix"}


def test_xlsx_statement():
    import io as _io
    import datetime as _dt
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in SHEET:
        row = list(r)
        if row and extractor._DATE.match(str(row[0])):  # real Excel cells: dates and numbers
            d = _dt.datetime.strptime(row[0], "%d/%m/%Y")
            row[0] = row[1] = d
            row[4:7] = [float(v.replace(",", "")) if v != "-" else None for v in row[4:7]]
        ws.append(row)
    buf = _io.BytesIO()
    wb.save(buf)
    _check_sheet(buf.getvalue())


def test_html_disguised_as_xls():
    html = "<html><body><table>" + "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in SHEET) + "</table></body></html>"
    _check_sheet(html.encode())


def test_tab_separated_text():
    _check_sheet("\n".join("\t".join(r) for r in SHEET).encode())


def test_not_a_statement():
    with pytest.raises(extractor.StatementError):
        extractor.load_statement(b"just,some\ncsv,text\n")


@pytest.mark.parametrize("name, category", [
    ("SRI SAI MEDICALS", "Health & Medical"),
    ("BALAJI KIRANA STORE", "Groceries"),
    ("HP PETROL PUMP", "Fuel"),
    ("STAR UNISEX SALON", "Personal Care"),
    ("GUPTA SWEETS", "Food & Dining"),
    ("RAMESH KUMAR", "Uncategorised"),
])
def test_keyword_categories(name, category):
    assert extractor._match(name, extractor.SEED_RULES)[1] == category


@pytest.mark.parametrize("name, vpa, kind", [
    ("Ramesh K", "9876543210", "person"),        # first name + phone VPA
    ("PRIYANKA S", "priyanka.s", "person"),      # first name alone is enough
    ("Rajeshkum", "rk1990", "person"),           # truncated, run-together name
    ("Mr Bunty", "bunty", "person"),             # title
    ("SHARMA", "9123456780", "person"),          # surname + phone
    ("RAMESH K", "paytm.s1ab2c", "merchant"),    # a person's name on a shop QR is a shop
    ("Ramesh K", "q123456789", "merchant"),      # PhonePe merchant code
    ("SAI TRADERS", "9876543210", "merchant"),   # business word beats the phone VPA
    ("KIRAN KIRANA", "kiran99", "merchant"),     # trade keyword beats the first name
    ("A2B FOODS", "a2b", "merchant"),
    ("XQZWV", "xqzwv", "merchant"),              # no evidence either way -> stays in spend
])
def test_payee_kind(name, vpa, kind):
    assert extractor.payee_kind(name, vpa) == kind


def test_person_note_keyword_beats_p2p():
    row = "WDL TFR UPI/DR/600112233449/Ramesh K/SBIN/9876543210/rent oct"
    _, _, category, kind = extractor.normalise(row)
    assert (kind, category) == ("person", "Rent & Housing")


def test_p2p_category_rule_marks_person():
    rules = {**extractor.SEED_RULES, "xyz shop": ("Xyz Shop", "P2P Transfer")}
    _, _, category, kind = extractor.normalise("UPI/DR/1/XYZ SHOP/YESB/q1234567/UPI", rules)
    assert (kind, category) == ("person", "P2P Transfer")
