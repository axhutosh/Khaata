"""Merchant rules: the user's learned narration-token -> merchant + category map.
Shared by the upload commit (Review corrections) and Transactions recategorise."""
from sqlalchemy.orm import Session
from .models import Transaction, MerchantRule
from . import extractor


def user_rules(db: Session, user_id: str) -> dict:
    rules = dict(extractor.SEED_RULES)
    for r in db.query(MerchantRule).filter(MerchantRule.user_id == user_id).all():
        rules[r.token] = (r.merchant, r.category)
    return rules


def learn(db: Session, user_id: str, merchant: str, category: str) -> None:
    """Save (or update) a rule for this merchant and retro-apply it to the user's saved rows."""
    token = extractor._clean(merchant)
    rule = db.query(MerchantRule).filter(
        MerchantRule.user_id == user_id, MerchantRule.token == token).first()
    if rule:
        rule.category = category
    else:
        db.add(MerchantRule(user_id=user_id, token=token, merchant=merchant, category=category))
    db.query(Transaction).filter(
        Transaction.user_id == user_id, Transaction.merchant == merchant
    ).update({Transaction.category: category})


def reclassify(db: Session, user_id: str) -> int:
    """Re-run categorisation over the user's saved rows with today's rules. Learned rules
    still have the final say (see extractor.normalise), so the user's own corrections stay."""
    current = user_rules(db, user_id)
    changed = 0
    for t in db.query(Transaction).filter(Transaction.user_id == user_id).all():
        method, merchant, category, kind = extractor.normalise(t.raw_narration, current)
        if (t.merchant, t.category, t.counterparty_kind) != (merchant, category, kind):
            t.method, t.merchant, t.category, t.counterparty_kind = method, merchant, category, kind
            changed += 1
    return changed
