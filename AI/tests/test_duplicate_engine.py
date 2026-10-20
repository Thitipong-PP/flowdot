import pytest
from datetime import datetime, timedelta, timezone
from app.workers.vision_worker import VisionWorker
from app.schemas.financial import PaymentSlipSchema, InvoiceOrBillSchema, SellerBuyerSchema

@pytest.mark.asyncio
async def test_tier1_hard_duplicate_slip_detected():
    worker = VisionWorker(mock_mode=True)
    slip = PaymentSlipSchema(reference_no="SLIP-99999", amount=5000.0)
    
    # Register slip once
    await worker.register_confirmed_document(slip.model_dump())
    
    # Check same slip again
    dup_res = await worker.check_3tier_duplicates(slip.model_dump())
    assert dup_res["is_hard_duplicate"] is True
    assert dup_res["tier"] == 1
    assert "already recorded" in dup_res["reason"]

@pytest.mark.asyncio
async def test_tier1_hard_duplicate_invoice_detected():
    worker = VisionWorker(mock_mode=True)
    invoice = InvoiceOrBillSchema(
        document_no="INV-2026-001",
        seller=SellerBuyerSchema(name="Siam Logistics", tax_id="0105551234567"),
        grand_total=12500.0
    )
    await worker.register_confirmed_document(invoice.model_dump())

    # Check same invoice again
    dup_res = await worker.check_3tier_duplicates(invoice.model_dump())
    assert dup_res["is_hard_duplicate"] is True
    assert dup_res["tier"] == 1
    assert "INV-2026-001" in dup_res["reason"]

@pytest.mark.asyncio
async def test_tier2_cross_check_reconciliation():
    worker = VisionWorker(mock_mode=True)
    # Register pending bill
    bill = InvoiceOrBillSchema(
        document_no="INV-888",
        seller=SellerBuyerSchema(name="Bangkok Diesel Maintenance Ltd.", tax_id="01055001"),
        subtotal=50000.0,
        grand_total=50000.0
    )
    await worker.register_pending_invoice(bill.model_dump())

    # Incoming payment slip matching invoice amount & receiver name
    slip = PaymentSlipSchema(
        reference_no="SLIP-777",
        receiver_name="Bangkok Diesel Maintenance Ltd.",
        amount=50000.0
    )
    dup_res = await worker.check_3tier_duplicates(slip.model_dump())
    assert dup_res["is_reconciled"] is True
    assert dup_res["matched_invoice_no"] == "INV-888"
    assert dup_res["tier"] == 2

@pytest.mark.asyncio
async def test_tier3_soft_duplicate_within_48h():
    worker = VisionWorker(mock_mode=True)
    # Recorded payment 2 hours ago
    past_doc = {
        "doc_type": "payment_slip",
        "reference_no": "SLIP-001",
        "sender_name": "Somchai Supermart",
        "receiver_name": "CP All Supplier",
        "amount": 2500.0,
        "created_at": datetime.now(timezone.utc) - timedelta(hours=2)
    }
    await worker.register_confirmed_document(past_doc)

    # New payment slip with different ref_no but same amount & same receiver within 48h
    new_doc = {
        "doc_type": "payment_slip",
        "reference_no": "SLIP-002",
        "sender_name": "Somchai Supermart",
        "receiver_name": "CP All Supplier",
        "amount": 2500.0,
        "created_at": datetime.now(timezone.utc)
    }
    dup_res = await worker.check_3tier_duplicates(new_doc)
    assert dup_res["is_hard_duplicate"] is False
    assert dup_res["is_soft_duplicate"] is True
    assert dup_res["tier"] == 3
    assert "CP All Supplier" in dup_res["reason"]

@pytest.mark.asyncio
async def test_tier3_outside_48h_not_flagged():
    worker = VisionWorker(mock_mode=True)
    # Recorded payment 3 days ago (> 48h)
    old_doc = {
        "doc_type": "payment_slip",
        "reference_no": "SLIP-OLD",
        "receiver_name": "Office Supplies Co.",
        "amount": 1200.0,
        "created_at": datetime.now(timezone.utc) - timedelta(hours=72)
    }
    await worker.register_confirmed_document(old_doc)

    new_doc = {
        "doc_type": "payment_slip",
        "reference_no": "SLIP-NEW",
        "receiver_name": "Office Supplies Co.",
        "amount": 1200.0,
        "created_at": datetime.now(timezone.utc)
    }
    dup_res = await worker.check_3tier_duplicates(new_doc)
    assert dup_res["is_hard_duplicate"] is False
    assert dup_res["is_soft_duplicate"] is False
    assert dup_res["tier"] == 0

@pytest.mark.asyncio
async def test_document_classification_heuristics():
    worker = VisionWorker(mock_mode=True)
    
    slip_text = "โอนเงินสำเร็จ รหัสอ้างอิง 20261017001 จาก นายสมชาย ไปยัง นายสมศักดิ์ จำนวน 1,500.00 บาท"
    assert worker.classify_document_text(slip_text) == "payment_slip"

    inv_text = "ใบกำกับภาษี/ใบเสร็จรับเงิน TAX INVOICE เล่มที่ 01 เลขที่ INV-2026001 ยอดรวม 94,550 บาท VAT 7%"
    assert worker.classify_document_text(inv_text) == "invoice_or_bill"

    stmt_text = "ธนาคารกสิกรไทย รายการเดินบัญชี ยอดคงเหลือยกมา 120,000.00 ยอดเงินถอน 5,000 ยอดเงินเข้า 10,000"
    assert worker.classify_document_text(stmt_text) == "bank_statement"

    non_fin = "ภาพถ่ายหน้าร้านค้าและป้ายโปรโมชั่นเครื่องดื่มลดราคา 20%"
    assert worker.classify_document_text(non_fin) == "non_financial_image"

@pytest.mark.asyncio
async def test_extract_document_data_schemas():
    worker = VisionWorker(mock_mode=True)
    
    # 1. Slip extraction
    slip_text = "โอนเงินสำเร็จ\nจำนวนเงิน 5,000.00 บาท\nวันที่ทำรายการ 18 ต.ค. 2569\nรหัสอ้างอิง TX12345"
    slip_res = await worker.extract_document_data(slip_text, "payment_slip", use_llm=False)
    assert slip_res.amount == 5000.0
    assert slip_res.reference_no == "TX12345"
    assert slip_res.status_text == "โอนเงินสำเร็จ"

    # 2. Invoice extraction
    inv_text = "บจก. สยาม โลจิสติกส์\nTAX ID: 0105551234567\nเลขที่ INV-2026-999\nวันที่ 18/10/2026\nยอดรวมทั้งสิ้น 12,500.00"
    inv_res = await worker.extract_document_data(inv_text, "invoice_or_bill", use_llm=False)
    assert inv_res.grand_total == 12500.0
    assert inv_res.document_no == "INV-2026-999"
    assert inv_res.seller.tax_id == "0105551234567"

    # 3. Bank Statement extraction
    stmt_text = "ธนาคารไทยพาณิชย์ SCB\nCARD NUMBER 5344 42XX XXXX 4769\nPREVIOUS BALANCE 67,247.23\nNEW BALANCE 75,408.61"
    stmt_res = await worker.extract_document_data(stmt_text, "bank_statement", use_llm=False)
    assert stmt_res.account.bank == "SCB"
    assert stmt_res.account.balance_forward == 67247.23
    assert stmt_res.account.closing_balance == 75408.61
