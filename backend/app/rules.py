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
