import pytest
from app.templates.flex_messages import (
    parse_postback_action,
    build_receipt_card,
    build_loan_carousel,
    build_liquidity_alert_card
)

def test_parse_postback_action():
    data_str = "action=confirm_receipt&receipt_id=rcpt_123&session_id=sme_001"
    parsed = parse_postback_action(data_str)
    assert parsed["action"] == "confirm_receipt"
    assert parsed["receipt_id"] == "rcpt_123"
    assert parsed["session_id"] == "sme_001"

def test_build_receipt_card():
    card = build_receipt_card(
        receipt_id="rcpt_123",
        session_id="sme_001",
        vendor="Bangkok Diesel Maintenance Ltd.",
        grand_total=95000.0,
        vat=6214.95
    )
    assert card["type"] == "flex"
    assert "Bangkok Diesel Maintenance Ltd." in str(card)
    assert "95,000.00" in str(card)
    assert card["contents"]["type"] == "bubble"

def test_build_loan_carousel():
    sample_loans = [
        {
            "product_name": "TCG PGS SME Loan",
            "bank": "SME D Bank",
            "max_limit": 5000000.0,
            "interest_rate_text": "3.5% p.a.",
            "approval_probability": 85
        },
        {
            "product_name": "SME Single Account Loan",
            "bank": "Kasikornbank",
            "max_limit": 2000000.0,
            "interest_rate_text": "MRR+1.5%",
            "approval_probability": 70
        }
    ]
    carousel = build_loan_carousel(sample_loans, session_id="sme_001")
    assert carousel["type"] == "flex"
    assert carousel["contents"]["type"] == "carousel"
    bubbles = carousel["contents"]["contents"]
    assert len(bubbles) == 2
    assert "TCG PGS SME Loan" in str(bubbles[0])
    assert "85%" in str(bubbles[0])

def test_build_liquidity_alert_card():
    card = build_liquidity_alert_card(
        deficit=45000.0,
        remaining_cash=25000.0,
        upcoming_debt=70000.0,
        runway_days=18.5,
        session_id="sme_001"
    )
    assert card["type"] == "flex"
    assert "45,000.00" in str(card)
    assert "18.5 days" in str(card)
