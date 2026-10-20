import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Union
import httpx
from app.config import settings
from app.db.mongo import MongoDBManager
from app.schemas.financial import (
    PaymentSlipSchema,
    InvoiceOrBillSchema,
    BankStatementSchema,
    SellerBuyerSchema,
    LineItemSchema,
    StatementAccountSchema,
    StatementTransactionSchema
)

class VisionWorker:
    def __init__(self, mock_mode: bool = False):
        self.mock_mode = mock_mode
        self.mongo = MongoDBManager()
        # In-memory mock store for unit testing & fallback
        self._mock_docs: List[Dict[str, Any]] = []
        self._mock_pending_invoices: List[Dict[str, Any]] = []

    def classify_document_text(self, text: str) -> str:
        """Rule-based text heuristic classifier based on anchor keywords."""
        text_lower = text.lower()

        # 1. Bank Statement
        statement_anchors = [
            "รายการเดินบัญชี",
            "ใบแจ้งยอด",
            "ยอดคงเหลือยกมา",
            "ยอดยกไป",
            "ยอดยกมา",
            "ดอกเบี้ยสะสม",
            "ยอดเงินชำระขั้นต่ำ",
            "bank statement",
            "statement of",
            "brought forward",
            "balance forward",
            "closing balance",
            "previous balance",
            "minimum payment",
            "credit limit",
        ]
        if any(k in text_lower for k in statement_anchors):
            return "bank_statement"

        # 2. Payment Slip & Salary Slip (สลิปโอนเดี่ยว และสลิปเงินเดือน)
        slip_anchors = [
            "โอนเงินสำเร็จ",
            "ทำรายการสำเร็จ",
            "รหัสอ้างอิง",
            "หมายเลขอ้างอิง",
            "สแกนตรวจสอบสลิป",
            "ตรวจสอบสลิป",
            "transfer successful",
            "transaction successful",
            "ใบรับเงินเดือน",
            "สลิปเงินเดือน",
            "หนังสือรับรองเงินเดือน",
            "หักมาสาย",
            "pay slip",
            "payslip",
            "salary slip",
            "net pay",
        ]
        if any(k in text_lower for k in slip_anchors):
            return "payment_slip"

        # 3. Commercial Invoice / Bill / Receipt
        invoice_anchors = [
            "ใบกำกับภาษี",
            "ใบเสร็จรับเงิน",
            "ใบแจ้งหนี้",
            "ใบส่งของ",
            "ยอดรวมทั้งสิ้น",
            "จำนวนเงินรวมทั้งสิ้น",
            "tax invoice",
            "receipt",
            "invoice",
            "grand total",
            "subtotal",
        ]
        if any(k in text_lower for k in invoice_anchors):
            return "invoice_or_bill"

        return "non_financial_image"

    async def classify_document(self, text: str, **kwargs) -> str:
        """
        Unified Document Classification:
        1. Fast Rule-based check using anchors.
        2. If unmatched ('non_financial_image'), falls back to local Satellite LLM (Qwen).
        """
        # Step 1: Rule-based text classification
        rule_result = self.classify_document_text(text)
        if rule_result != "non_financial_image":
            return rule_result

        # Step 2: LLM fallback when rule-based cannot determine the document type
        prompt = f"""You are an expert Thai Financial Document Classifier.
        Classify the OCR text into EXACTLY ONE class: "bank_statement", "payment_slip", "invoice_or_bill", "non_financial_image".

        ### DEFINITIONS:
        - "bank_statement":
        Bank account statements or credit card statements showing multi-transaction tables, closing balance, or deposit/withdrawal history (e.g., ใบแจ้งยอด, รายการเดินบัญชี, ยอดคงเหลือยกมา, brought forward, balance forward). NOTE: Even if a bank statement contains "TAX INVOICE / ใบกำกับภาษี" for bank fees, it is STILL "bank_statement".

        - "payment_slip":
        A SINGLE transaction proof of money transfer (e.g., โอนเงินสำเร็จ, transfer successful, K+, SCB EASY, Krungthai NEXT) OR an employee payroll / salary payslip (e.g., ใบรับเงินเดือน, สลิปเงินเดือน, หักมาสาย, ประจำงวด).

        - "invoice_or_bill":
        Commercial receipt, tax invoice, sales bill, gas receipt, or store slip issued by a company or merchant (e.g., ใบเสร็จรับเงิน, ใบกำกับภาษี, ใบแจ้งหนี้, receipt, invoice, ต้นฉบับ/สำเนา, รวมเป็นเงิน, grand total, vat 7%, SUSCO). NOTE: "ใบเสร็จรับเงิน" is ALWAYS "invoice_or_bill", NEVER payment_slip.

        - "non_financial_image":
        General pictures, articles, recipes, or non-financial text.

        Respond ONLY with JSON:
        {{"doc_type": "<bank_statement|payment_slip|invoice_or_bill|non_financial_image>"}}

        Document snippet:
        \"\"\"
        {text}
        \"\"\""""

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                res = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/chat/completions",
                    json={
                        "model": settings.OLLAMA_WORKER_MODEL,
                        "messages": [
                            {"role": "system", "content": "You are a specialized classifier that outputs JSON only."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.0,
                        "response_format": {"type": "json_object"}
                    }
                )
                if res.status_code == 200:
                    import json
                    data = res.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    doc_type = parsed.get("doc_type")
                    if doc_type in ["payment_slip", "invoice_or_bill", "bank_statement", "non_financial_image"]:
                        return doc_type
        except Exception as e:
            print(f"Error in classify_document LLM fallback ({type(e).__name__}): {e}")

        return "non_financial_image"

    async def register_confirmed_document(self, doc: Dict[str, Any]):
        """Persists a confirmed document to MongoDB receipts collection or mock storage."""
        if "created_at" not in doc:
            doc["created_at"] = datetime.now(timezone.utc)
            
        if self.mock_mode:
            self._mock_docs.append(doc)
        else:
            try:
                await self.mongo.receipts.insert_one(doc)
            except Exception as e:
                print(f"Error in register_confirmed_document: {e}")
                self._mock_docs.append(doc)

    async def register_pending_invoice(self, bill: Dict[str, Any]):
        """Registers an invoice as pending payment."""
        if "created_at" not in bill:
            bill["created_at"] = datetime.now(timezone.utc)
        bill["status"] = "PENDING_CONFIRMATION"

        if self.mock_mode:
            self._mock_pending_invoices.append(bill)
        else:
            try:
                await self.mongo.receipts.insert_one(bill)
            except Exception as e:
                print(f"Error in register_pending_invoice: {e}")
                self._mock_pending_invoices.append(bill)

    async def check_3tier_duplicates(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        3-Tier Duplicate & Reconciliation Engine:
        - Tier 1: Hard Duplicate Check (reference_no for slips, document_no + seller.tax_id for invoices)
        - Tier 2: Cross-check reconciliation (Payment slip matches an unpaid/pending invoice)
        - Tier 3: Soft Duplicate (Same vendor and same amount within 48h)
        """
        doc_type = doc.get("doc_type")
        ref_no = doc.get("reference_no")
        doc_no = doc.get("document_no")
        seller_tax_id = doc.get("seller", {}).get("tax_id") if isinstance(doc.get("seller"), dict) else None
        amount = float(doc.get("amount") or doc.get("grand_total") or 0.0)

        # -------------------------------------------------------------
        # Gather candidate documents from Mongo or mock storage
        # -------------------------------------------------------------
        existing_docs = list(self._mock_docs)
        pending_invoices = list(self._mock_pending_invoices)

        if not self.mock_mode:
            try:
                cursor = self.mongo.receipts.find()
                async for item in cursor:
                    if item.get("status") == "PENDING_CONFIRMATION":
                        pending_invoices.append(item)
                    else:
                        existing_docs.append(item)
            except Exception as e:
                print(f"Error fetching existing receipts in check_3tier_duplicates: {e}")

        # -------------------------------------------------------------
        # Tier 1: Hard Duplicate Check (Immediate Rejection)
        # -------------------------------------------------------------
        for existing in existing_docs:
            # Slip duplicate by reference_no
            if ref_no and existing.get("reference_no") == ref_no:
                return {
                    "is_hard_duplicate": True,
                    "is_reconciled": False,
                    "is_soft_duplicate": False,
                    "tier": 1,
                    "reason": f"Slip ref {ref_no} already recorded"
                }
            # Invoice duplicate by document_no + seller tax_id
            if doc_no and seller_tax_id:
                ex_doc_no = existing.get("document_no")
                ex_seller = existing.get("seller", {})
                ex_tax = ex_seller.get("tax_id") if isinstance(ex_seller, dict) else None
                if ex_doc_no == doc_no and ex_tax == seller_tax_id:
                    return {
                        "is_hard_duplicate": True,
                        "is_reconciled": False,
                        "is_soft_duplicate": False,
                        "tier": 1,
                        "reason": f"Invoice {doc_no} from {seller_tax_id} already recorded"
                    }

        # -------------------------------------------------------------
        # Tier 2: Cross-check reconciliation (Payment Slip -> Pending Invoice)
        # -------------------------------------------------------------
        if doc_type == "payment_slip":
            receiver_name = (doc.get("receiver_name") or "").strip().lower()
            for pending in pending_invoices:
                p_seller = pending.get("seller", {})
                p_seller_name = (p_seller.get("name") if isinstance(p_seller, dict) else "").strip().lower()
                p_total = float(pending.get("grand_total") or pending.get("subtotal") or 0.0)
                
                # Check amount match (within 1.0 THB) & name match
                amount_matches = abs(p_total - amount) < 1.0
                name_matches = bool(receiver_name and (receiver_name in p_seller_name or p_seller_name in receiver_name))
                
                if amount_matches and (name_matches or not receiver_name):
                    pending["status"] = "PAID"
                    matched_inv = pending.get("document_no", "UNKNOWN")
                    if not self.mock_mode:
                        try:
                            await self.mongo.receipts.update_one(
                                {"document_no": matched_inv},
                                {"$set": {"status": "PAID", "reconciled_at": datetime.now(timezone.utc)}}
                            )
                        except Exception as e:
                            print(f"Error updating invoice status to PAID: {e}")
                    return {
                        "is_hard_duplicate": False,
                        "is_reconciled": True,
                        "is_soft_duplicate": False,
                        "tier": 2,
                        "matched_invoice_no": matched_inv,
                        "reason": f"Payment slip matches pending invoice {matched_inv}"
                    }

        # -------------------------------------------------------------
        # Tier 3: Soft Duplicate (Same vendor and amount within 48 hours)
        # -------------------------------------------------------------
        vendor = (
            doc.get("receiver_name")
            or doc.get("sender_name")
            or (doc.get("seller", {}).get("name") if isinstance(doc.get("seller"), dict) else None)
        )
        now = datetime.now(timezone.utc)
        
        for existing in existing_docs:
            ex_vendor = (
                existing.get("receiver_name")
                or existing.get("sender_name")
                or (existing.get("seller", {}).get("name") if isinstance(existing.get("seller"), dict) else None)
            )
            ex_amount = float(existing.get("amount") or existing.get("grand_total") or 0.0)
            ex_time = existing.get("created_at")
            if isinstance(ex_time, str):
                try:
                    ex_time = datetime.fromisoformat(ex_time)
                except Exception as e:
                    print(f"Error parsing datetime in soft duplicate check: {e}")
                    ex_time = now
            elif not isinstance(ex_time, datetime):
                ex_time = now
                
            # If naive datetime, make UTC aware
            if ex_time.tzinfo is None:
                ex_time = ex_time.replace(tzinfo=timezone.utc)

            if vendor and ex_vendor and (vendor.strip().lower() == ex_vendor.strip().lower()):
                if abs(ex_amount - amount) < 0.01:
                    time_diff = now - ex_time
                    if time_diff <= timedelta(hours=48):
                        return {
                            "is_hard_duplicate": False,
                            "is_reconciled": False,
                            "is_soft_duplicate": True,
                            "tier": 3,
                            "reason": f"Similar transaction of {amount:,.2f} THB to {vendor} within past 48h ({time_diff.total_seconds() / 3600:.1f} hrs ago)"
                        }

        return {
            "is_hard_duplicate": False,
            "is_reconciled": False,
            "is_soft_duplicate": False,
            "tier": 0,
            "reason": "No duplicates detected"
        }

    async def ocr_image(self, image_path: str) -> str:
        """
        Calls OpenTyphoon OCR API (model: 'typhoon-ocr') on an image file.
        Requires TYPHOON_API_KEY in .env.
        """
        import os
        import asyncio

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at path: {image_path}")

        api_key = settings.TYPHOON_API_KEY.strip()
        if not api_key:
            raise ValueError(
                "TYPHOON_API_KEY is not configured! Please open your .env file and set TYPHOON_API_KEY=your_key_here"
            )

        try:
            from typhoon_ocr import ocr_document
            # Run in thread pool so it does not block the async event loop
            return await asyncio.to_thread(
                ocr_document,
                pdf_or_image_path=image_path,
                api_key=api_key,
                base_url=settings.TYPHOON_OCR_API_URL
            )
        except Exception as e:
            print(f"Primary typhoon_ocr failed with error: {e}. Falling back to REST API...")
            import base64
            with open(image_path, "rb") as img_f:
                b64_image = base64.b64encode(img_f.read()).decode("utf-8")

            ext = os.path.splitext(image_path)[1].lower()
            mime_type = "image/png" if ext == ".png" else "image/jpeg"

            url = f"{settings.TYPHOON_OCR_API_URL.rstrip('/')}/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "typhoon-ocr",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extract all text from the image.\n\nInstructions:\n- Only return the clean Markdown.\n- Do not include any explanation or extra text.\n- You must include all information on the page."},
                            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_image}"}}
                        ]
                    }
                ],
                "max_tokens": 8000,
                "temperature": 0.1
            }

            async with httpx.AsyncClient(timeout=90.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code != 200:
                    raise RuntimeError(f"Typhoon OCR API error ({res.status_code}): {res.text}")
                data = res.json()
                return data["choices"][0]["message"]["content"]

    def extract_slip_schema(self, text: str) -> PaymentSlipSchema:
        """Parses OCR text of a payment slip into PaymentSlipSchema."""
        slip = PaymentSlipSchema()
        
        # 1. Amount
        amt_match = re.search(r'(?:จำนวนเงิน|amount)\s*[:\*]*\s*([\d,]+\.?\d*)', text, re.I)
        if amt_match:
            try:
                slip.amount = float(amt_match.group(1).replace(',', ''))
            except ValueError:
                pass
                
        # 2. Reference No
        ref_match = re.search(r'(?:รหัสอ้างอิง|หมายเลขอ้างอิง|reference\s*no\.?|ref(?:\s*no)?\.?)\s*[:\*]*\s*([A-Za-z0-9\-]+)', text, re.I)
        if ref_match:
            slip.reference_no = ref_match.group(1).replace('*', '').strip()
            
        # 3. Transaction datetime
        dt_match = re.search(r'(?:วันที่ทำรายการ|วันที่โอน|date|datetime)\s*[:\*]*\s*([0-9]{1,2}\s+[^\n\r]+)', text, re.I)
        if dt_match:
            slip.transaction_datetime = dt_match.group(1).replace('*', '').strip()
            
        # 4. Status text
        if "โอนเงินสำเร็จ" in text or "transfer successful" in text.lower():
            slip.status_text = "โอนเงินสำเร็จ"
            
        # 5. Accounts & Names
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for i, line in enumerate(lines):
            if "XXX" in line or any(b in line for b in ["กรุงไทย", "กสิกร", "ไทยพาณิชย์", "กรุงเทพ", "ttb"]):
                if not slip.sender_account_masked:
                    slip.sender_account_masked = line
                    if i > 0 and not any(kw in lines[i-1] for kw in ["โอนเงินสำเร็จ", "Krungthai"]):
                        slip.sender_name = lines[i-1]
                elif not slip.receiver_account_masked:
                    slip.receiver_account_masked = line
                    parts = line.split()
                    if len(parts) > 1 and not parts[0].startswith("XXX"):
                        slip.receiver_name = parts[0]
                    elif i > 0:
                        slip.receiver_name = lines[i-1]

        slip.extraction_confidence = 0.95 if slip.amount and slip.amount > 0 else 0.70
        return slip

    def extract_invoice_schema(self, text: str) -> InvoiceOrBillSchema:
        """Parses OCR text of an invoice/bill/receipt into InvoiceOrBillSchema."""
        inv = InvoiceOrBillSchema()
        
        # 1. Tax ID (from text or table)
        tax_matches = re.findall(r'(?:TAX\s*ID\.?|เลขประจำตัวผู้เสียภาษี(?:อากร)?)\s*[:\*<>\/td\s]*([0-9]{13})', text, re.I)
        if tax_matches:
            inv.seller = SellerBuyerSchema(tax_id=tax_matches[0])
            if len(tax_matches) > 1:
                inv.buyer = SellerBuyerSchema(tax_id=tax_matches[1])
                
        # 2. Document No
        doc_match = re.search(r'(?:No\.?|เลขที่|INV\s*No\.?)\s*[:\*<>\/td\s]*([A-Za-z0-9\/\-]+)', text, re.I)
        if doc_match:
            inv.document_no = doc_match.group(1).replace('*', '').strip()
            
        # 3. Date
        date_match = re.search(r'(?:Date:?|วันที่)\s*[:\*<>\/td\s]*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})', text, re.I)
        if date_match:
            inv.issue_date = date_match.group(1).strip()
            
        # 4. Totals (Grand Total, Subtotal, VAT, Discount)
        gt_match = re.search(r'(?:GRAND\s*TOTAL|รวมมูลค่าสุทธิ|รวมทั้งสิ้น|ยอดรวมทั้งสิ้น)[^0-9\n\r]*([\d,]+\.?\d*)', text, re.I)
        if gt_match:
            try:
                inv.grand_total = float(gt_match.group(1).replace(',', ''))
            except ValueError:
                pass
            
        sub_match = re.search(r'(?:มูลค่าสินค้า|subtotal|รวมเงิน)[^0-9\n\r]*([\d,]+\.?\d*)', text, re.I)
        if sub_match:
            try:
                inv.subtotal = float(sub_match.group(1).replace(',', ''))
            except ValueError:
                pass
            
        vat_match = re.search(r'(?:VAT\s*7\s*%\s*\)?|ภาษีมูลค่าเพิ่ม)[^0-9\n\r]*([\d,]+\.\d{2})', text, re.I)
        if vat_match:
            try:
                inv.vat_amount = float(vat_match.group(1).replace(',', ''))
            except ValueError:
                pass
            
        disc_match = re.search(r'(?:ส่วนลด|Discount)[^0-9\n\r]*([\d,]+\.?\d*)', text, re.I)
        if disc_match:
            try:
                inv.discount_total = float(disc_match.group(1).replace(',', ''))
            except ValueError:
                pass

        # 5. Line items from HTML table
        def clean_tags(s: str) -> str:
            return re.sub(r'<[^>]+>', ' ', s).strip()

        rows = re.findall(r'<tr>(.*?)</tr>', text, re.S | re.I)
        for r in rows:
            tds = [clean_tags(td) for td in re.findall(r'<td[^>]*>(.*?)</td>', r, re.S | re.I)]
            if len(tds) >= 4 and not any(h in tds[0].lower() for h in ['ลำดับ', 'tax id', 'card', 'date']):
                desc = tds[2] if len(tds) > 2 else tds[0]
                qty_str = tds[3] if len(tds) > 3 else "1"
                amt_str = tds[-1] if len(tds) > 1 else "0"
                try:
                    qty = float(re.sub(r'[^\d.]', '', qty_str) or 1.0)
                    amt = float(re.sub(r'[^\d.]', '', amt_str) or 0.0)
                    if desc and not any(w in desc.lower() for w in ['total', 'รวมเงิน']):
                        inv.line_items.append(LineItemSchema(
                            description=desc,
                            quantity=qty,
                            amount=amt
                        ))
                except Exception as e:
                    print(f"Error parsing invoice line item: {e}")

        # 6. Seller Name
        lines = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith('<') and not l.startswith('#')]
        if lines:
            if not inv.seller:
                inv.seller = SellerBuyerSchema()
            inv.seller.name = lines[0]

        inv.extraction_confidence = 0.90 if inv.grand_total and inv.grand_total > 0 else 0.60
        return inv

    def extract_statement_schema(self, text: str) -> BankStatementSchema:
        """Parses OCR text of a bank/credit card statement into BankStatementSchema."""
        stmt = BankStatementSchema()
        acct = StatementAccountSchema()
        
        # 1. Bank
        for b in ["SCB", "ไทยพาณิชย์", "กสิกรไทย", "KBANK", "กรุงไทย", "KTB", "กรุงเทพ", "BBL", "ttb"]:
            if b.lower() in text.lower():
                acct.bank = b
                break
                
        # 2. Account / Card No
        card_match = re.search(r'([0-9]{4}\s+[0-9]{2}[xX]{2}\s+[xX]{4}\s+[0-9]{4})', text)
        if not card_match:
            card_match = re.search(r'(?:CARD\s*NUMBER|หมายเลขบัตร|บัญชีเลขที่|เลขที่บัญชี)[^0-9xX]*([0-9xX\s\-]{10,25})', text, re.I)
        if card_match:
            acct.account_masked = card_match.group(1).strip()
            
        # 3. Balances
        bal_match = re.search(r'(?:PREVIOUS\s*BALANCE|ยอดคงเหลือยกมา)[^0-9\n\r]*([\d,]+\.?\d*)', text, re.I)
        if bal_match:
            try:
                acct.balance_forward = float(bal_match.group(1).replace(',', ''))
            except ValueError:
                pass
            
        new_bal_match = re.search(r'(?:NEW\s*BALANCE|THIS\s*PERIOD\s*BALANCE|ยอดคงเหลือ)[^0-9\n\r]*([\d,]+\.?\d*)', text, re.I)
        if new_bal_match:
            try:
                acct.closing_balance = float(new_bal_match.group(1).replace(',', ''))
            except ValueError:
                pass

        # 4. Transactions from HTML table
        def clean_tags(s: str) -> str:
            return re.sub(r'<[^>]+>', ' ', s).strip()

        rows = re.findall(r'<tr>(.*?)</tr>', text, re.S | re.I)
        for r in rows:
            tds = [clean_tags(td) for td in re.findall(r'<td[^>]*>(.*?)</td>', r, re.S | re.I)]
            if len(tds) >= 3 and not any(h in tds[0].lower() for h in ['date', 'วันที่', 'หมายเลข', 'card']):
                date_val = tds[0]
                desc_val = tds[2] if len(tds) > 2 else tds[1]
                amt_str = tds[-1] if len(tds) > 1 else "0"
                if desc_val and not any(b in desc_val for b in ['PREVIOUS BALANCE', 'THIS PERIOD BALANCE', 'TOTAL INTEREST']):
                    try:
                        amt_clean = re.sub(r'[^\d.]', '', amt_str)
                        if amt_clean:
                            # Handle multiple dots if OCR misread commas as dots (e.g. '100.007.00' -> '100007.00')
                            if amt_clean.count('.') > 1:
                                parts = amt_clean.split('.')
                                amt_clean = "".join(parts[:-1]) + "." + parts[-1]
                            amt = float(amt_clean)
                        else:
                            amt = 0.0
                        stmt.transactions.append(StatementTransactionSchema(
                            date=date_val,
                            description=desc_val,
                            amount=amt
                        ))
                    except Exception as e:
                        print(f"Error parsing statement transaction item: {e}")

        stmt.account = acct
        stmt.extraction_confidence = 0.90 if acct.bank else 0.60
        return stmt

    async def _call_llm_json(self, prompt: str, system_prompt: str, timeout: float = 600.0) -> Optional[Dict[str, Any]]:
        """Helper to invoke local Ollama with JSON output mode."""
        import json
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                res = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/chat/completions",
                    json={
                        "model": settings.OLLAMA_WORKER_MODEL,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.0,
                        "response_format": {"type": "json_object"}
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"]
                    return json.loads(content)
        except Exception as e:
            print(f"Error calling LLM JSON in _call_llm_json ({type(e).__name__}): {e}")
        return None

    async def _extract_slip_llm(self, text: str) -> PaymentSlipSchema:
        """Extracts structured payment slip data using LLM with deterministic fallback."""
        prompt = (
            "You are a Thai Financial Document Parser. Extract data from this payment slip OCR text into JSON.\n\n"
            "JSON Fields to extract:\n"
            "{\n"
            '  "amount": <float, e.g. 1000000.0>,\n'
            '  "currency": "THB",\n'
            '  "transaction_datetime": <str, e.g. "06 พ.ค. 2567 - 16:14">,\n'
            '  "reference_no": <str or null>,\n'
            '  "status_text": <str, e.g. "โอนเงินสำเร็จ">,\n'
            '  "sender_name": <str or null>,\n'
            '  "sender_account_masked": <str or null>,\n'
            '  "receiver_name": <str or null>,\n'
            '  "receiver_account_masked": <str or null>,\n'
            '  "memo": <str or null>\n'
            "}\n\n"
            f"OCR Text:\n\"\"\"{text[:1500]}\"\"\""
        )
        parsed = await self._call_llm_json(
            prompt=prompt,
            system_prompt="You are a specialized financial extraction AI. Output strictly valid JSON."
        )
        if parsed and isinstance(parsed, dict) and parsed.get("amount"):
            try:
                slip = PaymentSlipSchema.model_validate(parsed)
                slip.extraction_confidence = 0.95
                return slip
            except Exception as e:
                print(f"Error validating PaymentSlipSchema in _extract_slip_llm: {e}")
        return self.extract_slip_schema(text)

    async def _extract_invoice_llm(self, text: str) -> InvoiceOrBillSchema:
        """Extracts structured invoice/bill data using LLM with deterministic fallback."""
        prompt = (
            "You are a Thai Financial Document Parser. Extract data from this Tax Invoice / Receipt OCR text into JSON.\n\n"
            "JSON Fields to extract:\n"
            "{\n"
            '  "document_no": <str or null>,\n'
            '  "issue_date": <str or null>,\n'
            '  "currency": "THB",\n'
            '  "seller": {"name": <str or null>, "tax_id": <str 13-digits or null>},\n'
            '  "buyer": {"name": <str or null>, "tax_id": <str or null>},\n'
            '  "line_items": [{"description": <str>, "quantity": <float>, "unit_price": <float>, "amount": <float>}],\n'
            '  "subtotal": <float>,\n'
            '  "vat_amount": <float>,\n'
            '  "grand_total": <float>\n'
            "}\n\n"
            f"OCR Text:\n\"\"\"{text[:2500]}\"\"\""
        )
        parsed = await self._call_llm_json(
            prompt=prompt,
            system_prompt="You are a specialized tax invoice extraction AI. Output strictly valid JSON."
        )
        if parsed and isinstance(parsed, dict) and (parsed.get("grand_total") or parsed.get("line_items")):
            try:
                inv = InvoiceOrBillSchema.model_validate(parsed)
                inv.extraction_confidence = 0.92
                return inv
            except Exception as e:
                print(f"Error validating InvoiceOrBillSchema in _extract_invoice_llm: {e}")
        return self.extract_invoice_schema(text)

    async def _extract_statement_llm(self, text: str) -> BankStatementSchema:
        """Extracts structured bank statement data using LLM with deterministic fallback."""
        prompt = (
            "You are a Thai Financial Document Parser. Extract data from this Bank/Card Statement OCR text into JSON.\n\n"
            "JSON Fields to extract:\n"
            "{\n"
            '  "bank_format": <str, e.g. "SCB" or "KBANK">,\n'
            '  "account": {\n'
            '    "bank": <str>,\n'
            '    "account_masked": <str or null>,\n'
            '    "currency": "THB",\n'
            '    "balance_forward": <float or null>,\n'
            '    "closing_balance": <float or null>\n'
            '  },\n'
            '  "transactions": [\n'
            '    {"date": <str>, "description": <str>, "amount": <float>}\n'
            '  ]\n'
            "}\n\n"
            f"OCR Text:\n\"\"\"{text[:2500]}\"\"\""
        )
        parsed = await self._call_llm_json(
            prompt=prompt,
            system_prompt="You are a bank statement extraction AI. Output strictly valid JSON."
        )
        if parsed and isinstance(parsed, dict) and parsed.get("account"):
            try:
                stmt = BankStatementSchema.model_validate(parsed)
                stmt.extraction_confidence = 0.90
                return stmt
            except Exception as e:
                print(f"Error validating BankStatementSchema in _extract_statement_llm: {e}")
        return self.extract_statement_schema(text)

    async def extract_document_data(
        self,
        ocr_text: str,
        doc_type: str,
        use_llm: bool = True
    ) -> Union[PaymentSlipSchema, InvoiceOrBillSchema, BankStatementSchema, Dict[str, Any]]:
        """
        Master Facade Entrypoint:
        Dispatches OCR text to specialized LLM extractors (or heuristic extractors if use_llm=False).
        Returns a typed Pydantic Schema model instance.
        """
        if doc_type == "payment_slip":
            return await self._extract_slip_llm(ocr_text) if use_llm else self.extract_slip_schema(ocr_text)
        elif doc_type == "invoice_or_bill":
            return await self._extract_invoice_llm(ocr_text) if use_llm else self.extract_invoice_schema(ocr_text)
        elif doc_type == "bank_statement":
            return await self._extract_statement_llm(ocr_text) if use_llm else self.extract_statement_schema(ocr_text)
        else:
            return {"doc_type": "non_financial_image", "message": "No structured financial fields extracted"}

    async def process_financial_image(self, image_path: str, use_llm: bool = True) -> Dict[str, Any]:
        """
        Full pipeline for real images:
        1. OCR via Typhoon OCR API
        2. Classify document type (Heuristic + LLM)
        3. Extracts structured data into typed Pydantic Schema via LLM
        """
        ocr_text = await self.ocr_image(image_path)
        doc_type = await self.classify_document(ocr_text, use_llm=use_llm)
        schema_model = await self.extract_document_data(ocr_text, doc_type, use_llm=use_llm)
        structured_data = schema_model.model_dump() if hasattr(schema_model, "model_dump") else schema_model
        
        return {
            "image_path": image_path,
            "doc_type": doc_type,
            "ocr_text": ocr_text,
            "structured_data": structured_data
        }

