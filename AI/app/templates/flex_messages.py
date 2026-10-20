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
        "altText": f"ยืนยันข้อมูลใบเสร็จ: {vendor} ({grand_total:,.2f} THB)",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "🧾 ยืนยันข้อมูลเอกสารการเงิน",
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
                            {"type": "text", "text": f"ร้านค้า/คู่ค้า: {vendor}", "size": "sm", "color": "#475569"},
                            {"type": "text", "text": f"ยอดรวมสุทธิ: {grand_total:,.2f} THB", "size": "lg", "weight": "bold", "color": "#0284c7"},
                            {"type": "text", "text": f"ภาษีมูลค่าเพิ่ม (VAT): {vat:,.2f} THB", "size": "xs", "color": "#94a3b8"}
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
                            "label": "ยืนยันบันทึก",
                            "data": f"action=confirm_receipt&receipt_id={receipt_id}&session_id={session_id}"
                        }
                    },
                    {
                        "type": "button",
                        "style": "secondary",
                        "action": {
                            "type": "postback",
                            "label": "แก้ไขข้อมูล",
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
        name = loan.get("product_name") or loan.get("name", "สินเชื่อธุรกิจ SME")
        bank = loan.get("bank", "สถาบันการเงินพันธมิตร")
        max_limit = loan.get("max_limit", 0.0)
        interest = loan.get("interest_rate_text", "ตามเกณฑ์ธนาคาร")
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
                            {"type": "text", "text": f"วงเงินสูงสุด: {max_limit:,.0f} THB", "size": "xs", "color": "#334155"},
                            {"type": "text", "text": f"อัตราดอกเบี้ย: {interest}", "size": "xs", "color": "#334155"},
                            {"type": "text", "text": f"โอกาสอนุมัติ: {prob}%", "size": "sm", "weight": "bold", "color": "#16a34a"}
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
                            "label": "สนใจสมัครสินเชื่อนี้",
                            "data": f"action=apply_loan&product_id={product_id}&session_id={session_id}"
                        }
                    }
                ]
            }
        }
        bubbles.append(bubble)

    return {
        "type": "flex",
        "altText": f"แนะนำผลิตภัณฑ์สินเชื่อ SME {len(bubbles)} รายการ",
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
        "altText": f"⚠️ แจ้งเตือนวิกฤตสภาพคล่อง! ขาดดุล {deficit:,.2f} THB",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "🚨 แจ้งเตือนสภาพคล่องตึงตัว",
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
                            {"type": "text", "text": f"เงินสดคงเหลือ: {remaining_cash:,.2f} THB", "size": "sm", "color": "#334155"},
                            {"type": "text", "text": f"หนี้ที่ต้องชำระสิ้นเดือน: {upcoming_debt:,.2f} THB", "size": "sm", "color": "#334155"},
                            {"type": "text", "text": f"ยอดขาดดุลประเมิน: {deficit:,.2f} THB", "size": "lg", "weight": "bold", "color": "#dc2626"},
                            {"type": "text", "text": f"ระยะเวลาประคองตัว (Runway): {runway_days:.1f} วัน", "size": "xs", "color": "#64748b"}
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
                            "label": "ค้นหาสินเชื่อ SME ฉุกเฉิน",
                            "data": f"action=find_emergency_loan&deficit={deficit:.2f}&session_id={session_id}"
                        }
                    }
                ]
            }
        }
    }
