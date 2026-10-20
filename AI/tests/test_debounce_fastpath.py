import pytest
import asyncio
import time
from app.core.debouncer import DebounceManager
from app.core.anonymizer import mask_pii
from app.core.fast_path import FastPathRouter

def test_pii_anonymizer():
    raw = "My citizen id is 1-1002-00345-67-8 and bank account is 098-2-34567-1."
    masked = mask_pii(raw)
    assert "1-1002-00345-67-8" not in masked
    assert "098-2-34567-1" not in masked
    assert "[ID_CARD_MASKED]" in masked
    assert "[BANK_ACC_MASKED]" in masked

def test_pii_anonymizer_continuous_digits():
    raw = "บัตรประชาชน 1100200345678 และเลขบัญชี 1234567890 ติดต่อ 0812345678"
    masked = mask_pii(raw)
    assert "1100200345678" not in masked
    assert "[ID_CARD_MASKED]" in masked

def test_fast_path_latency_and_bypass():
    router = FastPathRouter()
    t0 = time.perf_counter()
    res = router.check_static_intent("menu_login")
    latency_ms = (time.perf_counter() - t0) * 1000

    assert res is not None
    assert res["bypass_llm"] is True
    assert "login_url" in res
    assert latency_ms < 200.0  # Constraint: Fast-path execution < 200 ms

def test_fast_path_non_matching_returns_none():
    router = FastPathRouter()
    res = router.check_static_intent("ขอวิเคราะห์งบการเงินหน่อยครับ")
    assert res is None

@pytest.mark.asyncio
async def test_debounce_batches_rapid_events():
    flushed = []

    async def on_flush(user_id, items):
        flushed.append((user_id, items))

    debouncer = DebounceManager(wait_seconds=0.2, on_flush_callback=on_flush)
    await debouncer.add_event("user1", {"type": "image", "id": "img1"})
    await debouncer.add_event("user1", {"type": "text", "content": "hello"})
    await asyncio.sleep(0.35)

    assert len(flushed) == 1
    assert len(flushed[0][1]) == 2
    assert flushed[0][0] == "user1"

@pytest.mark.asyncio
async def test_concurrency_lock_per_user():
    debouncer = DebounceManager(wait_seconds=0.1)
    lock1 = debouncer.get_lock("user1")
    lock2 = debouncer.get_lock("user1")
    lock_other = debouncer.get_lock("user2")

    assert lock1 is lock2
    assert lock1 is not lock_other

@pytest.mark.asyncio
async def test_semantic_fast_path_intercepts_login_intent():
    router = FastPathRouter()
    intercepted, route = await router.evaluate_fast_path("อยากล็อกอินเข้าเว็บ SME Portal ต้องทำยังไงครับ")
    assert intercepted is True
    assert route is not None
    assert route["bypass_llm"] is True
    assert "login_url" in route

@pytest.mark.asyncio
async def test_semantic_fast_path_intercepts_contact_intent():
    router = FastPathRouter()
    intercepted, route = await router.evaluate_fast_path("ขอเบอร์โทรคอลเซ็นเตอร์หน่อย มีเรื่องอยากปรึกษาเจ้าหน้าที่")
    assert intercepted is True
    assert route is not None
    assert route["bypass_llm"] is True
    assert "phone" in route

@pytest.mark.asyncio
async def test_semantic_fast_path_allows_orchestration_for_finance():
    router = FastPathRouter()
    intercepted, route = await router.evaluate_fast_path("ขาดสภาพคล่อง 100,000 บาท ช่วยแนะนำสินเชื่อและคำนวณ DSCR หน่อย")
    assert intercepted is False
    assert route is None

def test_step1_deterministic_rule_sub_2ms_and_no_llm():
    router = FastPathRouter()
    t0 = time.perf_counter()
    res = router.step1_deterministic_rule_based("menu_login")
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert res is not None
    assert res["bypass_llm"] is True
    assert res["matched_by"] == "step1_exact_key"
    assert elapsed_ms < 2.0  # Constraint: Sub-2ms

def test_step1_fast_anchor_keyword_match():
    router = FastPathRouter()
    res = router.step1_deterministic_rule_based("ขอเบอร์โทรคอลเซ็นเตอร์หน่อย")
    assert res is not None
    assert res["bypass_llm"] is True
    assert res["matched_by"] == "step1_anchor_keyword"

def test_step1_ignores_anchors_with_financial_keywords():
    router = FastPathRouter()
    # Contains anchor 'เข้าสู่ระบบ' BUT also financial keyword 'สินเชื่อ'
    res = router.step1_deterministic_rule_based("ขอสินเชื่อเพื่อเข้าสู่ระบบ")
    assert res is None  # Must NOT be intercepted by Step 1 rule


