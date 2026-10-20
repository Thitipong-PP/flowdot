import sys
import os
import time
from typing import Dict, Any, List, Optional
import httpx
from app.config import settings
from app.db.vector_store import MongoDBAtlasVectorSearch

os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Ensure UTF-8 output on Windows consoles to prevent charmap UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

class LoanWorker:
    def __init__(self, vector_store: Optional[MongoDBAtlasVectorSearch] = None):
        self.vector_store = vector_store or MongoDBAtlasVectorSearch()

    def calculate_ratios(self, net_income: float, debt_service: float, monthly_revenue: float) -> Dict[str, float]:
        """Calculates DSCR (Debt Service Coverage Ratio) and DTI (Debt-to-Income)."""
        dscr = round(net_income / max(1.0, debt_service), 2)
        dti = round(debt_service / max(1.0, monthly_revenue), 2)
        return {"dscr": dscr, "dti": dti}

    # =========================================================================
    # STAGE 1: PRE-RETRIEVAL (Context-Augmented Query Formulation)
    # =========================================================================
    def stage1_synthesize_query(
        self,
        deficit: float,
        ratios: Dict[str, float],
        profile: Dict[str, Any]
    ) -> str:
        """
        Synthesizes a natural semantic description query from real user financial metrics:
        - Incorporates deficit amount, monthly revenue, business age, DSCR ratio, and collateral status.
        - Avoids any hardcoded numerical thresholds, leaving constraint checking to Stage 3 and semantic matching to E5.
        """
        rev = float(profile.get("monthly_revenue", 0.0))
        age = float(profile.get("business_age_years", 1.0))
        has_col = bool(profile.get("has_collateral", False))
        dscr = float(ratios.get("dscr", 1.0))

        col_desc = "มีหลักทรัพย์ค้ำประกัน" if has_col else "ไม่มีหลักทรัพย์ค้ำประกัน ต้องการ Clean Loan หรือ บสย. ค้ำประกัน"

        # Natural Semantic Description formulation
        query = (
            f"ผู้ประกอบการ SME ดำเนินธุรกิจมาแล้ว {age:.1f} ปี รายได้เดือนละ {rev:,.0f} บาท "
            f"ขาดสภาพคล่องต้องการสินเชื่อวงเงิน {deficit:,.0f} บาท "
            f"ความสามารถในการชำระหนี้ DSCR {dscr:.2f} เท่า {col_desc}"
        )
        return query

    # =========================================================================
    # STAGE 2: HYBRID RETRIEVAL (MongoDB Atlas Vector Search)
    # =========================================================================
    async def stage2_hybrid_retrieve(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Executes real MongoDB Atlas $vectorSearch + keyword hybrid ranking.
        """
        return await self.vector_store.hybrid_search(query, limit=limit)

    # =========================================================================
    # STAGE 3: DETERMINISTIC GRADING (Pure Python Invariant Grader)
    # =========================================================================
    def stage3_grade_candidate(
        self,
        candidate: Dict[str, Any],
        profile: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Pure Python Constraint Grader:
        Evaluates hard underwriting rules without LLM hallucination.
        """
        rules = candidate.get("extra_rules", {})
        min_rev = rules.get("min_revenue", 0.0)
        min_age = rules.get("min_age_years", 0.0)
        req_col = rules.get("requires_collateral", False)

        rev = float(profile.get("monthly_revenue", 0.0))
        age = float(profile.get("business_age_years", 1.0))
        has_col = bool(profile.get("has_collateral", False))

        if rev < min_rev:
            return False, f"REVENUE_BELOW_MINIMUM: {rev:,.0f} < {min_rev:,.0f}"
        if age < min_age:
            return False, f"AGE_BELOW_MINIMUM: {age:.1f}y < {min_age:.1f}y"
        if req_col and not has_col:
            return False, "COLLATERAL_REQUIRED"
        return True, None

    # =========================================================================
    # STAGE 4: CRAG RECOVERY LOOP (Diagnostic Evaluation & Dynamic Query Relaxation)
    # =========================================================================
    async def stage4_crag_recovery(
        self,
        diagnostics: List[tuple[Dict[str, Any], str]],
        profile: Dict[str, Any],
        deficit: float,
        existing_candidate_ids: Optional[set] = None
    ) -> List[Dict[str, Any]]:
        """
        Corrective RAG (CRAG) Self-Correction Loop:
        1. Analyzes rejection diagnostics dynamically (e.g. COLLATERAL_REQUIRED, AGE_BELOW_MINIMUM, REVENUE_BELOW_MINIMUM).
        2. Dynamically formulates a relaxed semantic query tailored to the user's actual deficit and profile constraints.
        3. Re-retrieves alternative candidate products from MongoDB Atlas (max 1 loop).
        4. Validates each candidate with the deterministic grader and deduplicates by product ID.
        """
        existing_ids = existing_candidate_ids or set()
        rejection_reasons = [reason for _, reason in diagnostics]
        rev = float(profile.get("monthly_revenue", 0.0))
        age = float(profile.get("business_age_years", 1.0))

        # Dynamic query relaxation based on actual diagnostic feedback
        relaxation_clauses = [f"สินเชื่อ SME ขาดสภาพคล่อง {deficit:,.0f} บาท ดำเนินธุรกิจ {age:.1f} ปี"]

        if any("COLLATERAL_REQUIRED" in r for r in rejection_reasons):
            relaxation_clauses.append("ไม่มีหลักทรัพย์ค้ำประกัน สินเชื่อ Clean Loan บสย. PGS โครงการค้ำประกันเต็มวงเงิน")
        elif any("AGE_BELOW_MINIMUM" in r or "REVENUE_BELOW_MINIMUM" in r for r in rejection_reasons):
            relaxation_clauses.append(f"รายได้ {rev:,.0f} บาทต่อเดือน สินเชื่อรายย่อย ไมโครไฟแนนซ์ บสย. เกณฑ์ยืดหยุ่น")
        else:
            relaxation_clauses.append("สินเชื่อหมุนเวียนระยะสั้น อัตราดอกเบี้ยผ่อนปรน")

        relaxed_query = " ".join(relaxation_clauses)
        mode_label = "In-Memory FAISS + BM25 (RRF)" if getattr(settings, "RETRIEVAL_MODE", "in_memory") == "in_memory" and self.vector_store.is_warmed_up() else "MongoDB Atlas ($vectorSearch)"
        print(f"   📡 [CRAG Retrieval] Retrieving alternative loan products (Mode: {mode_label})...", flush=True)

        re_candidates = await self.vector_store.hybrid_search(relaxed_query, limit=5)
        recovered = []
        for c in re_candidates:
            cid = c.get("id")
            if cid and cid not in existing_ids:
                passed, reason = self.stage3_grade_candidate(c, profile)
                if passed:
                    recovered.append(c)
                    existing_ids.add(cid)
                    print(f"       ✨ [Recovered Candidate] {c.get('product_name')} [{c.get('bank')}] passed relaxed criteria", flush=True)
                else:
                    print(f"       ⚠️ [Still Ineligible] {c.get('product_name')} [{c.get('bank')}] -> {reason}", flush=True)

        print(f"   🎉 Successfully recovered {len(recovered)} alternative products", flush=True)
        return recovered

    # =========================================================================
    # STAGE 5: SYNTHESIS, SCORING & CHECKLIST GENERATION
    # =========================================================================
    async def stage5_synthesize_recommendations(
        self,
        candidates: List[Dict[str, Any]],
        deficit: float,
        ratios: Dict[str, float],
        profile: Dict[str, Any],
        use_llm_rationale: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Synthesizes approved loan products:
        - Calculates underwriting Approval Probability (%) using DSCR tiers.
        - Generates tailored Thai recommendation rationale via local Satellite LLM (qwen3:1.7b).
        - Compiles Required Document Checklist for loan submission.
        - Structures output ready for LINE Carousel Flex Message rendering.
        """
        dscr = float(ratios.get("dscr", 1.0))
        synthesized = []

        for p in candidates:
            # Underwriting probability rule based on DSCR
            if dscr >= 1.5:
                prob = 85
            elif dscr >= 1.2:
                prob = 70
            elif dscr >= 1.0:
                prob = 55
            else:
                prob = 40

            if use_llm_rationale:
                rationale = await self.generate_loan_rationale(p, deficit, ratios, profile)
            else:
                rationale = (
                    f"ครอบคลุมยอดขาดสภาพคล่อง {deficit:,.2f} บาท "
                    f"สอดคล้องกับ DSCR {dscr:.2f} เท่า และรองรับเงื่อนไขธุรกิจ"
                )

            # Ensure complete checklist of real submission documents
            required_docs = list(p.get("required_documents") or [
                "ภ.พ.30 ย้อนหลัง 6 เดือน",
                "Bank Statement ย้อนหลัง 6 เดือน",
                "สำเนาบัตรประชาชนกรรมการผู้มีอำนาจ"
            ])

            synthesized.append({
                **p,
                "approval_probability": prob,
                "deficit_covered": deficit,
                "recommendation_rationale": rationale,
                "required_documents": required_docs,
                "flex_carousel_ready": True
            })

        return synthesized

    async def generate_loan_rationale(
        self,
        product: Dict[str, Any],
        deficit: float,
        ratios: Dict[str, float],
        profile: Dict[str, Any]
    ) -> str:
        """Calls Satellite Worker LLM (qwen3:1.7b) to generate a live, contextual Thai recommendation."""
        dscr = ratios.get("dscr", 1.2)
        p_name = product.get("product_name", "สินเชื่อ SME")
        bank = product.get("bank", "ธนาคาร")

        print(f"   🤖 [Stage 5: Live Ollama LLM] Requesting live analysis from {settings.OLLAMA_WORKER_MODEL} for '{p_name}' [{bank}]...", flush=True)

        col_status = 'มีหลักทรัพย์ค้ำประกัน' if profile.get('has_collateral') else 'ไม่มีหลักทรัพย์ค้ำประกัน (ใช้ บสย./Clean Loan)'
        prompt = (
            f"คุณคือผู้เชี่ยวชาญสินเชื่อธุรกิจ SME กรุณาเขียนคำอธิบายสั้นๆ (1-2 ประโยค) แนะนำผลิตภัณฑ์ '{p_name}' ของ '{bank}' "
            f"สำหรับร้านค้าที่ขาดสภาพคล่อง {deficit:,.0f} บาท โดยมีรายได้เดือนละ {profile.get('monthly_revenue', 0):,.0f} บาท "
            f"และค่า DSCR อยู่ที่ {dscr} เท่า สถานะหลักประกัน: {col_status} ห้ามระบุข้อมูลหลักประกันขัดแย้งกับความเป็นจริง "
            f"ตอบกระชับ เป็นทางการ และตรงจุด"
        )
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                res = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/chat/completions",
                    json={
                        "model": settings.OLLAMA_WORKER_MODEL,
                        "messages": [
                            {"role": "system", "content": "คุณคือผู้เชี่ยวชาญวิเคราะห์สินเชื่อ SME ตอบภาษาไทยสุภาพกระชับ ไม่ต้องคิดในแท็ก think ให้ตอบตรงคำตอบทันที"},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.2,
                        "max_tokens": 150
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"].strip()
                    if content:
                        print(f"     ✅ Received live recommendation from LLM", flush=True)
                        return content
        except Exception as e:
            print(f"Loan rationale LLM generation exception ({type(e).__name__}): {e}")

        # In case of absolute LLM outage, return factual synthesis
        return f"อนุมัติเบื้องต้นสอดคล้องกับ DSCR {dscr:.2f} เท่า ครอบคลุมยอดขาดสภาพคล่อง {deficit:,.2f} บาท ของ {bank}"

    # =========================================================================
    # MASTER 5-STAGE AGENTIC RAG ORCHESTRATION PIPELINE
    # =========================================================================
    async def match_loans(
        self,
        deficit: float,
        ratios: Dict[str, float],
        profile: Optional[Dict[str, Any]] = None,
        use_llm_rationale: bool = True,
        return_trace: bool = False
    ) -> Any:
        """
        Complete 5-Stage Financial Agentic RAG Pipeline:
        Stage 1: Pre-Retrieval (Context-Augmented Query Formulation)
        Stage 2: Hybrid Retrieval (MongoDB Atlas Vector Search)
        Stage 3: Deterministic Grading (Pure Python Invariant Grader)
        Stage 4: CRAG Recovery Loop (Triggered if passed candidates < 2 to ensure sufficient options for Flex Carousel)
        Stage 5: Synthesis, Scoring & Required Document Checklist (Live LLM Rationale)
        """
        if profile is None:
            profile = {"monthly_revenue": 100000.0, "business_age_years": 2.0, "has_collateral": False}

        trace: Dict[str, Any] = {}

        # -------------------------------------------------------------
        # STAGE 1: Pre-Retrieval (Query Synthesis)
        # -------------------------------------------------------------
        print("\n🧠 [STAGE 1: PRE-RETRIEVAL] Synthesizing natural semantic context query from financial figures...", flush=True)
        print(f"   - Financial Metrics: Deficit={deficit:,.0f} THB | Revenue={profile.get('monthly_revenue', 0):,.0f} THB | Age={profile.get('business_age_years', 0):.1f}y | DSCR={ratios.get('dscr', 0):.2f} | Collateral={profile.get('has_collateral', False)}", flush=True)
        stage1_query = self.stage1_synthesize_query(deficit, ratios, profile)
        print(f"   - Synthesized Search Query: \"{stage1_query}\"", flush=True)
        trace["stage1_query"] = stage1_query

        # -------------------------------------------------------------
        # STAGE 2: Hybrid Retrieval (Dual-Mode: In-Memory RRF / Atlas)
        # -------------------------------------------------------------
        mode_label = "In-Memory FAISS + BM25 (RRF)" if getattr(settings, "RETRIEVAL_MODE", "in_memory") == "in_memory" and self.vector_store.is_warmed_up() else "MongoDB Atlas ($vectorSearch)"
        print(f"\n📡 [STAGE 2: HYBRID RETRIEVAL] Searching loan products (Mode: {mode_label})...", flush=True)
        t0_retrieval = time.perf_counter()
        raw_candidates = await self.stage2_hybrid_retrieve(stage1_query, limit=5)
        retrieval_ms = (time.perf_counter() - t0_retrieval) * 1000
        print(f"   - Retrieved {len(raw_candidates)} raw candidates (Retrieval speed: {retrieval_ms:.2f} ms)", flush=True)
        for idx, c in enumerate(raw_candidates, 1):
            score_val = c.get("score")
            score_str = f" | Score: {score_val:.4f}" if score_val is not None else ""
            print(f"       {idx}. {c.get('product_name')} [{c.get('bank')}]{score_str}", flush=True)
        trace["stage2_retrieved_count"] = len(raw_candidates)
        trace["stage2_candidates"] = [c.get("product_name") for c in raw_candidates]
        trace["stage2_latency_ms"] = round(retrieval_ms, 2)

        # -------------------------------------------------------------
        # STAGE 3: Deterministic Grading (Pure Python)
        # -------------------------------------------------------------
        print(f"\n⚖️ [STAGE 3: DETERMINISTIC GRADING] Evaluating financial hard constraints (Pure Python)...", flush=True)
        passed_candidates = []
        diagnostics = []
        seen_ids = set()

        for c in raw_candidates:
            passed, reason = self.stage3_grade_candidate(c, profile)
            if passed:
                cid = c.get("id")
                if cid not in seen_ids:
                    passed_candidates.append(c)
                    seen_ids.add(cid)
            else:
                diagnostics.append((c, reason))

        print(f"   - Passed immediately: {len(passed_candidates)} products", flush=True)
        if diagnostics:
            print(f"   - Ineligible candidates with rejection diagnostics:", flush=True)
            for c, reason in diagnostics:
                print(f"       ❌ {c.get('product_name')} [{c.get('bank')}] -> {reason}", flush=True)

        trace["stage3_passed_count"] = len(passed_candidates)
        trace["stage3_diagnostics"] = [(c.get("product_name"), r) for c, r in diagnostics]

        # -------------------------------------------------------------
        # STAGE 4: CRAG Recovery Loop (Agentic Self-Correction when len < 2)
        # -------------------------------------------------------------
        crag_triggered = False
        # Agentic principle: Ensure at least 2 qualified choices for LINE Carousel display
        if len(passed_candidates) < 2 and diagnostics:
            crag_triggered = True
            print(f"\n🔄 [STAGE 4: CRAG RECOVERY LOOP] Candidates < 2 ({len(passed_candidates)}/2) -> Triggering CRAG self-correction to recover candidates for Carousel", flush=True)
            recovered_candidates = await self.stage4_crag_recovery(
                diagnostics=diagnostics,
                profile=profile,
                deficit=deficit,
                existing_candidate_ids=seen_ids
            )
            passed_candidates.extend(recovered_candidates)
            trace["stage4_recovered_count"] = len(recovered_candidates)
            trace["stage4_recovered"] = [c.get("product_name") for c in recovered_candidates]
        else:
            print(f"\n🔄 [STAGE 4: CRAG RECOVERY LOOP] Skipping recovery ({len(passed_candidates)} qualified candidates found)", flush=True)

        trace["stage4_crag_triggered"] = crag_triggered

        # -------------------------------------------------------------
        # FALLBACK GUARD: Do not recommend rejected candidates
        # -------------------------------------------------------------
        final_candidates = list(passed_candidates)

        if not final_candidates:
            print(f"\n⚠️ [UNDERWRITING ALERT] No loan products met criteria even after CRAG round", flush=True)
            print(f"   - Deterministic Guard: Denied standard loan recommendations", flush=True)
            print(f"   - Providing alternative Micro/Nano finance advisory instead", flush=True)

            advisory_item = {
                "id": "advisory_nano_micro_finance",
                "product_name": "ไม่พบผลิตภัณฑ์ที่เข้าเกณฑ์เนื่องจากรายได้ต่ำกว่าเกณฑ์ขั้นต่ำของสถาบันการเงิน",
                "bank": "คำแนะนำทางเลือกสำหรับธุรกิจรายย่อย",
                "type": "Micro/Nano Finance Alternative",
                "interest_rate": "ตามเกณฑ์สถาบันการเงินรายย่อย",
                "max_limit": 50000.0,
                "approval_probability": 0,
                "deficit_covered": 0.0,
                "recommendation_rationale": (
                    "ไม่พบผลิตภัณฑ์สินเชื่อที่เข้าเกณฑ์เนื่องจากรายได้ต่ำกว่าเกณฑ์ขั้นต่ำของสถาบันการเงิน "
                    "ขอแนะนำให้พิจารณาสินเชื่อ Micro Finance / Nano Finance หรือโครงการสินเชื่อสร้างโอกาสรายย่อยจากสถาบันการเงินเฉพาะกิจของรัฐเพื่อเสริมสภาพคล่องเบื้องต้น"
                ),
                "required_documents": [
                    "สำเนาบัตรประจำตัวประชาชน",
                    "ทะเบียนบ้าน",
                    "สมุดบัญชีเงินฝากหรือหลักฐานการค้าขายหน้าร้าน"
                ],
                "flex_carousel_ready": False,
                "extra_rules": {}
            }
            synthesized_results = [advisory_item]
            trace["stage5_result_count"] = 0
            trace["stage5_status"] = "REJECTED_BELOW_MINIMUM"
            if return_trace:
                return {"results": synthesized_results, "agentic_trace": trace}
            return synthesized_results

        # -------------------------------------------------------------
        # STAGE 5: Synthesis & Checklist Generation
        # -------------------------------------------------------------
        print(f"\n🎯 [STAGE 5: SYNTHESIS & CHECKLIST GENERATION] Processing live recommendations via Ollama ({settings.OLLAMA_WORKER_MODEL})...", flush=True)
        synthesized_results = await self.stage5_synthesize_recommendations(
            candidates=final_candidates,
            deficit=deficit,
            ratios=ratios,
            profile=profile,
            use_llm_rationale=use_llm_rationale
        )
        trace["stage5_result_count"] = len(synthesized_results)

        print(f"\n📋 [FINAL RESULTS] Loan matching completed ({len(synthesized_results)} products):", flush=True)
        for idx, res in enumerate(synthesized_results, 1):
            print(f"   [{idx}] {res['product_name']} [{res['bank']}]", flush=True)
            print(f"       - ประเภท: {res['type']} | วงเงินสูงสุด: {res['max_limit']:,.0f} THB | โอกาสผ่าน: {res['approval_probability']}%", flush=True)
            print(f"       - คำแนะนำสดจาก LLM: \"{res['recommendation_rationale']}\"", flush=True)

        if return_trace:
            return {"results": synthesized_results, "agentic_trace": trace}
        return synthesized_results

