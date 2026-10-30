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
    assert (priya.counterparty_kind, priya.category) == ("person", "Transfer · Person")
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
