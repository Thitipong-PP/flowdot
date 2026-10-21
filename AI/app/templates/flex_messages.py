from urllib.parse import parse_qs
from typing import Dict, Any, List

def parse_postback_action(data_str: str) -> Dict[str, str]:
    """
    Parses a LINE postback data string (query string format) into a dictionary.
    Example: 'action=confirm_receipt&receipt_id=rcpt_123&session_id=sme_001'
    """
    parsed = parse_qs(data_str)
    return {k: v[0] for k, v in parsed.items()}

def build_receipt_card(
    receipt_id: str,
    session_id: str,
    vendor: str,
    grand_total: float,
    vat: float = 0.0
) -> Dict[str, Any]:
    """
    Builds an interactive LINE Bubble Flex Message for confirming extracted receipt/bill data.
    """
    return {
        "type": "flex",
        "altText": f"Receipt Confirmation: {vendor} ({grand_total:,.2f} THB)",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "🧾 Confirm Financial Document",
                        "weight": "bold",
                        "size": "md",
                        "color": "#1e293b"
                    },
                    {
                        "type": "separator",
                        "margin": "md"
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "md",
                        "spacing": "xs",
                        "contents": [
                            {"type": "text", "text": f"Vendor / Counterparty: {vendor}", "size": "sm", "color": "#475569"},
                            {"type": "text", "text": f"Total Amount: {grand_total:,.2f} THB", "size": "lg", "weight": "bold", "color": "#0284c7"},
                            {"type": "text", "text": f"VAT: {vat:,.2f} THB", "size": "xs", "color": "#94a3b8"}
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "horizontal",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#10b981",
                        "action": {
                            "type": "postback",
                            "label": "Confirm & Save",
                            "data": f"action=confirm_receipt&receipt_id={receipt_id}&session_id={session_id}"
                        }
                    },
                    {
                        "type": "button",
                        "style": "secondary",
                        "action": {
                            "type": "postback",
                            "label": "Edit Details",
                            "data": f"action=edit_receipt&receipt_id={receipt_id}&session_id={session_id}"
                        }
                    }
                ]
            }
        }
    }

def build_loan_carousel(
    loans: List[Dict[str, Any]],
    session_id: str = ""
) -> Dict[str, Any]:
    """
    Builds a LINE Carousel Flex Message displaying recommended loan products.
    """
    bubbles = []
    for idx, loan in enumerate(loans[:5], 1):
        name = loan.get("product_name") or loan.get("name", "SME Business Loan")
        bank = loan.get("bank", "Partner Financial Institution")
        max_limit = loan.get("max_limit", 0.0)
        interest = loan.get("interest_rate_text", "Bank Terms Apply")
        prob = loan.get("approval_probability", 80)
        product_id = loan.get("product_id") or f"loan_{idx}"

        bubble = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"🏦 {bank}",
                        "weight": "bold",
                        "size": "xs",
                        "color": "#64748b"
                    },
                    {
                        "type": "text",
                        "text": name,
                        "weight": "bold",
                        "size": "sm",
                        "wrap": True,
                        "color": "#0f172a",
                        "margin": "xs"
                    },
                    {
                        "type": "separator",
                        "margin": "md"
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "md",
                        "spacing": "xs",
                        "contents": [
                            {"type": "text", "text": f"Max Limit: {max_limit:,.0f} THB", "size": "xs", "color": "#334155"},
                            {"type": "text", "text": f"Interest Rate: {interest}", "size": "xs", "color": "#334155"},
                            {"type": "text", "text": f"Approval Match: {prob}%", "size": "sm", "weight": "bold", "color": "#16a34a"}
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#0284c7",
                        "action": {
                            "type": "postback",
                            "label": "Apply for this Loan",
                            "data": f"action=apply_loan&product_id={product_id}&session_id={session_id}"
                        }
                    }
                ]
            }
        }
        bubbles.append(bubble)

    return {
        "type": "flex",
        "altText": f"Recommended SME Loan Options ({len(bubbles)} products)",
        "contents": {
            "type": "carousel",
            "contents": bubbles
        }
    }

def build_liquidity_alert_card(
    deficit: float,
    remaining_cash: float,
    upcoming_debt: float,
    runway_days: float,
    session_id: str = ""
) -> Dict[str, Any]:
    """
    Builds a high-priority liquidity warning card with action button.
    """
    return {
        "type": "flex",
        "altText": f"⚠️ Liquidity Alert! Projected Deficit: {deficit:,.2f} THB",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "🚨 Liquidity Shortfall Warning",
                        "weight": "bold",
                        "size": "md",
                        "color": "#dc2626"
                    },
                    {
                        "type": "separator",
                        "margin": "md"
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "md",
                        "spacing": "xs",
                        "contents": [
                            {"type": "text", "text": f"Remaining Cash: {remaining_cash:,.2f} THB", "size": "sm", "color": "#334155"},
                            {"type": "text", "text": f"Upcoming Debt Due: {upcoming_debt:,.2f} THB", "size": "sm", "color": "#334155"},
                            {"type": "text", "text": f"Estimated Deficit: {deficit:,.2f} THB", "size": "lg", "weight": "bold", "color": "#dc2626"},
                            {"type": "text", "text": f"Cash Runway: {runway_days:.1f} days", "size": "xs", "color": "#64748b"}
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#dc2626",
                        "action": {
                            "type": "postback",
                            "label": "Find Emergency Financing",
                            "data": f"action=find_emergency_loan&deficit={deficit:.2f}&session_id={session_id}"
                        }
                    }
                ]
            }
        }
    }
