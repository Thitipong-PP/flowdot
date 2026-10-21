from typing import Optional, Dict, Any
import time
import json
import re
import httpx
from app.config import settings

class FastPathRouter:
    """
    Independent Two-Step Fast-Path Router Module:
    
    Step 1: Deterministic Rule-Based Engine (Zero-Latency / Sub-2ms)
    - Directly intercepts exact keys from Rich Menu (e.g. 'menu_login', 'menu_contact')
    - Directly intercepts Thai keyword anchors (e.g. 'ล็อกอิน', 'เข้าสู่ระบบ', 'ติดต่อเจ้าหน้าที่', 'เบอร์โทร', 'คอลเซ็นเตอร์')
    - If conditions match and no financial keywords are present, returns immediately (bypass_llm: True, latency_ms < 2ms)
      without invoking any LLM model.
      
    Step 2: Satellite Worker Intent Classifier (qwen3:1.7b)
    - If Step 1 does not match, sends general text to local Ollama worker to classify intent
    - Disables Thinking Mode (temperature: 0.0, num_predict: 64, strips <think> tags)
    - Defensively extracts JSON via regex
    - If intent matches a menu with confidence >= 0.7, cuts off LLM and returns Fast-Path
    - If financial matter (slip, bill, deficit, loan, statements) or intent == 'orchestrate', returns None to proceed to Orchestrator.
    """
    STATIC_ROUTES = {
        "menu_login": {
            "bypass_llm": True,
            "title": "SME Web Portal Sign-In",
            "action": "open_url",
            "login_url": "https://app.sme-copilot.com/login"
        },
        "menu_manage_account": {
            "bypass_llm": True,
            "title": "User Account Settings",
            "action": "open_url",
            "settings_url": "https://app.sme-copilot.com/settings"
        },
        "menu_faq": {
            "bypass_llm": True,
            "title": "Frequently Asked Questions (FAQ)",
            "action": "open_url",
            "help_url": "https://app.sme-copilot.com/help"
        },
        "menu_contact": {
            "bypass_llm": True,
            "title": "Customer Support Center",
            "action": "contact_support",
            "phone": "02-123-4567",
            "line_oa": "@sme-finance-copilot"
        }
    }

    FAST_ANCHORS = {
        "menu_login": ["login", "sign in", "signin", "portal", "link to login", "ล็อกอิน", "เข้าสู่ระบบ", "เข้าระบบ", "ขอลิงก์ล็อกอิน"],
        "menu_manage_account": ["account settings", "manage account", "change password", "edit profile", "manage profile", "profile settings", "user settings", "ตั้งค่าบัญชี", "จัดการบัญชี", "เปลี่ยนรหัสผ่าน", "แก้ไขโปรไฟล์", "จัดการโปรไฟล์"],
        "menu_faq": ["faq", "frequently asked questions", "user guide", "manual", "help guide", "คำถามที่พบบ่อย", "วิธีใช้งานระบบ", "คู่มือการใช้งาน"],
        "menu_contact": ["contact support", "call center", "phone number", "admin", "customer service", "helpdesk", "contact us", "ติดต่อเจ้าหน้าที่", "คอลเซ็นเตอร์", "ขอเบอร์โทร", "เบอร์โทรศัพท์", "ติดต่อแอดมิน", "ติดต่อฝ่ายบริการ", "คุยกับเจ้าหน้าที่"]
    }

    FINANCIAL_INDICATORS = [
        "slip", "receipt", "invoice", "bill", "tax", "vat", "wht", "liquidity", "loan", "borrow", "credit", "dscr",
        "analysis", "income", "expense", "burn rate", "financials", "balance", "transfer", "statement",
        "financing", "finance", "financial", "fund", "funding", "capital", "interest", "rate",
        "สลิป", "ใบเสร็จ", "ใบแจ้งหนี้", "ภาษี", "หัก ณ ที่จ่าย", "ขาดสภาพคล่อง", "สินเชื่อ", "กู้เงิน", "กู้",
        "วิเคราะห์", "รายได้", "รายจ่าย", "งบการเงิน", "ยอดเงิน", "โอนเงิน", "เงินทุน", "แหล่งเงินทุน", "การเงิน"
    ]

    # =========================================================================
    # STEP 1: DETERMINISTIC RULE-BASED ENGINE (Sub-2ms, Zero LLM Call)
    # =========================================================================
    def step1_deterministic_rule_based(self, user_text_or_action: str) -> Optional[Dict[str, Any]]:
        """
        Step 1: Pure Python constraint & keyword filter.
        Guarantees sub-2ms response and bypass_llm: True without touching Ollama.
        """
        if not user_text_or_action:
            return None

        t0 = time.perf_counter()
        clean_text = user_text_or_action.strip().lower()

        # 1. Exact Rich Menu Key Match
        if clean_text in self.STATIC_ROUTES:
            route_data = dict(self.STATIC_ROUTES[clean_text])
            latency_ms = (time.perf_counter() - t0) * 1000
            route_data["latency_ms"] = round(latency_ms, 3)
            route_data["matched_by"] = "step1_exact_key"
            route_data["confidence"] = 1.0
            return route_data

        # 2. Check if text contains financial operations -> must NOT match Step 1
        has_financial = any(f in clean_text for f in self.FINANCIAL_INDICATORS)
        if has_financial:
            return None

        # 3. Direct Fast Anchor Keyword Match
        for route_key, anchors in self.FAST_ANCHORS.items():
            if any(a in clean_text for a in anchors):
                route_data = dict(self.STATIC_ROUTES[route_key])
                latency_ms = (time.perf_counter() - t0) * 1000
                route_data["latency_ms"] = round(latency_ms, 3)
                route_data["matched_by"] = "step1_anchor_keyword"
                route_data["confidence"] = 0.98
                return route_data

        return None

    # Backward compatibility alias
    def check_static_intent(self, user_text_or_action: str) -> Optional[Dict[str, Any]]:
        return self.step1_deterministic_rule_based(user_text_or_action)

    # =========================================================================
    # STEP 2: SATELLITE WORKER INTENT CLASSIFIER (qwen3:1.7b, No Thinking Mode)
    # =========================================================================
    async def step2_satellite_worker_classifier(self, user_text: str) -> Optional[Dict[str, Any]]:
        """
        Step 2: Calls local Satellite LLM worker (qwen3:1.7b) to semantically classify intent.
        Enforces thinking mode disablement, defensive regex extraction, and threshold validation.
        """
        if not user_text:
            return None

        t0 = time.perf_counter()

        # Prompt with strict constraint enforcement
        prompt = f"""You are an AI intent classifier for SME business users.
Analyze whether the following user message matches any Fast-Path menu:
1. "menu_login": Wants to log in, sign in, or get a link to SME Web Portal
2. "menu_manage_account": Wants account settings, change password, or manage profile
3. "menu_faq": Wants to see FAQ, help guide, or user manual
4. "menu_contact": Wants to contact support, call center, customer service, or admin
5. "orchestrate": Financial questions, revenue/expense analysis, payment slips, bills/invoices, SME loans, liquidity deficit, borrowing, or anything requiring calculation/deliberation

User message: "{user_text}"

Respond ONLY with JSON format:
{{"intent": "menu_login" | "menu_manage_account" | "menu_faq" | "menu_contact" | "orchestrate", "confidence": 0.0-1.0}}"""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/chat/completions",
                    json={
                        "model": settings.OLLAMA_WORKER_MODEL,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "You are an intent classifier. Respond ONLY with JSON format "
                                    '{"intent": "...", "confidence": ...}. Do not include markdown, '
                                    "explanations, or <think> tags."
                                )
                            },
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.0,
                        "max_tokens": 64,
                        "stream": False
                    }
                )
                if res.status_code == 200:
                    raw_content = res.json()["choices"][0]["message"]["content"].strip()
                    # Strip any <think> tags if generated by reasoning models
                    clean_content = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL).strip()
                    
                    # Defensive regex extraction of JSON block
                    match = re.search(r'\{.*\}', clean_content, re.DOTALL)
                    if match:
                        parsed = json.loads(match.group(0))
                        intent = parsed.get("intent")
                        confidence = float(parsed.get("confidence", 0.0))

                        # If intent matches menu with confidence >= 0.7, cut off LLM and return Fast-Path
                        if intent in self.STATIC_ROUTES and confidence >= 0.7:
                            route_data = dict(self.STATIC_ROUTES[intent])
                            latency_ms = (time.perf_counter() - t0) * 1000
                            route_data["latency_ms"] = round(latency_ms, 3)
                            route_data["matched_by"] = "step2_satellite_classifier"
                            route_data["confidence"] = confidence
                            return route_data
        except Exception as e:
            print(f"Fast-path Step 2 satellite classifier warning ({type(e).__name__}): {e}")

        # If financial matter, orchestrate, or low confidence -> return None to proceed to Orchestrator
        return None

    # Backward compatibility alias
    async def check_semantic_intent(self, user_text: str) -> Optional[Dict[str, Any]]:
        return await self.step2_satellite_worker_classifier(user_text)

    # =========================================================================
    # UNIFIED EVALUATOR (Step 1 -> Step 2 -> Orchestrator)
    # =========================================================================
    async def evaluate_fast_path(self, user_text_or_action: str) -> tuple[bool, Optional[Dict[str, Any]]]:
        """
        Two-Step Strict Fast-Path Evaluation:
        1. Step 1 (Deterministic Rule-Based): If exact key or anchor matches without financial keywords,
           returns (True, route_data) in < 2ms without invoking LLM.
        2. Step 2 (Satellite Worker Classifier): If natural language conveys fast-path intent (confidence >= 0.7),
           cuts off LLM ('ตัดจบ LLM') and returns (True, route_data).
        3. If neither matches (e.g. financial analysis, loans, receipts), returns (False, None) to proceed to Master Orchestrator.
        """
        # Step 1: Sub-2ms Deterministic Filter (Strictly NO LLM)
        step1_res = self.step1_deterministic_rule_based(user_text_or_action)
        if step1_res:
            return True, step1_res

        # Step 2: Satellite Worker Intent Classifier (qwen3:1.7b, No Thinking)
        step2_res = await self.step2_satellite_worker_classifier(user_text_or_action)
        if step2_res:
            return True, step2_res

        # Financial matter or unclassified -> Proceed to Master Orchestrator
        return False, None
