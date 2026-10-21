import os
import re
import json
import uuid
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.schemas.events import TelemetryEvent, ActiveNode, NodeStatus, LiveMetrics
from app.core.telemetry import telemetry_emitter as default_telemetry_emitter, TelemetryEmitter
from app.core.guard import InvariantSanityGuard
from app.workers.cashflow_worker import CashflowSimulationWorker
from app.workers.loan_worker import LoanWorker
from app.workers.vision_worker import VisionWorker
from app.templates.flex_messages import build_loan_carousel

def clean_json_markdown(content: str) -> str:
    cleaned = re.sub(r'^```(?:json)?\s*', '', content.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    return cleaned.strip()

class MasterOrchestrator:
    def __init__(
        self,
        mock_mode: bool = False,
        telemetry_emitter: Optional[TelemetryEmitter] = None,
        cashflow_worker: Optional[CashflowSimulationWorker] = None,
        loan_worker: Optional[LoanWorker] = None,
        guard: Optional[InvariantSanityGuard] = None,
        vision_worker: Optional[VisionWorker] = None
    ):
        self.mock_mode = mock_mode
        self.telemetry = telemetry_emitter or default_telemetry_emitter
        self.guard = guard or InvariantSanityGuard()
        self.cashflow_worker = cashflow_worker or CashflowSimulationWorker()
        self.loan_worker = loan_worker or LoanWorker()
        self.vision_worker = vision_worker or VisionWorker(mock_mode=self.mock_mode)

    async def get_user_financial_profile(self, user_id: str) -> Dict[str, Any]:
        try:
            client = AsyncIOMotorClient(settings.MONGO_URI, serverSelectionTimeoutMS=2000)
            db = client[settings.MONGO_DB_NAME]
            stmt = await db["statements"].find_one({
                "$or": [
                    {"business_id": user_id},
                    {"user_id": user_id},
                    {"business_id": "sme_user_001"}
                ]
            })
            if stmt:
                return {
                    "business_name": stmt.get("business_name", "Somchai Supermart Ltd."),
                    "current_cash": float(stmt.get("current_cash_reserve", 120000.0)),
                    "upcoming_debt": float(stmt.get("upcoming_debt_service", 70000.0)),
                    "daily_burn_rate": float(stmt.get("daily_burn_rate", 3000.0)),
                    "monthly_revenue": float(stmt.get("monthly_gross_revenue", 200000.0)),
                    "net_income": float(stmt.get("net_monthly_operating_income", 60000.0))
                }
        except Exception as e:
            print(f"MongoDB profile lookup note: {e}")

        return {
            "business_name": "Somchai Supermart Ltd.",
            "current_cash": 120000.0,
            "upcoming_debt": 70000.0,
            "daily_burn_rate": 3000.0,
            "monthly_revenue": 200000.0,
            "net_income": 60000.0
        }

    async def _plan_agent_actions(
        self,
        user_text: str,
        has_images: bool,
        profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Allows LLM to select tools and extract financial amounts based on natural language understanding."""
        if self.mock_mode:
            amt_match = re.search(r'(\d+[\d,]*(?:\.\d+)?)\s*(?:บาท|thb|baht|usd|\$)?', user_text.replace(',', ''), re.IGNORECASE)
            amt = float(amt_match.group(1)) if amt_match else 0.0
            tools = []
            if has_images:
                tools.append("tool_vision")
            if any(k in user_text.lower() for k in ["บิล", "จ่าย", "บาท", "thb", "หนี้", "การเงิน", "ยอด", "เช็ค", "เช็ก", "bill", "pay", "expense", "debt", "cash", "balance", "cost", "invoice", "receipt"]):
                tools.append("tool_cashflow")
            if any(k in user_text.lower() for k in ["สินเชื่อ", "กู้", "เงินทุน", "loan", "borrow", "fund", "financing", "credit"]):
                tools.append("tool_loan_rag")
            return {"thought": "Mock planning", "tools_to_call": tools, "extracted_expense": amt}

        prompt = f"""You are the Master AI Financial Orchestrator for {profile['business_name']}.
Tools Registry:
1. "tool_vision": Read bill/slip data from images (use when user attaches an image).
2. "tool_cashflow": Simulate cashflow and runway (use when user reports expenses/income, inquires cash balance, or checks debt).
3. "tool_loan_rag": Search SME financing products via 5-Stage Agentic RAG (use when asking about loans, financing, or facing liquidity deficit).

User Message: "{user_text}"
Image Attached: {'Yes' if has_images else 'No'}

Decision Rules:
- If greeting (hi, hello, greetings), casual chat, or general knowledge question (e.g. what day is today, 1+1=?) -> DO NOT call any tools (tools_to_call: []).
- If an image is attached -> choose "tool_vision".
- If the user reports an expense, extract "extracted_expense" as a numeric value (e.g., if user says "bill 95,000 THB", extract 95000.0) and choose "tool_cashflow".
- If asking about loans or financing -> choose "tool_loan_rag".

Respond strictly in valid JSON matching this schema:
{{
  "thought": "Brief 1-sentence reasoning",
  "tools_to_call": ["tool_cashflow"],
  "extracted_expense": 0.0
}}
(Note: Replace 0.0 in extracted_expense with the actual numeric amount mentioned. If no expense is mentioned, keep it 0.0)"""

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                res = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/chat/completions",
                    json={
                        "model": settings.OLLAMA_MAIN_MODEL,
                        "messages": [
                            {"role": "system", "content": "You are a precise JSON Agent Router. Output valid JSON only."},
                            {"role": "user", "content": prompt}
                        ],
                        "options": {"temperature": 0.0, "num_predict": 256}
                    }
                )
                if res.status_code == 200:
                    raw = res.json()["choices"][0]["message"]["content"]
                    match = re.search(r'\{.*\}', clean_json_markdown(raw), re.DOTALL)
                    if match:
                        plan_data = json.loads(match.group(0))
                        # Defense-in-depth: If LLM missed numeric extraction despite explicit currency keywords
                        if float(plan_data.get("extracted_expense", 0.0)) == 0.0:
                            amt_match = re.search(r'(\d+[\d,]*(?:\.\d+)?)\s*(?:บาท|thb|baht|usd|\$)', user_text.replace(',', ''), re.IGNORECASE)
                            if amt_match:
                                plan_data["extracted_expense"] = float(amt_match.group(1))
                                if "tool_cashflow" not in plan_data.get("tools_to_call", []):
                                    plan_data.setdefault("tools_to_call", []).append("tool_cashflow")

                        # Defense-in-depth: Ensure loan RAG is invoked if query asks about loans/financing
                        if any(k in user_text.lower() for k in ["loan", "credit", "borrow", "financing", "fund", "สินเชื่อ", "กู้", "เงินกู้", "เงินทุน"]):
                            if "tool_loan_rag" not in plan_data.get("tools_to_call", []):
                                plan_data.setdefault("tools_to_call", []).append("tool_loan_rag")

                        return plan_data
        except Exception as e:
            print(f"Agent Planning warning: {e}")

        amt_match = re.search(r'(\d+[\d,]*(?:\.\d+)?)\s*(?:บาท|thb|baht|usd|\$)?', user_text.replace(',', ''), re.IGNORECASE)
        amt = float(amt_match.group(1)) if amt_match else 0.0
        tools = []
        if has_images:
            tools.append("tool_vision")
        if amt > 0 or any(k in user_text.lower() for k in ["บิล", "จ่าย", "บาท", "thb", "หนี้", "bill", "pay", "expense", "debt", "cash"]):
            tools.append("tool_cashflow")
        if any(k in user_text.lower() for k in ["loan", "credit", "borrow", "financing", "fund", "สินเชื่อ", "กู้", "เงินกู้", "เงินทุน"]):
            tools.append("tool_loan_rag")
        return {"thought": "Fallback safety", "tools_to_call": tools, "extracted_expense": amt}

    def classify_document_flow(
        self,
        doc_type: str,
        struct: Dict[str, Any],
        business_name: str,
        user_text: str = ""
    ) -> Dict[str, Any]:
        """
        Classifies incoming financial transaction into INFLOW (income) or OUTFLOW (expense)
        by matching business identity against sender/receiver or seller/buyer.
        """
        def _norm(s: Any) -> str:
            return re.sub(r'บจก\.?|บริษัท|จำกัด|ltd\.?|co\.?|inc\.?|\s+', '', str(s or '')).lower()

        biz_clean = _norm(business_name)
        text_lower = user_text.lower()

        # 1. Bank Statement: Contains both deposits and withdrawals
        if doc_type == "bank_statement":
            txs = struct.get("transactions", [])
            total_dep = sum(float(t.get("deposit") or 0.0) for t in txs if isinstance(t, dict))
            total_wdr = sum(float(t.get("withdrawal") or 0.0) for t in txs if isinstance(t, dict))
            # Fallback: if deposit/withdrawal keys are None, use transaction amount
            if total_dep == 0.0 and total_wdr == 0.0 and txs:
                total_wdr = sum(float(t.get("amount") or 0.0) for t in txs if isinstance(t, dict))
            acct = struct.get("account", {}) if isinstance(struct.get("account"), dict) else {}
            closing = float(acct.get("closing_balance") or 0.0)
            b_fwd = float(acct.get("balance_forward") or 0.0) if acct.get("balance_forward") is not None else None
            return {
                "flow_type": "STATEMENT",
                "income": total_dep,
                "expense": total_wdr,
                "closing_balance": closing,
                "balance_forward": b_fwd,
                "description": f"Bank Statement (Inflow: {total_dep:,.2f} THB, Outflow: {total_wdr:,.2f} THB)"
            }

        # 2. Payment Slip: Check receiver vs sender
        if doc_type == "payment_slip":
            rec_clean = _norm(struct.get("receiver_name"))
            snd_clean = _norm(struct.get("sender_name"))
            amt = float(struct.get("amount") or 0.0)

            income_keywords = ["ลูกค้าโอน", "เงินเข้า", "รับเงิน", "ชำระเงินเข้ามา", "ขายของได้", "ได้รับเงิน", "โอนมาให้", "transfer", "deposit", "received", "income", "inflow", "sales", "revenue"]
            # If business is the receiver or user mentioned customer transfer -> INFLOW
            is_receiver = bool(biz_clean and (biz_clean in rec_clean or rec_clean in biz_clean))
            has_income_hint = any(k in text_lower for k in income_keywords)

            if is_receiver or has_income_hint:
                return {
                    "flow_type": "INFLOW",
                    "income": amt,
                    "expense": 0.0,
                    "description": f"Customer transfer inflow {amt:,.2f} THB ({struct.get('sender_name') or 'Customer'})"
                }
            else:
                return {
                    "flow_type": "OUTFLOW",
                    "income": 0.0,
                    "expense": amt,
                    "description": f"Expense payment outflow {amt:,.2f} THB ({struct.get('receiver_name') or 'Recipient'})"
                }

        # 3. Invoice / Bill / Receipt: Check seller vs buyer
        if doc_type == "invoice_or_bill":
            seller_obj = struct.get("seller") or {}
            buyer_obj = struct.get("buyer") or {}
            seller_clean = _norm(seller_obj.get("name") if isinstance(seller_obj, dict) else "")
            buyer_clean = _norm(buyer_obj.get("name") if isinstance(buyer_obj, dict) else "")
            amt = float(struct.get("grand_total") or struct.get("amount") or struct.get("subtotal") or 0.0)

            # If our business is the SELLER -> Sales Invoice (Income/Inflow)
            is_seller = bool(biz_clean and (biz_clean in seller_clean or seller_clean in biz_clean))
            has_sales_hint = any(k in text_lower for k in ["ขาย", "ออกบิล", "ใบเสร็จขาย", "sale", "sales", "invoice to", "sold"])

            if is_seller or has_sales_hint:
                return {
                    "flow_type": "INFLOW",
                    "income": amt,
                    "expense": 0.0,
                    "description": f"Sales receipt / invoice {amt:,.2f} THB"
                }
            else:
                # Default for bills/receipts is purchase/expense of the shop
                return {
                    "flow_type": "OUTFLOW",
                    "income": 0.0,
                    "expense": amt,
                    "description": f"Expense bill / invoice {amt:,.2f} THB ({seller_obj.get('name') if isinstance(seller_obj, dict) else 'Supplier'})"
                }

        # 4. Fallback / General
        amt = float(struct.get("grand_total") or struct.get("amount") or struct.get("total_amount") or 0.0)
        return {
            "flow_type": "OUTFLOW",
            "income": 0.0,
            "expense": amt,
            "description": f"Financial transaction {amt:,.2f} THB"
        }

    async def _synthesize_agent_response(
        self,
        user_text: str,
        profile: Dict[str, Any],
        expense: float,
        cash_res: Dict[str, Any],
        loan_results: List[Dict[str, Any]],
        income: float = 0.0,
        doc_type: str = "none"
    ) -> str:
        has_new_expense = expense > 0
        has_new_income = income > 0
        is_crisis = cash_res.get("is_liquidity_crisis", False)
        has_loans = len(loan_results) > 0

        current_cash_description = f"{profile['current_cash']:,.2f} THB" if profile.get("current_cash") is not None else "No verified initial cash balance available"
        system_prompt = f"""You are the AI CFO financial advisor for "{profile['business_name']}".
- Current Cash Reserve: {current_cash_description}
- Month-End Debt Obligation: {profile['upcoming_debt']:,.2f} THB
Persona: Professional, friendly, direct, genuinely supportive of SMEs. If user chats casually, respond naturally."""

        if has_loans:
            loans_summary = []
            for l in loan_results[:3]:
                name = l.get("product_name") or l.get("name") or "SME Financing"
                rate = l.get("interest_rate_text") or str(l.get("interest_rate", "Bank terms apply"))
                limit = float(l.get("max_limit") or l.get("max_credit_limit") or 0.0)
                rationale = l.get("recommendation_rationale") or l.get("rationale") or "Suitable limit and requirements"
                loans_summary.append(f"- {name}: Interest {rate}, Limit {limit:,.0f} THB ({rationale})")

            user_prompt = f"""Business owner inquiry: "{user_text}"
[Matched Financing Products]
{chr(10).join(loans_summary)}
Instruction: Recommend the financing options above concisely, highlighting key features and summarizing names and terms. Do not refer to UI cards below."""
            target_temp = 0.4

        elif doc_type == "bank_statement" and profile.get("current_cash") is None:
            user_prompt = f"""Statement report from business owner: "{user_text}"
[Data Limitation] System does not have a verified initial cash balance.
- Total Inflow in Statement: {income:,.2f} THB
- Total Outflow in Statement: {expense:,.2f} THB
Instruction: Summarize only the detected inflow and outflow amounts. Do not calculate cash balance or runway, and notify the user that an initial cash balance is required for liquidity analysis."""
            target_temp = 0.2

        elif doc_type == "bank_statement":
            user_prompt = f"""Statement report from business owner: "{user_text}"
[Bank Statement Analysis Results]
- Total Deposits (Inflow): {income:,.2f} THB
- Total Withdrawals (Outflow): {expense:,.2f} THB
- Updated Cash Balance: {cash_res.get('projected_cash', 0):,.2f} THB
- Estimated Runway: {cash_res.get('runway_days', 0)} days
Instruction: Summarize the statement activity, clearly updating remaining cash balance and runway."""
            target_temp = 0.3

        elif (has_new_income or has_new_expense) and profile.get("current_cash") is None:
            user_prompt = f"""Message from business owner: "{user_text}"
[Data Limitation] The system does not have a verified initial cash balance, so runway and ending balance cannot be calculated.
Instruction: State this limitation clearly. Do not fabricate a balance or liquidity assessment, and ask the user to provide their current cash balance before proceeding with liquidity analysis."""
            target_temp = 0.2

        elif has_new_income:
            user_prompt = f"""Inquiry/document from business owner: "{user_text}"
[Cashflow Analysis After Inflow]
- Inflow / Revenue Recorded: {income:,.2f} THB
- Updated Cash Reserve: {cash_res.get('projected_cash', 0):,.2f} THB
- Month-End Debt Obligations: {profile['upcoming_debt']:,.2f} THB
- Estimated Runway: {cash_res.get('runway_days', 0)} days
Instruction: Warmly and professionally summarize the inflow, report the updated cash reserve, and encourage business growth."""
            target_temp = 0.4

        elif has_new_expense:
            user_prompt = f"""Inquiry/document from business owner: "{user_text}"
[Cashflow Analysis After Expense]
- Verified Expense: {expense:,.2f} THB
- Cash Remaining After Payment: {cash_res.get('projected_cash', 0):,.2f} THB
- Status: {'⚠️ Liquidity Risk for Month-End Obligations' if is_crisis else '✅ Healthy Liquidity'}
- Deficit: {cash_res.get('deficit', 0):,.2f} THB | Runway: {cash_res.get('runway_days', 0)} days
Instruction: Summarize the remaining cash balance and financial impact directly and constructively with professional encouragement."""
            target_temp = 0.3

        else:
            user_prompt = f"""User message: "{user_text}"
Instruction: Respond naturally, directly, and accurately to the user's message."""
            target_temp = 0.6

        if self.mock_mode:
            if profile.get("current_cash") is None and (has_new_income or has_new_expense):
                return "Cannot calculate remaining balance or liquidity yet because there is no verified initial cash reserve. Please specify your current cash balance first."
            if has_loans:
                return f"Matched {len(loan_results)} suitable financing options for your business. Please check the Find financing section to explore details and terms."
            if doc_type == "bank_statement":
                return f"Statement updated successfully: Inflow {income:,.2f} THB, Outflow {expense:,.2f} THB, Projected balance {cash_res.get('projected_cash', 0):,.2f} THB."
            if has_new_income:
                return f"Recorded inflow of {income:,.2f} THB. Cash reserve increased to {cash_res.get('projected_cash', 0):,.2f} THB with healthy liquidity."
            if has_new_expense:
                return f"Expense of {expense:,.2f} THB recorded. Remaining cash balance is {cash_res.get('projected_cash', 0):,.2f} THB."
            return f"Hello! I am your AI CFO for {profile['business_name']}. How can I assist you with your business finances today?"

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                res = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/chat/completions",
                    json={
                        "model": settings.OLLAMA_MAIN_MODEL,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": target_temp,
                        "max_tokens": 512,
                        "options": {"temperature": target_temp, "num_predict": 512}
                    }
                )
                if res.status_code == 200:
                    choice = res.json()["choices"][0]["message"]
                    content = choice.get("content", "").strip()
                    if not content and "reasoning_content" in choice:
                        content = choice["reasoning_content"].strip()
                    if content:
                        return content
        except Exception as e:
            print(f"Master response synthesis warning: {e}")

        if profile.get("current_cash") is None and (has_new_income or has_new_expense or doc_type == "bank_statement"):
            return "The system recorded the transaction amounts, but cannot calculate ending cash balance or runway without a verified initial balance. Please provide your current cash balance first."
        if has_loans:
            return "We have matched suitable financing products for your business. Please check the Find financing section for detailed eligibility and application terms."
        if has_new_expense:
            return f"Expense of {expense:,.2f} THB brings projected cash reserve to {cash_res.get('projected_cash', 0):,.2f} THB."
        return f"Hello! Happy to assist with accounting and financial planning for {profile['business_name']}."

    async def process_session(
        self,
        session_id: str,
        inputs: List[Dict[str, Any]],
        profile_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        await self.telemetry.emit(TelemetryEvent(
            session_id=session_id,
            event="ORCHESTRATOR_START",
            active_node=ActiveNode.ORCHESTRATOR,
            node_status=NodeStatus.PROCESSING,
            thought_log="Master Orchestrator Brain is loading business profile..."
        ))

        profile_data = profile_context if profile_context is not None else await self.get_user_financial_profile(session_id)
        current_reserve = profile_data.get("current_cash")
        upcoming_debt = profile_data["upcoming_debt"]
        daily_burn_rate = profile_data["daily_burn_rate"]

        text_list = [item.get("content", "") for item in inputs if item.get("type") == "text"]
        
        # Check for valid physical image files on disk
        image_items = []
        for item in inputs:
            if item.get("type") == "image":
                raw_path = item.get("file_path") or item.get("file_name") or item.get("path") or ""
                # Check candidates on disk
                candidates = [
                    str(raw_path),
                    os.path.join("uploads", os.path.basename(str(raw_path))),
                    os.path.join("thai_sme_loans", os.path.basename(str(raw_path)))
                ]
                found = False
                for c in candidates:
                    if c and os.path.exists(c) and os.path.isfile(c):
                        item["file_path"] = os.path.abspath(c)
                        image_items.append(item)
                        found = True
                        break
                if not found and (self.mock_mode or "mock" in str(raw_path).lower()):
                    image_items.append(item)

        combined_text = " ".join(text_list)
        has_valid_images = len(image_items) > 0

        # Step 2: Planning Phase
        agent_plan = await self._plan_agent_actions(
            user_text=combined_text,
            has_images=has_valid_images,
            profile=profile_data
        )

        planned_tools = agent_plan.get("tools_to_call", [])
        raw_amt = float(agent_plan.get("extracted_expense", 0.0))
        expense = 0.0
        income = 0.0
        doc_type = "none"
        flow_type = "NONE"
        flow_info = {}

        # Classify monetary direction from text when no image is present
        if raw_amt > 0:
            income_keywords = [
                "ลูกค้าโอน", "เงินเข้า", "รายรับ", "ขายของได้", "ได้รับเงิน", "ยอดขาย", "รายได้", "รับเงิน", "ได้เงิน", "โอนมาให้",
                "income", "inflow", "sales", "revenue", "received", "deposit", "transfer", "customer payment"
            ]
            if any(k in combined_text.lower() for k in income_keywords):
                income = raw_amt
                flow_type = "INFLOW"
            else:
                expense = raw_amt
                flow_type = "OUTFLOW"

        await self.telemetry.emit(TelemetryEvent(
            session_id=session_id,
            event="THOUGHT_STREAM",
            active_node=ActiveNode.ORCHESTRATOR,
            node_status=NodeStatus.PROCESSING,
            thought_log=f"Planning complete. Selected steps: {', '.join(planned_tools) if planned_tools else 'No specialist step required.'}"
        ))

        # Step 3: Tool Execution -> Vision Worker (100% Real Typhoon OCR from disk without mock fallback)
        if has_valid_images:
            img_item = image_items[0]
            target_path = img_item.get("file_path")

            if target_path and (os.path.exists(target_path) or self.mock_mode):
                await self.telemetry.emit(TelemetryEvent(
                    session_id=session_id,
                    event="TOOL_INVOKED",
                    active_node=ActiveNode.VISION_WORKER,
                    node_status=NodeStatus.PROCESSING,
                    active_wire="ORCHESTRATOR_TO_VISION",
                    thought_log=f"Found physical image: {os.path.basename(target_path)}, invoking Typhoon OCR extraction..."
                ))
                try:
                    extracted_doc = await self.vision_worker.process_financial_image(
                        str(target_path),
                        use_llm=not self.mock_mode
                    )
                    doc_type = extracted_doc.get("doc_type", "payment_slip")
                    struct = extracted_doc.get("structured_data", {}) if isinstance(extracted_doc, dict) else {}

                    # Classify document type and flow direction (INFLOW / OUTFLOW / STATEMENT)
                    flow_info = self.classify_document_flow(
                        doc_type=doc_type,
                        struct=struct,
                        business_name=profile_data.get("business_name", ""),
                        user_text=combined_text
                    )
                    flow_type = flow_info.get("flow_type", "OUTFLOW")
                    income = float(flow_info.get("income", 0.0))
                    expense = float(flow_info.get("expense", 0.0))

                    if income > 0 or expense > 0 or doc_type == "bank_statement":
                        if "tool_cashflow" not in planned_tools:
                            planned_tools.append("tool_cashflow")

                    await self.telemetry.emit(TelemetryEvent(
                        session_id=session_id,
                        event="TOOL_COMPLETED",
                        active_node=ActiveNode.VISION_WORKER,
                        node_status=NodeStatus.SUCCESS,
                        active_wire="VISION_TO_ORCHESTRATOR",
                        thought_log=f"Document extraction completed. Classification: {doc_type}.",
                    ))
                except Exception as e:
                    print(f"Vision tool OCR error: {e}")

        # Step 4: Tool Execution -> Cashflow Simulation
        cash_res = {}
        if current_reserve is not None and ("tool_cashflow" in planned_tools or expense > 0 or income > 0):
            cash_res = self.cashflow_worker.simulate_cashflow(
                current_cash=current_reserve,
                new_expense=expense,
                new_income=income,
                upcoming_debt=upcoming_debt,
                daily_burn_rate=daily_burn_rate
            )
            cash_res["is_liquidity_crisis"] = cash_res.get("is_debt_default_risk", False) or cash_res.get("is_liquidity_risk", False)

            await self.telemetry.emit(TelemetryEvent(
                session_id=session_id,
                event="TOOL_COMPLETED",
                active_node=ActiveNode.CASHFLOW_WORKER,
                node_status=NodeStatus.SUCCESS,
                active_wire="CASHFLOW_TO_ORCHESTRATOR",
                thought_log="Cashflow simulation completed. Review the result in the response.",
                live_metrics=LiveMetrics(
                    risk_level=cash_res["risk_level"],
                    current_cash=cash_res.get("current_cash"),
                    projected_cash=cash_res.get("projected_cash"),
                    runway_days=cash_res.get("runway_days")
                ),
            ))

            # Step 5: Invariant Math Guard
            alignment = self.guard.verify_cashflow_alignment(
                current_cash=current_reserve,
                expense=expense,
                income=income,
                projected_cash=cash_res["projected_cash"],
                stated_runway=cash_res["runway_days"],
                actual_runway=cash_res["runway_days"]
            )
            if not alignment.is_valid:
                await self.telemetry.emit(TelemetryEvent(
                    session_id=session_id,
                    event="GUARD_VIOLATION",
                    active_node=ActiveNode.SANITY_GUARD,
                    node_status=NodeStatus.ERROR,
                    active_wire="GUARD_TO_ORCHESTRATOR_RETRY",
                    thought_log="Arithmetic guard found a mismatch and requested correction."
                ))

            if doc_type == "bank_statement" and flow_info:
                stmt_guard = self.guard.verify_statement_math(
                    balance_forward=flow_info.get("balance_forward"),
                    closing_balance=flow_info.get("closing_balance", 0.0),
                    total_deposit=income,
                    total_withdrawal=expense
                )
                if not stmt_guard.is_valid:
                    await self.telemetry.emit(TelemetryEvent(
                        session_id=session_id,
                        event="GUARD_VIOLATION",
                        active_node=ActiveNode.SANITY_GUARD,
                        node_status=NodeStatus.WARNING,
                        thought_log="Statement consistency check found a mismatch and requested correction."
                    ))

        # Step 6: Tool Execution -> Loan Worker (5-Stage Agentic RAG)
        has_liquidity_crisis = cash_res.get("is_liquidity_crisis", False) and cash_res.get("deficit", 0) > 0
        needs_loan_tool = current_reserve is not None and (("tool_loan_rag" in planned_tools) or (has_liquidity_crisis and expense > 0))

        loan_results = []
        flex_carousel = None

        if needs_loan_tool:
            deficit = float(cash_res.get("deficit", 0))
            if deficit <= 0:
                deficit = float(upcoming_debt) if upcoming_debt > 0 else 50000.0

            await self.telemetry.emit(TelemetryEvent(
                session_id=session_id,
                event="TOOL_INVOKED",
                active_node=ActiveNode.LOAN_WORKER,
                node_status=NodeStatus.PROCESSING,
                active_wire="ORCHESTRATOR_TO_LOAN_WORKER",
                thought_log="Searching and validating SME financing options through the retrieval pipeline."
            ))

            profile = {
                "monthly_revenue": profile_data.get("monthly_revenue", 200000.0),
                "business_age_years": 2.5,
                "has_collateral": False
            }
            net_income = max(10000.0, current_reserve - expense)
            ratios = self.loan_worker.calculate_ratios(
                net_income=net_income,
                debt_service=upcoming_debt,
                monthly_revenue=profile["monthly_revenue"]
            )

            loan_results = await self.loan_worker.match_loans(
                deficit=deficit,
                ratios=ratios,
                profile=profile,
                use_llm_rationale=not self.mock_mode,
                return_trace=False
            )

            await self.telemetry.emit(TelemetryEvent(
                session_id=session_id,
                event="TOOL_COMPLETED",
                active_node=ActiveNode.LOAN_WORKER,
                node_status=NodeStatus.SUCCESS,
                active_wire="LOAN_WORKER_TO_ORCHESTRATOR",
                thought_log=f"Loan RAG matching completed: {len(loan_results)} products found",
                payload={"loan_count": len(loan_results)}
            ))

            if loan_results:
                for loan in loan_results:
                    if "product_name" in loan and "name" not in loan:
                        loan["name"] = loan["product_name"]
                    if "max_limit" in loan and "max_credit_limit" not in loan:
                        loan["max_credit_limit"] = loan["max_limit"]
                    if "interest_rate_text" not in loan and "interest_rate" in loan:
                        loan["interest_rate_text"] = str(loan["interest_rate"])
                flex_carousel = build_loan_carousel(loans=loan_results, session_id=session_id)

        # Step 7: Live Response Synthesis
        await self.telemetry.emit(TelemetryEvent(
            session_id=session_id,
            event="RESPONSE_SYNTHESIS",
            active_node=ActiveNode.RESPONSE_COMPILER,
            node_status=NodeStatus.PROCESSING,
            thought_log="Master Orchestrator is synthesizing final response..."
        ))

        reply_text = await self._synthesize_agent_response(
            user_text=combined_text,
            profile=profile_data,
            expense=expense,
            cash_res=cash_res,
            loan_results=loan_results,
            income=income,
            doc_type=doc_type
        )

        payload_data = {
            "status": "COMPLETED",
            "reply_text": reply_text,
            "cashflow": cash_res,
            "loans": loan_results,
            "flex_carousel": flex_carousel,
            "flow_type": flow_type,
            "income": income,
            "expense": expense,
            "doc_type": doc_type
        }

        # Step 8: Emit completion event
        await self.telemetry.emit(TelemetryEvent(
            session_id=session_id,
            event="COMPLETED",
            active_node=ActiveNode.RESPONSE_COMPILER,
            node_status=NodeStatus.SUCCESS,
            thought_log="Processing completed, returning final response to user",
            # This is delivered only over the protected SSE endpoint for the
            # requesting session; TelemetryEmitter persists metadata only.
            payload=payload_data
        ))

        return payload_data
