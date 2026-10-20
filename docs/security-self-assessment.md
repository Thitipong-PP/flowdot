# Security self-assessment report

| รายการ | รายละเอียด |
| --- | --- |
| ระบบ | Flowdot — SME Finance Copilot |
| วันที่ประเมิน | 2026-10-20 |
| ขอบเขต | ตรวจ source code และ configuration ที่มีใน repository สำหรับ Express API, MongoDB, session authentication, permission tiers, request logging และ AI gateway |
| ประเภทเอกสาร | self-assessment เบื้องต้น ไม่ใช่ penetration test, audit อิสระ, certification หรือการรับรองความสอดคล้องตามกฎหมาย |

## Executive summary

ระบบมีพื้นฐานที่ดีสำหรับ development/demo: backend ตรวจ session และ role, จำกัดข้อมูลธุรกรรม/ticket ของ customer ตามเจ้าของ, ใช้ password hashing, signed HttpOnly cookie, input validation, Helmet, CORS allowlist และบันทึก HTTP status รวมถึง `200` ลง JSONL โดยไม่บันทึก body/cookie/auth header ใน request record

ยังไม่ควรนำไปใช้ production กับข้อมูลการเงินจริงโดยไม่มีการแก้ความเสี่ยงระดับสูงสองข้อก่อน:

1. **High — PII masking ไม่ครอบคลุมข้อความอิสระ**: regex อาจพลาดชื่อและข้อมูลระบุตัวตน โดยเฉพาะภาษาไทย/บริบทที่ไม่ได้ตรงรูปแบบ ความเสี่ยงคือข้อมูลจริงถูกส่งให้ LLM provider
2. **High — mutation request ที่ไม่มี `Origin` ผ่าน origin middleware**: ปัจจุบันปฏิเสธเฉพาะ origin ที่มีค่าแต่ไม่อยู่ allowlist คำขอที่ไม่มี header นี้ผ่านได้ ซึ่งลดประสิทธิภาพของ CSRF defense สำหรับ session cookie

ระดับความเสี่ยงในรายงานนี้เป็นการจัดลำดับเบื้องต้นตามผลกระทบและความเป็นไปได้จากการอ่านโค้ด ไม่ใช่ผลจากการโจมตีจริง

## Permission-tier assessment

| Role | สิทธิ์ที่ยืนยันจาก backend | ข้อจำกัด/ข้อสังเกต |
| --- | --- | --- |
| Anonymous | Health check, ดูผลิตภัณฑ์สินเชื่อที่ active, register, login | ไม่มีการอ่านข้อมูลลูกค้าหรือข้อมูลบัญชีโดยไม่ login |
| Customer | session ของตนเอง; อ่าน/แก้ไขโปรไฟล์ตนเอง; ดู dashboard/transactions ของตน; เพิ่มธุรกรรม; สร้างและดู ticket ของตน; ขอ recommendation จากโปรไฟล์ตน; เรียก assistant | ไม่มี transaction administration, อ่าน customer คนอื่น, เปลี่ยน ticket status หรือเปลี่ยน role |
| Admin | ดูรายชื่อลูกค้า, อ่านโปรไฟล์ตาม ID, ดู ticket ทุกคน, เปลี่ยน ticket status | ไม่มี endpoint สำหรับจัดการบัญชี/role, ไม่มี endpoint สำหรับดูธุรกรรมลูกค้าผ่าน API ชุดนี้; โปรไฟล์ตาม ID เปิดเผยข้อมูลมากกว่ารายการลูกค้า |

การบังคับ role อยู่ใน backend middleware `authenticate` และ `requireRole`; การแสดงผลใน UI ไม่ใช่ขอบเขต security เจ้าของข้อมูลใน transaction/ticket/dashboard ใช้ `customerId` จาก session ไม่รับ owner ID จาก client เป็นตัวกำหนด scope

## Controls ที่พบ

- Password hash ใช้ Node.js `scrypt` พร้อม salt แบบสุ่ม และเปรียบเทียบ hash ด้วย `timingSafeEqual`.
- Session เป็น HMAC-signed token; ตรวจบัญชี active, role และ `sessionVersion` กับฐานข้อมูลทุก request ที่ authenticate.
- Cookie ใช้ `HttpOnly` และ `SameSite=Lax`; ตั้ง `Secure` เมื่อ `NODE_ENV=production`.
- ตรวจ `AUTH_SECRET` ว่ามีอย่างน้อย 32 ตัวอักษรก่อนเปิด API.
- API ใช้ Zod validation, ปิด `x-powered-by`, เปิด Helmet และ CORS จำกัด origin ตาม `FRONTEND_ORIGIN`.
- Request logger เก็บ status ทุก response รวม success `200`, request ID และ duration; request record ไม่มี body, query string, cookie หรือ authorization header.
- `.env`, log และ `backend/.data` ถูก exclude จาก Git ตาม `.gitignore`; env examples ใช้ placeholder.
- LLM request ผ่าน gateway กลางและเรียก `maskPii` ก่อนส่ง provider; เมื่อไม่มี endpoint/key ระบบตอบ `503` แทนการสร้างคำตอบจำลอง.

## Findings และแผนจัดการความเสี่ยง

| ID | ระดับ | ความเสี่ยง/หลักฐาน | ผลกระทบ | แนวทางจัดการที่แนะนำ |
| --- | --- | --- | --- | --- |
| SEC-01 | **High** | PII masker ใน `backend/src/services/pii-masker.js` เป็น pattern-based; ชื่อทั่วไป/ภาษาไทย/ข้อมูลอิสระอาจไม่ตรง regex และ gateway ส่งข้อความที่ผ่าน masker ต่อไปยัง provider | PII หรือข้อมูลการเงินอาจออกนอกระบบโดยไม่ตั้งใจ | จำกัดข้อมูลที่ส่ง LLM ด้วย allowlist; แยก structured context จาก free text; ทำ redaction ที่ fail closed เมื่อไม่มั่นใจ; ทดสอบภาษาไทย/รูปแบบหลากหลาย; ไม่ใช้ model กับข้อมูลจริงก่อนผ่าน privacy review และอนุมัติ provider terms |
| SEC-02 | **High** | `requireTrustedOrigin` ปฏิเสธ origin ที่ไม่อยู่ allowlist เฉพาะเมื่อ header มีค่า; mutation ที่ไม่มี `Origin` ผ่านได้ | ลดการป้องกัน CSRF ต่อ endpoint ที่ใช้ cookie session โดยเฉพาะการเปลี่ยนข้อมูล/สิทธิ์ admin | ปฏิเสธ missing Origin สำหรับ browser mutation หรือใช้ CSRF token ที่ตรวจ server-side; กำหนด policy แยกสำหรับ trusted service clients; ทดสอบ browser และ API clients ก่อนเปิดใช้งาน |
| SEC-03 | **Medium** | Auth rate limiter ใช้ `Map` ใน process เดียว และ Express ไม่ได้กำหนด trusted proxy | limit ถูก reset เมื่อ restart/ไม่แชร์ระหว่าง replica; หลัง proxy อาจระบุตัว IP ผิด หรือผู้ใช้หลัง proxy ถูกจัดกลุ่มเดียวกัน | ใช้ Redis/shared rate limit store, กำหนด trust proxy เฉพาะจำนวน/เครือข่าย proxy ที่รู้จัก และทดสอบ spoofed `X-Forwarded-For` |
| SEC-04 | **Medium** | Log เก็บใน local JSONL ไม่มี retention/rotation/central alert; การเขียนไฟล์ทำแบบ asynchronous หลัง response | log อาจโตไม่จำกัด, สูญหายเมื่อ process หยุดฉับพลัน หรือไม่มีสัญญาณเตือนเมื่อ log sink ล้มเหลว | ส่ง structured logs ไป platform กลาง, ตั้ง retention และ access policy, alert เมื่อ 5xx/503 เพิ่มหรือเขียน log ไม่ได้, กำหนด encryption/backup |
| SEC-05 | **Medium** | Log ปัจจุบันเป็น HTTP request completion เป็นหลัก; ไม่มี domain audit สำหรับ profile/transaction/ticket mutations และยังไม่มี AI step events | ตรวจสอบย้อนหลังว่าใครเปลี่ยน resource หรือ AI ทำขั้นตอนไหน/ได้ผลแบบใดได้ไม่ครบ | เพิ่ม audit event ที่ไม่เก็บ payload และ AI event sink ตาม [permission and audit logging](permission-and-audit-logging.md) ก่อนเชื่อม agent ของทีม |
| SEC-06 | **Medium** | Admin อ่าน customer profile เต็มตาม ID; role มีเพียง `customer`/`admin`, ไม่มี permission แยกตามงาน | สิทธิ์ admin กว้างและไม่มี separation of duties; credential admin ถูกใช้เพื่ออ่านข้อมูลส่วนบุคคลจำนวนมาก | ใช้ least privilege/permission scopes, MFA/SSO สำหรับ admin, audit การอ่านข้อมูล, จำกัดข้อมูลที่แสดงตามหน้าที่ |
| SEC-07 | **Medium** | มี demo seed data และ seed script สร้างบัญชี admin/customer จาก env; ไม่พบขั้นตอนบังคับเปลี่ยน credential หรือ disable seed ใน production | อาจเปิด seed/example account หรือข้อมูลตัวอย่างใน environment ผิด | ห้าม seed demo data ใน production; ใช้ secret manager, admin bootstrap แบบ one-time และตรวจไม่ให้ใช้ credential ตัวอย่าง |
| SEC-08 | **Low–Medium** | Error ตอน log เขียนไม่สำเร็จพิมพ์ `error.message` ไป stderr | ข้อความ filesystem/runtime error อาจเปิดเผย path หรือข้อมูลประกอบที่ไม่ควรอยู่ใน log กลาง | ใช้ error code/type แบบ allowlist, sanitize message และอย่าแนบ connection string/secret |
| SEC-09 | **Medium** | ยังไม่พบ endpoint สำหรับ MFA, reset password, email verification หรือการจัดการ session/device | บัญชีที่ยึดได้กู้คืน/ควบคุมได้ยาก และยังไม่มีขั้นตอนพิสูจน์เจ้าของบัญชี | เพิ่ม account recovery/verification และ MFA ตาม threat model ก่อนใช้กับลูกค้าจริง |

## AI provider / team integration checklist

ก่อนต่อ AI orchestration ของทีม:

- กำหนด data-flow diagram และระบุ field ที่อนุญาตให้ส่งออกไป provider อย่างชัดเจน
- ตกลง retention, training usage, region, subprocessors, deletion และ incident terms กับ provider
- ให้ AI adapter ส่ง event ขั้นตอนผ่าน backend event sink โดยผูก `requestId`/`runId` และส่งเฉพาะ status/result summary ที่ sanitize แล้ว
- ไม่เก็บ raw prompt, output, chain-of-thought, PII, secrets หรือ provider error body ใน log
- ตรวจว่า masking สำเร็จก่อนเรียก provider; หาก policy fail หรือ sanitizer ล้มเหลว ต้องไม่ส่ง request ออก
- ตั้ง timeout, retry limit, payload limit และ provider allowlist; ป้องกัน endpoint URL จากการชี้ไป internal network/metadata service
- บันทึก model/provider/version และ outcome แบบไม่ระบุตัวบุคคลเพื่อรองรับ incident triage
- ทดสอบ prompt injection, output validation, provider failure, timeout, retry และข้อมูล PII ภาษาไทย

## สถานะการทดสอบและข้อจำกัด

เอกสารนี้อ้างอิงจากการ review source/configuration; ไม่ได้ทำ penetration test, dependency vulnerability scan, cloud/IAM review, MongoDB backup/restore test หรือ legal/privacy compliance assessment ข้อความว่า “พบ control” ไม่ได้หมายถึง control นั้นผ่านการทดสอบในทุก deployment

รายการ remediation ที่แนะนำให้ทำก่อน production:

1. แก้ SEC-01 และ SEC-02 พร้อม regression tests
2. เปลี่ยน rate limit และทำ trusted proxy policy (SEC-03)
3. ออกแบบ central logging, audit event และ AI step events พร้อม retention/access control (SEC-04/05)
4. เพิ่ม MFA/least privilege/admin audit และกระบวนการ bootstrap credential (SEC-06/07/09)
5. ทำ security test, backup restore test, privacy review และ deployment-specific review ก่อนเปิดให้ผู้ใช้จริง
