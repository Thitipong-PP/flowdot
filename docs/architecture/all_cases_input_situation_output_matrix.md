# 📑 แผนผังทุกกรณีการใช้งาน (Input ➔ Situation ➔ Pipeline ➔ Telemetry SSE ➔ Web / Chat Output)

เอกสารนี้รวบรวม **ทุกกรณีที่เป็นไปได้ (All 13 Production Scenarios)** ของระบบ **SME Finance Copilot** เพื่อให้ทีม Frontend, Backend และผู้ดูแลระบบใช้เป็นพิมพ์เขียว (Blueprint) มาตรฐานเดียวกัน

---

## 🗺️ ภาพรวมของช่องทางการสื่อสาร (Dual Output Channels)

เมื่อระบบประมวลผล จะส่งข้อมูลออก **2 ช่องทางคู่ขนานเสมอ**:
1. **Chat UI / LINE Client (ผู้ใช้)**: รับคำตอบเป็นข้อความ Markdown, LINE Flex Bubble Cards หรือ Carousels
2. **Web Dashboard / Telemetry Monitor (หน้าเว็บ/แดชบอร์ดผู้บริหาร)**: รับ **Server-Sent Events (SSE)** สดที่ `/api/v1/telemetry/stream?session_id=...` เพื่อแสดง:
   - `active_node`: โหนดที่กำลังทำงาน (`INGRESS`, `ORCHESTRATOR`, `VISION_WORKER`, `SANITY_GUARD`, `CASHFLOW_WORKER`, `LOAN_WORKER`, `RESPONSE_COMPILER`)
   - `node_status`: สถานะ (`PROCESSING`, `SUCCESS`, `WARNING`, `ERROR`)
   - `thought_log`: บันทึกความคิดของ AI
   - `live_metrics`: ตัวเลขเงินสดสด (`current_cash`, `projected_cash`, `runway_days`, `risk_level`, `latency_ms`)
   - `payload`: วัตถุข้อมูลดิบสำหรับ Inspect

---

## 🗂️ สารบัญ 13 กรณีการทำงาน (13 Production Scenarios)

1. [กรณีที่ 1: เมนูลัดตรงจาก Rich Menu (Fast-Path Tier 1 Exact Key)](#กรณีที่-1-เมนูลัดตรงจาก-rich-menu-fast-path-tier-1-exact-key)
2. [กรณีที่ 2: ภาษาธรรมชาติที่เป็นเจตนาทั่วไป (Fast-Path Tier 2 Semantic Shortcut)](#กรณีที่-2-ภาษาธรรมชาติที่เป็นเจตนาทั่วไป-fast-path-tier-2-semantic-shortcut)
3. [กรณีที่ 3: อัปโหลดบิล/ใบเสร็จค่าใช้จ่ายปกติ (สภาพคล่องปลอดภัย)](#กรณีที่-3-อัปโหลดบิลใบเสร็จค่าใช้จ่ายปกติ-สภาพคล่องปลอดภัย)
4. [กรณีที่ 4: อัปโหลดบิลแล้วพบวิกฤตสภาพคล่อง (เงินขาดดุล ➔ เรียก Loan RAG อัตโนมัติ)](#กรณีที่-4-อัปโหลดบิลแล้วพบวิกฤตสภาพคล่อง-เงินขาดดุล--เรียก-loan-rag-อัตโนมัติ)
5. [กรณีที่ 5: บิลค่าใช้จ่ายมีตัวเลขผิดพลาด / ภาษีไม่ลงตัว (Sanity Guard Math Mismatch)](#กรณีที่-5-บิลค่าใช้จ่ายมีตัวเลขผิดพลาด--ภาษีไม่ลงตัว-sanity-guard-math-mismatch)
6. [กรณีที่ 6.1: ตรวจพบเอกสารซ้ำแบบเด็ดขาด (Tier 1 Hard Duplicate: เลขที่บิล/สลิปซ้ำ)](#กรณีที่-61-ตรวจพบเอกสารซ้ำแบบเด็ดขาด-tier-1-hard-duplicate-เลขที่บิลสลิปซ้ำ)
7. [กรณีที่ 6.2: ตรวจพบสลิปจับคู่กับใบแจ้งหนี้ที่รออยู่ (Tier 2 Cross-Check Reconciliation)](#กรณีที่-62-ตรวจพบสลิปจับคู่กับใบแจ้งหนี้ที่รออยู่-tier-2-cross-check-reconciliation)
8. [กรณีที่ 6.3: ตรวจพบการจ่ายเงินซ้ำซ้อนภายใน 48 ชม. (Tier 3 Soft Duplicate Warning)](#กรณีที่-63-ตรวจพบการจ่ายเงินซ้ำซ้อนภายใน-48-ชม-tier-3-soft-duplicate-warning)
9. [กรณีที่ 7: อัปโหลดรายการเดินบัญชี (Bank Statement Extraction & Health Update)](#กรณีที่-7-อัปโหลดรายการเดินบัญชี-bank-statement-extraction--health-update)
10. [กรณีที่ 8: ปรึกษาสินเชื่อและขอวงเงินกู้โดยตรง (5-Stage Financial Agentic RAG)](#กรณีที่-8-ปรึกษาสินเชื่อและขอวงเงินกู้โดยตรง-5-stage-financial-agentic-rag)
11. [กรณีที่ 9: ธุรกิจตกเกณฑ์สินเชื่อทั้งหมด (Underwriting Reject + Actionable Diagnostics)](#กรณีที่-9-ธุรกิจตกเกณฑ์สินเชื่อทั้งหมด-underwriting-reject--actionable-diagnostics)
12. [กรณีที่ 10: ไม่มีหลักประกัน แต่กู้คืนได้ด้วย CRAG Recovery (บสย. / Clean Loan)](#กรณีที่-10-ไม่มีหลักประกัน-แต่กู้คืนได้ด้วย-crag-recovery-บสย--clean-loan)
13. [กรณีที่ 11: ธุรกิจกำไรสูง Burn Rate เป็นศูนย์หรือติดลบ (Zero-Division Safe Guard)](#กรณีที่-11-ธุรกิจกำไรสูง-burn-rate-เป็นศูนย์หรือติดลบ-zero-division-safe-guard)
14. [กรณีที่ 12: การกดปุ่มบนการ์ด LINE Flex (Human-in-the-Loop Postback Webhook)](#กรณีที่-12-การกดปุ่มบนการ์ด-line-flex-human-in-the-loop-postback-webhook)
15. [กรณีที่ 13: ผู้ใช้ส่งรูปและข้อความรัวๆ ติดกัน (Ingress Debounce Buffer Window)](#กรณีที่-13-ผู้ใช้ส่งรูปและข้อความรัวๆ-ติดกัน-ingress-debounce-buffer-window)

---

### กรณีที่ 1: เมนูลัดตรงจาก Rich Menu (Fast-Path Tier 1 Exact Key)

* **Input**:
  ```json
  POST /api/v1/ingress
  {"user_id": "sme_001", "type": "text", "content": "menu_login"}
  ```
* **Situation**: ผู้ใช้กดปุ่ม Rich Menu บน LINE OA หรือพิมพ์คีย์เวิร์ดระบบตรงตัว
* **Pipeline Flow**: `Ingress` ➔ `Step 1 Deterministic Rule Engine` (ตรวจพบใน < 2ms) ➔ ตัดจบ ไม่เรียก LLM
* **SSE Telemetry Output (ส่งหน้าเว็บ)**:
  ```json
  event: FAST_PATH_BYPASS
  active_node: "INGRESS"
  node_status: "SUCCESS"
  thought_log: "ตรวจพบคีย์ลัด 'menu_login' ตอบกลับทันที < 2ms โดยไม่ผ่าน LLM"
  live_metrics: {"latency_ms": 1.15}
  ```
* **Chat UI / LINE Client Output (ตอบกลับผู้ใช้)**:
  ```json
  HTTP 200 OK
  {
    "bypass_llm": true,
    "matched_by": "step1_exact_key",
    "title": "เข้าสู่ระบบ SME Web Portal",
    "action": "open_url",
    "login_url": "https://app.sme-copilot.com/login",
    "latency_ms": 1.15
  }
  ```

---

### กรณีที่ 2: ภาษาธรรมชาติที่เป็นเจตนาทั่วไป (Fast-Path Tier 2 Semantic Shortcut)

* **Input**:
  ```json
  POST /api/v1/ingress
  {"user_id": "sme_001", "type": "text", "content": "ขอเบอร์โทรคอลเซ็นเตอร์หน่อย มีเรื่องอยากคุยกับเจ้าหน้าที่"}
  ```
* **Situation**: ผู้ใช้พิมพ์ภาษาพูดทั่วไป ไม่มีคีย์เวิร์ดทางการเงิน (สลิป, กู้, ภาษี, ยอดเงิน)
* **Pipeline Flow**: `Ingress` ➔ `Step 1 Anchor Check` ➔ ดักจับคำว่า "ขอเบอร์โทร/คอลเซ็นเตอร์" ได้ทันที หรือส่งต่อ `Step 2 Satellite Worker` ได้ Confidence >= 0.7 ➔ ตัดจบ LLM
* **SSE Telemetry Output**:
  ```json
  event: FAST_PATH_BYPASS
  active_node: "INGRESS"
  node_status: "SUCCESS"
  thought_log: "ตรวจพบเจตนา 'menu_contact' ตัดจบ LLM ดึงเข้า Fast-Path ทันที"
  live_metrics: {"latency_ms": 1.45}
  ```
* **Chat UI / LINE Client Output**:
  ```json
  HTTP 200 OK
  {
    "bypass_llm": true,
    "matched_by": "step1_anchor_keyword",
    "title": "ติดต่อเจ้าหน้าที่ฝ่ายบริการ",
    "action": "contact_support",
    "phone": "02-123-4567",
    "line_oa": "@sme-finance-copilot"
  }
  ```

---

### กรณีที่ 3: อัปโหลดบิล/ใบเสร็จค่าใช้จ่ายปกติ (สภาพคล่องปลอดภัย)

* **Input**:
  - ข้อความ: `"บิลค่าอุปกรณ์สำนักงาน 12,000 บาท"` หรือส่งรูปภาพใบเสร็จ
* **Situation**:
  - เงินสดสำรองปัจจุบัน: `120,000 บาท`
  - ค่าใช้จ่ายใหม่: `12,000 บาท`
  - เงินสดคงเหลือหลังจ่าย: `108,000 บาท`
  - หนี้สินสิ้นเดือน: `70,000 บาท` ➔ **เงินเหลือ 38,000 บาท (สภาพคล่องปลอดภัย ไม่ขาดดุล)**
* **Pipeline Flow**: `Ingress` ➔ `Vision Worker (OCR)` ➔ `Sanity Guard` ➔ `Cashflow Worker` ➔ `Response Compiler`
* **SSE Telemetry Output (ส่งเข้าหน้าเว็บแดชบอร์ดตามลำดับ)**:
  1. `active_node`: `INGRESS` | `node_status`: `SUCCESS` | `thought_log`: `"รับข้อความเข้าสู่คิว Debounce"`
  2. `active_node`: `SANITY_GUARD` | `node_status`: `SUCCESS` | `thought_log`: `"ตรวจสอบสมการบัญชี: 120,000 - 12,000 = 108,000 บาท ถูกต้อง"`
  3. `active_node`: `CASHFLOW_WORKER` | `node_status`: `SUCCESS` | `live_metrics`: `{"current_cash": 120000, "projected_cash": 108000, "runway_days": 36.0, "risk_level": "HEALTHY"}`
  4. `active_node`: `RESPONSE_COMPILER` | `node_status`: `SUCCESS`
* **Chat UI / LINE Client Output (ส่งให้ผู้ใช้)**:
  * **ข้อความ**:
    > "ตรวจสอบรายการค่าใช้จ่าย 12,000.00 บาท เรียบร้อยแล้วค่ะ  
    > - เงินคงเหลือก่อนจ่าย: 120,000.00 บาท  
    > - เงินคงเหลือหลังจ่าย: 108,000.00 บาท  
    > - หนี้สินสิ้นเดือน: 70,000.00 บาท  
    > ✅ สภาพคล่องอยู่ในเกณฑ์ปลอดภัย รองรับการชำระหนี้สิ้นเดือนได้เพียงพอค่ะ"
  * **LINE Flex Card**: แสดงการ์ด `build_receipt_card` ยืนยันยอดเงิน 12,000 บาท พร้อมปุ่ม `[ยืนยันบันทึก]` และ `[แก้ไขข้อมูล]`

---

### กรณีที่ 4: อัปโหลดบิลแล้วพบวิกฤตสภาพคล่อง (เงินขาดดุล ➔ เรียก Loan RAG อัตโนมัติ)

* **Input**:
  - ส่งรูปภาพบิลค่าซ่อมรถ หรือพิมพ์: `"บิลค่าซ่อมเครื่องยนต์ 95,000 บาท"`
* **Situation**:
  - เงินสดสำรอง: `120,000 บาท`
  - จ่ายค่าซ่อม: `95,000 บาท` ➔ เงินสดเหลือเพียง `25,000 บาท`
  - หนี้สิ้นเดือนที่ต้องจ่าย: `70,000 บาท`
  - **เกิดภาวะขาดสภาพคล่อง (Liquidity Crisis): ขาดดุล 45,000 บาท! ประคองตัวได้เพียง 8.3 วัน**
* **Pipeline Flow**: `Ingress` ➔ `Vision Worker` ➔ `Sanity Guard` ➔ `Cashflow Worker (พบ Deficit)` ➔ **Trigger `Loan Worker (5-Stage RAG)`** ➔ `Response Compiler`
* **SSE Telemetry Output**:
  1. `active_node`: `CASHFLOW_WORKER` | `node_status`: `WARNING` | `thought_log`: `"วิกฤตสภาพคล่อง! ขาดดุล 45,000 THB เมื่อเทียบกับหนี้สิ้นเดือน"` | `live_metrics`: `{"projected_cash": 25000, "runway_days": 8.3, "risk_level": "CRITICAL"}`
  2. `active_node`: `LOAN_WORKER` | `node_status`: `PROCESSING` | `thought_log`: `"ค้นหา In-Memory RRF + CRAG พบสินเชื่อ SME วงเงินรองรับยอดขาดดุล..."`
  3. `active_node`: `RESPONSE_COMPILER` | `node_status`: `SUCCESS`
* **Chat UI / LINE Client Output**:
  * **ข้อความตอบกลับ**:
    > "⚠️ **แจ้งเตือนความเสี่ยงสภาพคล่อง!**  
    > หลังชำระบิล 95,000.00 บาท เงินสดจะเหลือเพียง 25,000.00 บาท ซึ่งไม่พอชำระหนี้สิ้นเดือน 70,000.00 บาท (**ขาดดุล 45,000.00 บาท**)  
    > ระยะเวลาประคองตัวเหลือเพียง 8.3 วัน ระบบได้คัดเลือกสินเชื่อดอกเบี้ยต่ำที่เข้าเกณฑ์มาให้พิจารณาดังนี้ค่ะ"
  * **LINE Flex UI**:
    1. การ์ดสีแดง `build_liquidity_alert_card` แจ้งเตือนยอดขาดดุล 45,000 บาท
    2. Carousel `build_loan_carousel` แนะนำสินเชื่อ SME 2 รายการ พร้อมปุ่ม `[สนใจสมัครสินเชื่อนี้]`

---

### กรณีที่ 5: บิลค่าใช้จ่ายมีตัวเลขผิดพลาด / ภาษีไม่ลงตัว (Sanity Guard Math Mismatch)

* **Input**: รูปถ่ายใบกำกับภาษี หรือ JSON ที่สกัดมาได้ระบุ `Subtotal: 80,000`, `VAT: 5,600`, แต่ `Grand Total: 95,000` (ตัวเลขไม่ลงตัว เกินมา 9,400 บาท)
* **Situation**: ตัวเลขบนเอกสารขัดแย้งกับสมการบัญชีตามกฎหมาย
* **Pipeline Flow**: `Vision Worker` ➔ `Sanity Guard (ตรวจพบ Mismatch)` ➔ สกัดกั้นไม่ให้เข้า Cashflow ➔ ส่งสัญญาณเตือน
* **SSE Telemetry Output**:
  ```json
  event: GUARD_VIOLATION
  active_node: "SANITY_GUARD"
  node_status: "ERROR"
  active_wire: "GUARD_TO_ORCHESTRATOR_RETRY"
  thought_log: "Invariant check failed: ยอดรวม 95,000.00 ไม่ตรงกับ Subtotal(80,000) + VAT(5,600) = 85,600.00"
  ```
* **Chat UI / LINE Client Output**:
  * ข้อความแจ้งเตือน:
    > "⚠️ **พบข้อผิดพลาดของตัวเลขบนเอกสาร!**  
    > ระบบตรวจสอบพบว่า ยอดรวมสุทธิ (95,000 บาท) ไม่สอดคล้องกับยอดก่อนภาษีและ VAT (85,600 บาท)  
    > โปรดตรวจสอบความถูกต้องของเอกสาร หรือกดปุ่มแก้ไขตัวเลขด้านล่างค่ะ"
  * การ์ด LINE Flex ขึ้นแท็กสีส้ม `needs_human_review: true` พร้อมปุ่ม `[แก้ไขข้อมูล]`

---

### กรณีที่ 6.1: ตรวจพบเอกสารซ้ำแบบเด็ดขาด (Tier 1 Hard Duplicate: เลขที่บิล/สลิปซ้ำ)

* **Input**: ส่งรูปสลิปที่มี `reference_no: "KBNK-20261017-98765432"` ซ้ำกับที่เคยบันทึกในฐานข้อมูลแล้ว
* **Situation**: มีรายการสำเร็จบันทึกอยู่ใน MongoDB แล้ว
* **Pipeline Flow**: `Vision Worker` ➔ `Tier 1 Duplicate Engine` ➔ เจอตอ ปฏิเสธทันทีในระดับ Sub-millisecond
* **SSE Telemetry Output**:
  ```json
  event: DUPLICATE_REJECTED
  active_node: "VISION_WORKER"
  node_status: "WARNING"
  thought_log: "Tier 1 Hard Duplicate Detected: Slip ref KBNK-20261017-98765432 ถูกบันทึกไปแล้ว ปฏิเสธการบันทึกซ้ำ"
  ```
* **Chat UI / LINE Client Output**:
  > "❌ **สลิปนี้ถูกบันทึกในระบบไปแล้ว!**  
  > สลิปเลขอ้างอิง `KBNK-20261017-98765432` ยอดเงิน 50,000.00 บาท ได้รับการบันทึกบัญชีเรียบร้อยแล้วเมื่อวานนี้ ระบบจะไม่บันทึกซ้ำซ้อนค่ะ"

---

### กรณีที่ 6.2: ตรวจพบสลิปจับคู่กับใบแจ้งหนี้ที่รออยู่ (Tier 2 Cross-Check Reconciliation)

* **Input**: ส่งสลิปโอนเงิน 95,000 บาท เข้ามาในระบบ
* **Situation**: มีใบแจ้งหนี้ `INV-2026-0089` ยอด 95,000 บาท สถานะ `PENDING_CONFIRMATION` อยู่ในระบบ
* **Pipeline Flow**: `Vision Worker` ➔ `Tier 2 Reconciliation` ➔ Match คู่สำเร็จ ➔ อัปเดตสถานะใบแจ้งหนี้เป็น `RECONCILED`
* **SSE Telemetry Output**:
  ```json
  event: RECONCILIATION_SUCCESS
  active_node: "VISION_WORKER"
  node_status: "SUCCESS"
  thought_log: "จับคู่สำเร็จ! สลิป 95,000 บาทตรงกับใบแจ้งหนี้ INV-2026-0089 ทำการ Reconcile บัญชีอัตโนมัติ"
  ```
* **Chat UI / LINE Client Output**:
  > "🎉 **จับคู่เอกสารสำเร็จ (Reconciled)!**  
  > สลิปโอนเงิน 95,000 บาทตรงกับใบแจ้งหนี้ **INV-2026-0089** (บจก. กรุงเทพ ดีเซล)  
  > ระบบได้ทำการเคลียร์หนี้ค้างจ่ายรายการนี้ให้เรียบร้อยแล้วค่ะ"

---

### กรณีที่ 6.3: ตรวจพบการจ่ายเงินซ้ำซ้อนภายใน 48 ชม. (Tier 3 Soft Duplicate Warning)

* **Input**: บันทึกรายการโอนเงิน 3,500 บาท ให้ "ร้านอาหาร ครัวสมบูรณ์"
* **Situation**: ในช่วง 2 ชั่วโมงที่ผ่านมา เพิ่งมีการโอนยอด 3,500 บาท ให้ปลายทางเดียวกันไปแล้ว
* **Pipeline Flow**: `Vision Worker` ➔ `Tier 3 Soft Duplicate Check` ➔ แจ้งเตือนความเสี่ยงการจ่ายซ้ำ
* **SSE Telemetry Output**:
  ```json
  event: SOFT_DUPLICATE_FLAGGED
  active_node: "VISION_WORKER"
  node_status: "WARNING"
  thought_log: "แจ้งเตือน Soft Duplicate: พบรายการโอน 3,500 บาทให้ผู้รับเดียวกันภายใน 48 ชม."
  ```
* **Chat UI / LINE Client Output**:
  > "⚠️ **แจ้งเตือนความเสี่ยงการจ่ายเงินซ้ำ (Soft Duplicate)**  
  > พบว่าคุณเพิ่งโอนเงินจำนวน **3,500.00 บาท** ให้กับ 'ร้านอาหาร ครัวสมบูรณ์' ไปเมื่อ 2.0 ชั่วโมงที่แล้ว  
  > รายการนี้เป็นการโอนซ้ำหรือไม่? หากตั้งใจจ่าย ให้กดปุ่ม `[ยืนยันบันทึก]` ด้านล่างค่ะ"

---

### กรณีที่ 7: อัปโหลดรายการเดินบัญชี (Bank Statement Extraction & Health Update)

* **Input**: อัปโหลดไฟล์ภาพ Statement ธนาคาร 1–3 หน้า
* **Situation**: ต้องการซิงค์ฐานะการเงินและหายอดเงินสดจริง
* **Pipeline Flow**: `Vision Worker` ➔ แยกประเภท `BankStatementSchema` ➔ สกัด Transactions Array ➔ คำนวณ Net Cashflow ➔ บันทึก MongoDB
* **SSE Telemetry Output**:
  ```json
  event: STATEMENT_PROCESSED
  active_node: "VISION_WORKER"
  node_status: "SUCCESS"
  thought_log: "ประมวลผล Statement สำเร็จ: บัญชีกสิกรไทย เงินฝากเข้า 450,000 บาท ถอนออก 320,000 บาท ยอดคงเหลือ 130,000 บาท"
  live_metrics: {"current_cash": 130000}
  ```
* **Chat UI / LINE Client Output**:
  > "📊 **สรุปสุขภาพทางการเงินจาก Statement:**  
  > - ธนาคาร: กสิกรไทย (xxx-x-12345-x)  
  > - รายรับรวมเดือนล่าสุด: 450,000.00 บาท  
  > - รายจ่ายรวม: 320,000.00 บาท  
  > - เงินสดสุทธิคงเหลือ: **130,000.00 บาท**  
  > ระบบได้อัปเดตข้อมูลฐานะการเงินของธุรกิจคุณเพื่อใช้ประเมินสินเชื่อเรียบร้อยแล้วค่ะ"

---

### กรณีที่ 8: ปรึกษาสินเชื่อและขอวงเงินกู้โดยตรง (5-Stage Financial Agentic RAG)

* **Input**: `"ร้านขาดสภาพคล่อง 100,000 บาท รายได้เดือนละ 80,000 บาท ดำเนินธุรกิจมา 2 ปี ช่วยแนะนำสินเชื่อหน่อย"`
* **Situation**: ผู้ใช้ต้องการเงินทุนหมุนเวียน ไม่ส่งเอกสาร แต่ระบุตัวเลขครบถ้วน
* **Pipeline Flow**: `Fast-Path (ปล่อยผ่าน)` ➔ `Stage 1 Query Synthesis` ➔ `Stage 2 In-Memory RRF (FAISS + BM25)` ➔ `Stage 3 Underwriting Grader` ➔ `Stage 5 Ollama Rationale`
* **SSE Telemetry Output**:
  1. `active_node`: `LOAN_WORKER` | `node_status`: `PROCESSING` | `thought_log`: `"สังเคราะห์ Semantic Query: 'ผู้ประกอบการ SME ดำเนินธุรกิจมาแล้ว 2.0 ปี รายได้ 80,000 บาท ขาดสภาพคล่อง 100,000 บาท DSCR 1.30 เท่า'"`
  2. `active_node`: `LOAN_WORKER` | `node_status`: `SUCCESS` | `thought_log`: `"ดึง Raw Candidates 5 รายการ ผ่านเกณฑ์ทันที 2 รายการ"` | `live_metrics`: {"latency_ms": 18.2}
* **Chat UI / LINE Client Output**:
  * ข้อความสรุปวิเคราะห์:
    > "จากการประเมินคุณสมบัติเบื้องต้น (อายุธุรกิจ 2 ปี, รายได้ 80,000 บ./ด., DSCR 1.30 เท่า) คุณมีคุณสมบัติผ่านเกณฑ์สินเชื่อ 2 ผลิตภัณฑ์ค่ะ"
  * **LINE Flex Carousel**: แสดงการ์ดผลิตภัณฑ์สินเชื่อจากธนาคาร พร้อมอัตราดอกเบี้ยและปุ่ม `[สนใจสมัครสินเชื่อนี้]`

---

### กรณีที่ 9: ธุรกิจตกเกณฑ์สินเชื่อทั้งหมด (Underwriting Reject + Actionable Diagnostics)

* **Input**: ร้านเปิดใหม่ 2 เดือน รายได้ 15,000 บาท ขาดเงิน 50,000 บาท
* **Situation**: เกณฑ์ขั้นต่ำของทุกธนาคารกำหนดอายุธุรกิจอย่างน้อย 6 เดือน - 1 ปี และรายได้ขั้นต่ำ 30,000 บาท (ตกเกณฑ์ 100%)
* **Pipeline Flow**: `Stage 1` ➔ `Stage 2 RRF` ➔ `Stage 3 Deterministic Grader` ➔ **ตกเกณฑ์ทั้งหมด** ➔ `Stage 4 CRAG Check` ➔ ยังคงไม่ผ่าน ➔ ไม่ฝืนแนะนำ แต่สร้างคำแนะนำเชิงวินิจฉัย (Diagnostics)
* **SSE Telemetry Output**:
  ```json
  event: LOAN_REJECT_DIAGNOSTICS
  active_node: "LOAN_WORKER"
  node_status: "WARNING"
  thought_log: "ร้านค้าไม่ผ่านเกณฑ์ขั้นต่ำของทุกธนาคาร: รายได้ < 30,000 บ. และอายุธุรกิจ < 6 เดือน ส่งมอบแนวทางปรับปรุงตัวเลข"
  ```
* **Chat UI / LINE Client Output**:
  > "⚠️ **ยังไม่พบผลิตภัณฑ์สินเชื่อที่ตรงกับคุณสมบัติในขณะนี้**  
  > **เหตุผลที่ไม่ผ่านเกณฑ์การพิจารณาเบื้องต้น:**  
  > 1. *อายุการดำเนินธุรกิจ*: ปัจจุบัน 2 เดือน (เกณฑ์ขั้นต่ำของธนาคารส่วนใหญ่คือ 6 เดือนขึ้นไป)  
  > 2. *รายได้ต่อเดือน*: 15,000 บาท (เกณฑ์ขั้นต่ำเริ่มต้นที่ 30,000 บาท)  
  > 
  > 💡 **แนวทางปรับปรุงเพื่อยื่นกู้ในอนาคต:**  
  > - ดำเนินธุรกิจต่อเนื่องอีก 4 เดือนเพื่อให้ครบเกณฑ์อายุ 6 เดือน  
  > - นำเงินสดเข้าเดินบัญชีธนาคารอย่างสม่ำเสมอเพื่อสร้างประวัติ Statement"

---

### กรณีที่ 10: ไม่มีหลักประกัน แต่กู้คืนได้ด้วย CRAG Recovery (บสย. / Clean Loan)

* **Input**: ธุรกิจเปิดมา 2.5 ปี รายได้ 150,000 บาท แต่ **ไม่มีหลักทรัพย์ค้ำประกัน (has_collateral: False)**
* **Situation**: ใน Stage 2 ดึงสินเชื่อกลุ่มหลักทรัพย์ค้ำประกันมาทั้งหมด ทำให้ Stage 3 สอบตกหมด
* **Pipeline Flow**: Stage 3 ตกเกณฑ์เพราะหลักประกัน ➔ **Trigger Stage 4 CRAG Recovery Loop** ➔ สั่ง Rewrite Query เจาะจง `"Clean Loan บสย. ค้ำประกัน PGS"` ➔ ค้นหาและผ่านเกณฑ์ในรอบที่สองสำเร็จ!
* **SSE Telemetry Output**:
  ```json
  event: CRAG_RECOVERY_TRIGGERED
  active_node: "LOAN_WORKER"
  node_status: "PROCESSING"
  thought_log: "CRAG Self-Correction: ตกเกณฑ์เรื่องหลักทรัพย์ ทำการ Rewrite Query ค้นหากลุ่ม บสย. ค้ำประกัน และ Clean Loan..."
  ```
* **Chat UI / LINE Client Output**:
  > "✅ **ระบบค้นหาสินเชื่อทางเลือกสำเร็จ (ใช้ บสย. ค้ำประกันแทนหลักทรัพย์)**  
  > แม้ธุรกิจของคุณจะไม่มีโฉนดที่ดินหรือหลักทรัพย์ค้ำประกัน แต่ด้วยประวัติรายได้ 150,000 บาท/เดือน คุณสามารถเข้าร่วมโครงการ **บสย. SMEs สร้างไทย (บรรษัทประกันสินเชื่ออุตสาหกรรมขนาดย่อม)** ได้ค่ะ"
  * แสดงการ์ดสินเชื่อ บสย. พร้อม Checklist เอกสารที่ต้องใช้ (เช่น หนังสือยินยอมตรวจเครดิตบูโร, ทะเบียนพาณิชย์)

---

### กรณีที่ 11: ธุรกิจกำไรสูง Burn Rate เป็นศูนย์หรือติดลบ (Zero-Division Safe Guard)

* **Input**: ธุรกิจมีรายได้มากกว่ารายจ่าย กระแสเงินสดสุทธิเป็นบวก (Daily Burn Rate <= 0)
* **Situation**: หากใช้สูตรคณิตศาสตร์ทั่วไป `projected_cash / burn_rate` จะเกิดข้อผิดพลาด `ZeroDivisionError`
* **Pipeline Flow**: `Cashflow Worker` ➔ `Zero-Division Invariant Guard` ➔ คืนค่า `runway_days = 9999.0`
* **SSE Telemetry Output**:
  ```json
  event: ZERO_BURN_GUARD_ACTIVE
  active_node: "CASHFLOW_WORKER"
  node_status: "SUCCESS"
  thought_log: "Zero Division Guard Active: Daily burn rate <= 0 คืนค่า runway_days = 9999.0 สถานะ CASH_POSITIVE"
  live_metrics: {"runway_days": 9999.0, "risk_level": "HEALTHY"}
  ```
* **Chat UI / LINE Client Output**:
  > "🌟 **สภาพคล่องทางการเงินแข็งแกร่งมาก!**  
  > ธุรกิจของคุณมีกระแสเงินสดจากการดำเนินงานเป็นบวก (ไม่มีภาวะ Burn Rate) สามารถดำเนินธุรกิจต่อเนื่องได้อย่างปลอดภัยโดยไม่มีความเสี่ยงด้านสภาพคล่องค่ะ"

---

### กรณีที่ 12: การกดปุ่มบนการ์ด LINE Flex (Human-in-the-Loop Postback Webhook)

* **Input**:
  ```json
  POST /api/v1/postback
  {"data": "action=confirm_receipt&receipt_id=rcpt_100&session_id=sme_001"}
  ```
* **Situation**: ผู้ใช้กดปุ่ม `[ยืนยันบันทึก]` บน LINE Flex Card ในแชต
* **Pipeline Flow**: `Postback Router` ➔ `parse_postback_action` ➔ เปลี่ยนสถานะเอกสารใน MongoDB จาก `PENDING` เป็น `CONFIRMED`
* **SSE Telemetry Output**:
  ```json
  event: RECEIPT_CONFIRMED
  active_node: "ORCHESTRATOR"
  node_status: "SUCCESS"
  thought_log: "ผู้ใช้กดยืนยันบันทึกเอกสาร rcpt_100: บันทึกเข้าสมุดบัญชีถาวรเรียบร้อย"
  ```
* **Chat UI / LINE Client Output**:
  > "✅ **บันทึกรายการสำเร็จ!**  
  > บันทึกใบแจ้งหนี้ลงในสมุดรายจ่ายของธุรกิจเรียบร้อยแล้วค่ะ ข้อมูลถูกซิงค์เข้า Dashboard เรียบร้อย"

---

### กรณีที่ 13: ผู้ใช้ส่งรูปและข้อความรัวๆ ติดกัน (Ingress Debounce Buffer Window)

* **Input**:
  - วินาทีที่ 0.0s: ส่งรูปสลิป
  - วินาทีที่ 0.8s: ส่งรูปบิลค่าซ่อม
  - วินาทีที่ 1.5s: พิมพ์ตามมา `"ช่วยตรวจสองใบนี้ให้หน่อยค่ะ"`
* **Situation**: ป้องกันบอทตอบคำถาม 3 รอบและคิดเงินแยกกัน
* **Pipeline Flow**:
  1. `Event 1 (รูปสลิป)`: เข้า Debounce Buffer ➔ ตั้งเวลานับถอยหลัง 3 วินาที
  2. `Event 2 (รูปบิล)`: เข้ามาใน 0.8s ➔ Reset เวลานับถอยหลังใหม่
  3. `Event 3 (ข้อความ)`: เข้ามาใน 1.5s ➔ Reset เวลานับถอยหลังใหม่
  4. หมดหน้าต่างเวลา (Idle เกิน 3 วิ) ➔ รวมเป็น **1 Single Multi-Modal Batch** ➔ ล็อกด้วย `asyncio.Lock` ประมวลผลรอบเดียว
* **SSE Telemetry Output**:
  ```json
  event: DEBOUNCE_BATCH_FLUSHED
  active_node: "INGRESS"
  node_status: "SUCCESS"
  thought_log: "Debounce Buffer หมดเวลา: รวบรวม 3 เหตุการณ์ (2 รูปภาพ + 1 ข้อความ) ส่งต่อ Orchestrator เป็น Batch เดียว"
  ```
* **Chat UI / LINE Client Output**:
  * บอทตอบคำถาม **เพียงข้อความเดียว** โดยสรุปผลรวมของทั้งสลิปและใบแจ้งหนี้ให้พร้อมกัน ไม่ตอบซ้ำซ้อน 3 ครั้ง

---

## 📊 ตารางสรุปเปรียบเทียบทุกกรณี (Quick Reference Matrix)

| กรณี | Input ตัวอย่าง | สถานะภายใน / Condition | Fast-Path? | Workers ที่ทำงาน | Output ทางแชต (LINE/User) | Output ทางแดชบอร์ด (SSE) |
| :---: | :--- | :--- | :---: | :--- | :--- | :--- |
| **1** | `"menu_login"` | ปุ่มลัด Rich Menu | ✅ (<2ms) | Ingress Rule | URL ล็อกอินทันที | `FAST_PATH_BYPASS` |
| **2** | `"ขอเบอร์โทรคอลเซ็นเตอร์"` | เจตนาทั่วไป ไร้เรื่องเงิน | ✅ (<2ms) | Ingress / Satellite | เบอร์โทรศัพท์ และ LINE OA | `FAST_PATH_BYPASS` |
| **3** | บิล 12,000 บ. | เงินสดพอจ่าย หนี้ไม่กระทบ | ❌ | Vision ➔ Cashflow | รายงานเงินเหลือ + การ์ดยืนยัน | `HEALTHY` (Runway 36 วัน) |
| **4** | บิล 95,000 บ. | เงินขาดดุล 45,000 บ. | ❌ | Cashflow ➔ **Loan RAG** | การ์ดเตือนแดง + Carousel สินเชื่อ | `CRITICAL` (Deficit 45k) |
| **5** | ยอดรวมไม่ตรง VAT | Subtotal + VAT != Total | ❌ | Sanity Guard | เตือนตัวเลขผิด + ปุ่มแก้ไข | `GUARD_VIOLATION` (Error) |
| **6.1**| สลิปเลขเดิมซ้ำ | Ref No อยู่ในฐานข้อมูลแล้ว | ❌ | Tier 1 Duplicate | ปฏิเสธการบันทึกซ้ำ | `DUPLICATE_REJECTED` |
| **6.2**| สลิปตรงกับบิลรอจ่าย | ยอดเงินและคู่ค้าตรงกัน | ❌ | Tier 2 Reconcile | แจ้งจับคู่เคลียร์หนี้สำเร็จ | `RECONCILIATION_SUCCESS` |
| **6.3**| โอนซ้ำใน 48 ชม. | ยอดเดิม ผู้รับเดิม ภายใน 2 ชม. | ❌ | Tier 3 Soft Duplicate | ถามยืนยันเพื่อกันจ่ายซ้ำ | `SOFT_DUPLICATE_FLAGGED` |
| **7** | รูป Statement | รายการเดินบัญชีธนาคาร | ❌ | Vision ➔ DB Sync | สรุปรายรับ-จ่ายประจำเดือน | `STATEMENT_PROCESSED` |
| **8** | ขอกู้ 100,000 บ. | มีเกณฑ์เข้าข่ายกู้ได้ | ❌ | **5-Stage Agentic RAG** | Flex Carousel สินเชื่อตรงเกณฑ์ | `STAGE 2 RRF + STAGE 3 PASS` |
| **9** | ร้านเปิดใหม่ 2 ด. | ตกเกณฑ์ขั้นต่ำทุกธนาคาร | ❌ | Deterministic Grader | เหตุผลปฏิเสธ + แผนฟื้นฟู | `LOAN_REJECT_DIAGNOSTICS` |
| **10**| ขาดหลักประกัน | ตก Stage 3 แต่ฟื้นใน CRAG | ❌ | **CRAG Recovery Loop** | สินเชื่อ บสย. ค้ำประกัน PGS | `CRAG_RECOVERY_TRIGGERED` |
| **11**| ธุรกิจกำไรสูง | Burn Rate <= 0 | ❌ | Zero-Division Guard | ชมสุขภาพการเงินแข็งแกร่ง | `runway_days: 9999.0` |
| **12**| กดปุ่ม Postback | Action จากการ์ดในแชต | ❌ | Postback Handler | ยืนยันบันทึกบัญชีสำเร็จ | `RECEIPT_CONFIRMED` |
| **13**| ส่งภาพ+พิมพ์รัวๆ | เหตุการณ์เข้ามาถี่ < 3 วินาที | ❌ | Debounce Buffer | ตอบสรุปครั้งเดียว ไม่สแปม | `DEBOUNCE_BATCH_FLUSHED` |
