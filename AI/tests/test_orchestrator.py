import pytest
import asyncio
from app.core.orchestrator import MasterOrchestrator, clean_json_markdown
from app.core.telemetry import TelemetryEmitter
from app.schemas.events import ActiveNode, NodeStatus

def test_clean_json_markdown_parser():
    raw_response = "```json\n{\"action\": \"call_cashflow\", \"amount\": 95000.0}\n```"
    cleaned = clean_json_markdown(raw_response)
    assert cleaned == '{"action": "call_cashflow", "amount": 95000.0}'

    # Also test without codeblock
    plain = '{"action": "done"}'
    assert clean_json_markdown(plain) == '{"action": "done"}'

@pytest.mark.asyncio
async def test_orchestrator_mock_execution():
    orchestrator = MasterOrchestrator(mock_mode=True)
    res = await orchestrator.process_session(
        session_id="sme_001",
        inputs=[{"type": "text", "content": "อันนี้บิลซ่อม 95,000 บาท ช่วยตรวจดูสภาพคล่องหน่อย"}]
    )
    assert res["status"] == "COMPLETED"
    assert "reply_text" in res
    assert "cashflow" in res
    assert res["cashflow"]["projected_cash"] == 35000.0
    assert res["cashflow"]["is_liquidity_crisis"] is True

@pytest.mark.asyncio
async def test_orchestrator_emits_telemetry_lifecycle():
    emitter = TelemetryEmitter()
    orchestrator = MasterOrchestrator(mock_mode=True, telemetry_emitter=emitter)
    q = emitter.subscribe("user_stream_test")

    res = await orchestrator.process_session(
        session_id="user_stream_test",
        inputs=[{"type": "text", "content": "ขอเช็คยอดหนี้และการเงิน"}]
    )
    assert res["status"] == "COMPLETED"

    events = []
    while not q.empty():
        events.append(await q.get())

    event_names = [e.event for e in events]
    assert "ORCHESTRATOR_START" in event_names
    assert "TOOL_COMPLETED" in event_names
    assert "COMPLETED" in event_names

    # Check that live metrics were attached to cashflow event
    cash_evts = [e for e in events if e.active_node == ActiveNode.CASHFLOW_WORKER]
    assert len(cash_evts) > 0
    assert cash_evts[0].live_metrics.current_cash is not None

@pytest.mark.asyncio
async def test_orchestrator_income_inflow():
    orchestrator = MasterOrchestrator(mock_mode=True)
    res = await orchestrator.process_session(
        session_id="sme_001",
        inputs=[{"type": "text", "content": "ลูกค้าโอนเงินค่าของเข้ามา 50,000 บาท"}]
    )
    assert res["status"] == "COMPLETED"
    assert res["flow_type"] == "INFLOW"
    assert res["income"] == 50000.0
    assert res["expense"] == 0.0
    assert res["cashflow"]["projected_cash"] == 180000.0
    assert res["cashflow"]["is_liquidity_crisis"] is False
    assert len(res["loans"]) == 0  # Income does not trigger loan emergency

def test_classify_document_flow_logic():
    orchestrator = MasterOrchestrator(mock_mode=True)
    biz = "บจก. สมชาย ซุปเปอร์มาร์ท"

    # 1. Payment slip where receiver is the business -> INFLOW
    slip_in = orchestrator.classify_document_flow(
        doc_type="payment_slip",
        struct={"receiver_name": "สมชาย ซุปเปอร์มาร์ท", "sender_name": "นายกานต์", "amount": 2500.0},
        business_name=biz
    )
    assert slip_in["flow_type"] == "INFLOW"
    assert slip_in["income"] == 2500.0
    assert slip_in["expense"] == 0.0

    # 2. Payment slip where business pays someone -> OUTFLOW
    slip_out = orchestrator.classify_document_flow(
        doc_type="payment_slip",
        struct={"receiver_name": "การไฟฟ้านครหลวง", "sender_name": "บจก. สมชาย ซุปเปอร์มาร์ท", "amount": 8000.0},
        business_name=biz
    )
    assert slip_out["flow_type"] == "OUTFLOW"
    assert slip_out["expense"] == 8000.0
    assert slip_out["income"] == 0.0

    # 3. Invoice where business is the seller -> INFLOW (Sales invoice)
    inv_in = orchestrator.classify_document_flow(
        doc_type="invoice_or_bill",
        struct={"seller": {"name": "สมชาย ซุปเปอร์มาร์ท"}, "buyer": {"name": "ลูกค้ารายย่อย"}, "grand_total": 12000.0},
        business_name=biz
    )
    assert inv_in["flow_type"] == "INFLOW"
    assert inv_in["income"] == 12000.0

    # 4. Invoice where business is the buyer -> OUTFLOW (Expense/Bill)
    inv_out = orchestrator.classify_document_flow(
        doc_type="invoice_or_bill",
        struct={"seller": {"name": "โรงงานน้ำแข็งไทย"}, "buyer": {"name": "บจก. สมชาย"}, "grand_total": 4500.0},
        business_name=biz
    )
    assert inv_out["flow_type"] == "OUTFLOW"
    assert inv_out["expense"] == 4500.0

    # 5. Bank Statement
    stmt = orchestrator.classify_document_flow(
        doc_type="bank_statement",
        struct={
            "account": {"balance_forward": 100000.0, "closing_balance": 115000.0},
            "transactions": [
                {"deposit": 30000.0, "withdrawal": 0.0},
                {"deposit": 0.0, "withdrawal": 15000.0}
            ]
        },
        business_name=biz
    )
    assert stmt["flow_type"] == "STATEMENT"
    assert stmt["income"] == 30000.0
    assert stmt["expense"] == 15000.0
    assert stmt["closing_balance"] == 115000.0
