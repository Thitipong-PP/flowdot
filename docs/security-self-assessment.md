# Security Self-Assessment Report

| รายการ | รายละเอียด |
| --- | --- |
| ระบบ | Flowdot — SME Finance Copilot |
| วันที่ประเมิน | 2026-10-20 |
| ขอบเขต | Source code และ configuration ของ Next.js frontend, Express API, MongoDB, session authentication, permission tiers, request logging และ LLM gateway |
| ประเภทการประเมิน | Self-assessment จากการ review โค้ดและ configuration ไม่ใช่ penetration test, independent audit, certification หรือการรับรองความสอดคล้องตามกฎหมาย |

## 1. Permission-Tier Implementation & Enforcement

### Permission tiers

| Tier / Principal | สิทธิ์ที่ backend อนุญาต | ข้อจำกัด |
| --- | --- | --- |
| Anonymous | Health check, ดูผลิตภัณฑ์สินเชื่อที่เปิดใช้งาน, สมัคร customer account และ login | อ่าน/แก้ไขข้อมูลบัญชีหรือข้อมูลลูกค้าไม่ได้ |
| Customer | อ่าน/แก้ไขโปรไฟล์ตนเอง, ดู dashboard และธุรกรรมของตน, เพิ่มธุรกรรมของตน, สร้าง/ดู ticket ของตน, ขอ financing recommendations จากโปรไฟล์ตน และเรียก assistant | อ่านข้อมูลลูกค้าคนอื่น, ดูธุรกรรมคนอื่น, เปลี่ยน ticket status หรือเปลี่ยน role ไม่ได้ |
| Admin | ดูรายชื่อลูกค้าและโปรไฟล์ตาม ID, ดู ticket ทั้งหมด และเปลี่ยนสถานะ ticket | ไม่มี endpoint จัดการ role/account, ไม่มี endpoint อ่านหรือแก้ transaction ของลูกค้าใน API ชุดปัจจุบัน |
| AI assistant (service integration) | ปัจจุบันรับข้อความจากผู้ใช้ที่ login แล้ว ส่งข้อความผ่าน PII masker ไปยัง LLM provider ที่กำหนดด้วย environment variables และส่งข้อความตอบกลับ | ไม่ใช่ user role และไม่มี tool สำหรับเรียก API, query MongoDB, แก้ข้อมูล, ลบบัญชี, อนุมัติสินเชื่อ หรือยกระดับสิทธิ์; ไม่ได้มีสิทธิ์ `admin` |

การสมัครผ่าน API สร้างได้เฉพาะ `customer`; บัญชี admin ถูก bootstrap จาก `ADMIN_EMAIL`/`ADMIN_PASSWORD` ใน backend ไม่มีหน้าให้ยกระดับ role ด้วยตนเอง รายละเอียด endpoint แสดงใน [Permission tiers and audit logging](permission-and-audit-logging.md)

### Enforcement

สิทธิ์ถูกควบคุมใน backend code ไม่ได้อาศัยคำสั่งใน AI prompt หรือการซ่อนปุ่มใน frontend: `authenticate` ตรวจ session และสถานะบัญชีจาก MongoDB, `requireRole('admin')` ล็อก endpoint ของ admin ที่ route layer และ controller ใช้ `customerId` จาก session เป็นขอบเขต query ของ customer ข้อมูลธุรกรรม/ticket/dashboard ไม่รับ owner ID จาก client เพื่อเลือกเจ้าของข้อมูล

AI assistant ปัจจุบันเป็นการส่งข้อความผ่าน gateway เท่านั้น ไม่มี function/tool calling ที่มีสิทธิ์ทำ action ในระบบ Prompt ที่บอกว่า AI “ห้ามลบข้อมูล” ไม่ใช่ security boundary; หากเพิ่ม tools ในอนาคต แต่ละ tool ต้องมี allowlist และเรียก backend authorization เดียวกับ user/API โดยห้ามนำ admin credential หรือ database credential ไปให้ model

## 2. Known-Risk List & Controls

ระดับความเสี่ยงเป็นการจัดลำดับเบื้องต้นจากผลกระทบและโค้ดที่ตรวจ ไม่ได้ยืนยันด้วยการโจมตีจริง สถานะ `มีบางส่วน` หมายถึงมี control แต่ยังไม่เพียงพอสำหรับ production

| ID | ความเสี่ยง | ระดับ | Control ที่มีอยู่ | ช่องว่าง/การจัดการที่ต้องทำ |
| --- | --- | --- | --- | --- |
| R-01 | PII masking อาจพลาดชื่อ/ข้อมูลระบุตัวบุคคลในข้อความอิสระก่อนส่งให้ LLM โดยเฉพาะข้อความภาษาไทยหรือรูปแบบที่ไม่ตรง regex | **High** | ทุก provider request ผ่าน `llm-gateway.js` ซึ่งเรียก `maskPii` ก่อนส่ง | Masking เป็น pattern-based และไม่ fail closed เมื่อไม่มั่นใจ; จำกัดข้อมูลด้วย allowlist, ทดสอบข้อมูลไทย, ป้องกัน request เมื่อ sanitizer ล้มเหลว และห้ามใช้ข้อมูลจริงกับ provider ก่อนผ่าน privacy review |
| R-02 | Mutation request ที่ไม่มี `Origin` ผ่าน origin middleware ได้ อาจลดการป้องกัน CSRF ของ session cookie | **High** | CORS จำกัด allowlisted origin และ cookie ใช้ `SameSite=Lax`; origin ที่มีค่าแต่ไม่อยู่ allowlist ถูกปฏิเสธ | `requireTrustedOrigin` ตรวจเฉพาะกรณี header มีค่า; ปฏิเสธ missing Origin สำหรับ browser mutation หรือเพิ่ม CSRF token พร้อม policy สำหรับ service clients |
| R-03 | Prompt injection หรือคำแนะนำทางการเงินที่ผิด/ทำให้เข้าใจว่าอนุมัติสินเชื่อแล้ว | **Medium** | ปัจจุบันไม่มี AI tools สำหรับเปลี่ยนแปลงข้อมูล; system instruction ระบุว่าไม่อนุมัติสินเชื่อแทนผู้ให้กู้ | Prompt instruction ไม่ใช่ enforcement และ model อาจให้คำตอบผิด; ต้อง validate output, สื่อสารข้อจำกัด, ทดสอบ adversarial prompts และมี human review สำหรับการตัดสินใจสำคัญ |
| R-04 | ไม่มี AI step audit log จึงติดตามแต่ละขั้น, provider outcome หรือ retry ไม่ได้ | **Medium** | HTTP request logger เก็บ status, request ID และ duration รวม 200/4xx/5xx/503 | ปัจจุบัน log เป็น `http_request` เท่านั้น; เพิ่ม `ai_run_*`/`ai_step_*` ผ่าน event sink ตาม schema ในเอกสาร logging โดยห้าม log prompt/output ดิบ |
| R-05 | Rate limiting ใช้ memory ของ process เดียวและไม่กำหนด trusted proxy | **Medium** | Login/register จำกัดจำนวนครั้งในแต่ละ process | Limit รีเซ็ตเมื่อ restart/ไม่แชร์หลาย instance; เปลี่ยนเป็น shared store และกำหนด trusted proxy ให้ตรง deployment |
| R-06 | Admin อ่านข้อมูลโปรไฟล์ละเอียดและมี role เพียง `customer`/`admin` | **Medium** | Admin route ต้องผ่าน `requireRole`; รายชื่อลูกค้าส่งคืนเฉพาะบาง field | ใช้ least privilege/scoped permission, ลด field ตามหน้าที่, เพิ่ม MFA และ audit การเปิดดูข้อมูลส่วนบุคคล |
| R-07 | Consent และ compliance requirement อาจไม่ครบตามวัตถุประสงค์/วงจรข้อมูล | **High** | Registration ต้องส่ง `financialDataConsent: true` | มี boolean เดียว ไม่มี purpose/version/timestamp/ช่องทางถอน consent ที่แยกกัน และยังไม่ได้ legal/PDPA review; ออกแบบ consent record, privacy notice, retention/deletion และสิทธิของเจ้าของข้อมูลร่วมกับผู้เชี่ยวชาญ |
| R-08 | Log local ไม่มี rotation/retention/central alert; การเขียน log เป็น asynchronous | **Medium** | JSONL แยกวัน เก็บสำเร็จ/error status และเขียน stdout/stderr พร้อมไฟล์ | อาจโตไม่จำกัดหรือสูญหายเมื่อ process หยุด; เพิ่ม centralized log collection, retention, access control, alert และทดสอบ log sink failure |
| R-09 | Seed demo data และ admin bootstrap อาจถูกใช้ผิด environment | **Medium** | ใช้ค่าจาก env และตัวอย่างใน `.env.example` เป็น placeholder; `.env`/runtime logs ถูก ignore จาก Git | ปิด demo seed ใน production, ใช้ secret manager, จำกัด admin bootstrap แบบ one-time และตรวจหาค่า default ก่อน deploy |
| R-10 | ไม่มี MFA, email verification, password reset หรือ account recovery flow | **Medium** | Password hash ใช้ `scrypt` และ session signed cookie รองรับ revoke ด้วย `sessionVersion` | เพิ่ม recovery/verification/MFA และขั้นตอน session/device administration ก่อนเปิดใช้จริง |
| R-11 | Log write failure แสดง `error.message` ไป stderr | **Low–Medium** | request record ไม่เก็บ body, cookie หรือ authorization header | Sanitize/allowlist metadata ที่เขียน log และป้องกัน path/credential จากข้อความ error |
| R-12 | Third-party LLM/data processor อาจมีเงื่อนไขการเก็บ/ใช้ข้อมูลที่ยังไม่ได้อนุมัติ | **High** | LLM endpoint/key/model กำหนดผ่าน environment; ไม่มี config แล้ว API ตอบ 503 | ตรวจ provider terms, data residency, retention, training use, subprocessor และ deletion ก่อนเปิด provider; ใช้เฉพาะข้อมูลที่ได้รับอนุญาต |

## 3. Data Protection & Privacy

ก่อนเรียก LLM, `requestLlmCompletion` ส่ง system/message ผ่าน `maskPii` ซึ่งพยายามแทนอีเมล, หมายเลขโทรศัพท์ไทย, เลขประจำตัว/บัญชีบางรูปแบบ, ที่อยู่บางรูปแบบ และชื่อที่ตรงกับ phrase ที่กำหนดด้วย placeholder จากนั้นจึงสร้าง payload ไปยัง provider โดยตรง อย่างไรก็ตามการตรวจเป็น regex และชื่อ/ข้อมูลในข้อความอิสระอาจหลุดได้ จึงเป็น mitigation เบื้องต้น ไม่ใช่การรับประกันว่า PII ถูกลบทั้งหมด ระบบไม่มี AI step logs สำหรับเก็บ prompt/ผลลัพธ์ และไม่ควรเพิ่มการเก็บเนื้อหาเหล่านั้นลง log

การสมัครบัญชีต้องให้ `financialDataConsent` เป็น `true` แต่ปัจจุบันเป็น consent flag เดียวใน customer profile ไม่ได้แยกวัตถุประสงค์ เช่น การให้บริการ, การแนะนำสินเชื่อ, การส่งข้อมูลให้ LLM, analytics หรือ marketing และยังไม่มี record ของข้อความ/เวอร์ชัน notice, เวลา/ช่องทางยินยอม, การถอนความยินยอม หรือ retention ตามแต่ละ purpose ดังนั้นเอกสารนี้ **ไม่สรุปว่าระบบสอดคล้อง PDPA แล้ว** ต้องกำหนด lawful basis และ consent ที่เหมาะสมแยกตามวัตถุประสงค์พร้อม privacy notice, data minimization, retention/deletion และช่องทางใช้สิทธิ โดยให้ผู้เชี่ยวชาญด้าน privacy/legal ตรวจยืนยันก่อนใช้งานจริง

## Optional sections

### Overview & Threat Model

ระบบประกอบด้วย Next.js frontend, Express API และ MongoDB; API ใช้ signed cookie session และเรียก LLM provider แบบ OpenAI-compatible เมื่อกำหนดค่า Threat actors ที่พิจารณา: ผู้ไม่ login, customer ที่พยายามอ่านข้อมูลคนอื่น, บัญชี admin ที่ถูกยึด, ผู้โจมตีผ่าน browser/CSRF, prompt injection ในข้อความผู้ใช้, การรั่วไหลผ่าน logs และ third-party provider ที่รับข้อความจาก assistant

ขอบเขตความเชื่อถือหลักอยู่ที่ backend authorization, database ownership filters, input validation และ LLM gateway/masking boundary การซ่อน UI หรือ system prompt ไม่ถือเป็นขอบเขตความเชื่อถือ การประเมินนี้ไม่ครอบคลุม infrastructure/cloud IAM, production network, MongoDB deployment, backup system หรือผู้ให้บริการที่ยังไม่ได้เลือก

### Authentication & Secrets Management

- Password ใช้ `scrypt` พร้อม random salt และ constant-time comparison
- Session เป็น HMAC-SHA256 signed token; ตรวจ account active, role และ `sessionVersion` กับ MongoDB ทุก authenticated request
- Cookie ตั้ง `HttpOnly`, `SameSite=Lax`; ตั้ง `Secure` เมื่อ `NODE_ENV=production`
- Backend ปฏิเสธ start เมื่อไม่มี `AUTH_SECRET` หรือสั้นกว่า 32 ตัวอักษร; ค่า admin/demo และ LLM key อ่านจาก environment
- `.env` และ local logs อยู่ใน `.gitignore`; ไม่พบว่าระบบมี secret manager integration ในโค้ดชุดนี้ ต้องใช้ secret manager ของ deployment และห้ามใช้ demo credential ใน production

### Logging & AI Integration

ปัจจุบัน middleware เก็บ JSONL ต่อ HTTP response รวม `200` โดยมี timestamp, level, event, request ID, method, path, status, duration และ actor role เมื่อยืนยันตัวตนแล้ว ไม่เก็บ body, query, cookie หรือ authorization header ใน request record ไฟล์อยู่ที่ `backend/.data/logs/YYYY-MM-DD.jsonl` และไม่มี rotation/retention อัตโนมัติ

ยังไม่มี event log สำหรับแต่ละขั้นของ AI; มีเพียง HTTP status ของ assistant request เอกสาร [Permission tiers and audit logging](permission-and-audit-logging.md) ระบุ event schema ที่ทีม AI ควรส่ง (`ai_run_started/completed/failed`, `ai_step_started/completed/failed`) โดยเก็บเฉพาะสถานะ/summary ที่ sanitize แล้ว ห้ามเก็บ raw prompt, model output, chain-of-thought, PII หรือ secret

### Testing Performed

- ตรวจ route/middleware/controller/configuration แบบ source review เพื่อยืนยัน permission tier และขอบเขตข้อมูล
- ตรวจว่า HTTP logger สร้าง record เมื่อ response จบและรวม status code ที่สำเร็จ/error; ไม่ได้ทำ load test หรือ fault-injection ของ log storage ในการประเมินนี้
- ตรวจ flow PII masker → LLM gateway จาก source; ไม่ได้ทำ red-team test, coverage test ของ PII patterns หรือทดสอบกับ provider จริง
- ไม่ได้ทำ penetration test, dependency vulnerability scan, cloud/IAM review, MongoDB backup/restore test หรือ formal PDPA/legal review
- การตรวจนี้ไม่ใช่หลักฐานว่าไม่มีช่องโหว่; ควรทำ automated security tests และ external review ก่อน production

### Third-Party Components & Licenses

Runtime components ที่พบจาก manifests ได้แก่ Next.js, React, Express, Mongoose, MongoDB server image (ใน Compose), Helmet, CORS และ Zod; AI provider เป็น external OpenAI-compatible URL ที่ผู้ deploy กำหนดผ่าน env

ยังไม่ได้ทำ license inventory/SBOM หรือ dependency vulnerability scan สำหรับ transitive dependencies และยังไม่ทราบผู้ให้บริการ/เงื่อนไข LLM ที่จะเลือก ตรวจ `package-lock.json`/container image versions, สร้าง SBOM, สแกน CVE และทบทวน license/provider terms ก่อนปล่อย production

## Recommended actions before production

1. ทำ PII/data allowlist สำหรับ LLM และ fail closed เมื่อ masking/validation ไม่ผ่าน
2. แก้ CSRF/origin validation และทดสอบ mutation ทั้ง browser และ trusted service client
3. ออกแบบ consent แยกตามวัตถุประสงค์และให้ privacy/legal review; อย่าอ้าง PDPA compliance ก่อนตรวจครบ
4. เพิ่ม AI step event sink, domain audit trail, central log retention/access control และ alert
5. เพิ่ม shared rate limiting, trusted proxy config, MFA/least privilege สำหรับ admin และ account recovery
6. ปิด demo seed/credential ใน production; ใช้ secret manager และตรวจ dependency/license/SBOM
7. ทำ threat-based security tests, penetration test และทบทวน deployment configuration
