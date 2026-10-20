# Permission tiers and audit logging

เอกสารนี้อธิบายสิทธิ์ที่โค้ดปัจจุบันบังคับใช้ และรูปแบบ log สำหรับตรวจสอบคำขอและการทำงานของ AI โดยแยกสิ่งที่ระบบทำแล้วออกจากข้อเสนอสำหรับการเชื่อม AI ของทีม

## Permission tiers ที่มีในปัจจุบัน

ระบบมี role ในบัญชีสองระดับ คือ `customer` และ `admin` การตรวจสิทธิ์ทำที่ backend ทุก request ที่ใช้ session ไม่ควรอาศัยการซ่อนปุ่มหรือหน้าใน frontend เป็นมาตรการควบคุมสิทธิ์

| ความสามารถ | ผู้เยี่ยมชม | Customer | Admin |
| --- | --- | --- | --- |
| Health check (`GET /api/health`) | ได้ | ได้ | ได้ |
| ดูผลิตภัณฑ์สินเชื่อที่เปิดใช้งาน (`GET /api/v1/financing/products`) | ได้ | ได้ | ได้ |
| สมัครบัญชี (`POST /api/v1/auth/register`) | สร้างบัญชี customer | — | — |
| เข้าสู่ระบบ | ได้ | ได้ | ได้ |
| ดู session / ออกจากระบบ | ไม่ได้ | ของตนเอง | ของตนเอง |
| ดูหรือแก้ไขโปรไฟล์ (`/customers/me`) | ไม่ได้ | ของตนเอง | ไม่มี endpoint สำหรับแก้โปรไฟล์ admin ในขณะนี้ |
| ดู dashboard / รายการธุรกรรม | ไม่ได้ | ธุรกรรมของตนเอง | ไม่มีสิทธิ์ผ่าน endpoint ปัจจุบัน |
| เพิ่มธุรกรรม | ไม่ได้ | เพิ่มในบัญชีของตนเอง | ไม่มีสิทธิ์ผ่าน endpoint ปัจจุบัน |
| ขอคำแนะนำสินเชื่อ | ไม่ได้ | ใช้โปรไฟล์ของตนเอง | ไม่มีสิทธิ์ผ่าน endpoint ปัจจุบัน |
| สร้าง ticket / ดู ticket | ไม่ได้ | สร้างและดู ticket ของตนเอง | ดู ticket ทั้งหมด |
| เปลี่ยนสถานะ ticket | ไม่ได้ | ไม่ได้ | ได้ |
| ดูรายชื่อลูกค้า / ดูโปรไฟล์ลูกค้าตาม ID | ไม่ได้ | ไม่ได้ | ได้ |
| จัดการ role, ปิดบัญชี, สร้าง admin | ไม่ได้ | ไม่ได้ | ยังไม่มี endpoint สำหรับงานเหล่านี้ |

บัญชีที่สมัครผ่าน API จะเป็น `customer` เท่านั้น บัญชี `admin` ถูกสร้างจาก `ADMIN_EMAIL` และ `ADMIN_PASSWORD` ตอน backend เริ่มทำงานครั้งแรก ไม่มีหน้า self-service สำหรับยกระดับ role

### ขอบเขต endpoint

- สาธารณะ: `GET /api/health`, `GET /api/v1/financing/products`, `POST /api/v1/auth/register`, `POST /api/v1/auth/login`.
- ผู้ใช้ที่เข้าสู่ระบบ: `GET /api/v1/auth/session`, `POST /api/v1/auth/logout`.
- Customer: `/api/v1/customers/me*`, `/api/v1/transactions*`, `POST /api/v1/financing/recommendations`, `POST /api/v1/assistant/chat`, `POST /api/v1/support/tickets` และ `GET /api/v1/support/tickets` (เห็นเฉพาะ ticket ที่ตนเองเป็นเจ้าของ).
- Admin: `GET /api/v1/customers`, `GET /api/v1/customers/:customerId`, `PATCH /api/v1/support/tickets/:ticketId` และ `GET /api/v1/support/tickets` (เห็นทั้งหมด).

`GET /api/v1/customers/:customerId` ส่งคืนข้อมูลโปรไฟล์ที่ละเอียดกว่ารายชื่อลูกค้า จึงควรถือเป็นข้อมูลส่วนบุคคลที่มีการจำกัดสิทธิ์ ไม่ควรเพิ่ม role อื่นให้เรียก endpoint นี้โดยไม่กำหนดขอบเขตข้อมูลใหม่

## HTTP request log ที่ระบบเขียนอยู่แล้ว

Middleware สร้าง JSON Lines หนึ่ง record ต่อ HTTP response ที่จบแล้ว รวม response `2xx` เช่น `200`, `201` และ error status เช่น `400`, `401`, `403`, `429`, `500`, `503` โดยไฟล์แบ่งตามวันที่ UTC ที่ `backend/.data/logs/YYYY-MM-DD.jsonl` และส่ง record เดียวกันไป stdout หรือ stderr

ตัวอย่าง `200 OK`:

```json
{"timestamp":"2026-10-20T04:15:30.123Z","level":"info","event":"http_request","requestId":"9cc99a72-65ae-4904-97c6-67dc1517ff88","method":"GET","path":"/api/v1/customers/me","status":200,"durationMs":18.42,"actorRole":"customer"}
```

ฟิลด์ที่มีในปัจจุบัน:

| ฟิลด์ | ความหมาย |
| --- | --- |
| `timestamp` | เวลา UTC แบบ ISO 8601 |
| `level` | `info` สำหรับต่ำกว่า 400, `warn` สำหรับ 4xx, `error` สำหรับ 5xx |
| `event` | ชนิด event; ปัจจุบันคือ `http_request` |
| `requestId` | UUID สำหรับค้น log ของ request เดียวกัน; ส่งกลับใน header `x-request-id` |
| `method`, `path` | HTTP method และ path โดยไม่บันทึก query string |
| `status` | status code ของ response ที่ส่งกลับ |
| `durationMs` | เวลา request ตั้งแต่เข้า middleware จน response จบ |
| `actorRole` | มีเมื่อ middleware ยืนยันตัวตนได้ เช่น `customer` หรือ `admin` |
| `errorType`, `errorCode` | มีเมื่อ error handler ส่ง metadata กลับมา; ไม่มี error message หรือ stack trace ใน request record |

ไม่บันทึก request body, query string, cookie, authorization header, prompt หรือ response body ลง HTTP request log ตามการทำงานปัจจุบัน ไฟล์ log ถูก ignore จาก Git และสร้างด้วย permission `0600` ในกรณีไฟล์ใหม่ ระบบพยายาม append log หลัง response จบ; หากเขียนไฟล์ไม่ได้จะรายงาน `log_write_failed` ไป stderr

## AI workflow logging และการเชื่อมกับ AI ของทีม

### สถานะในโค้ดปัจจุบัน

Assistant ปัจจุบันทำงานเป็นขั้นสั้น ๆ: validate message, เรียก PII masker, ส่ง request ไป OpenAI-compatible endpoint และดึงข้อความผลลัพธ์ ระบบบันทึกได้เพียง `http_request` ของ `POST /api/v1/assistant/chat` ยังไม่มี event log แยกสำหรับขั้น AI, ไม่มี agent orchestration หลายขั้น และไม่มี callback contract ที่ผูกกับ AI framework ของทีม การตั้งค่า provider ยังไม่ครบจะได้ `503` และ request ดังกล่าวยังปรากฏใน HTTP log

ดังนั้นตารางและ event contract ด้านล่างเป็นข้อกำหนดสำหรับการต่อ integration; ยังไม่ใช่ log ที่ระบบปล่อยออกมาแล้ว

### Event ที่ AI adapter ควรส่ง

ให้ backend เป็นผู้รับ event จาก AI adapter ของทีม แล้วเขียนเป็น structured JSONL โดยผูก `requestId` เดิมกับ `runId` และ `stepId`:

1. `ai_run_started` เมื่อเริ่มงาน AI
2. `ai_step_started` ก่อนแต่ละขั้น เช่น `input_validation`, `pii_masking`, `context_retrieval`, `provider_request`, `response_validation` หรือชื่อขั้นจริงของ workflow
3. `ai_step_completed` เมื่อขั้นนั้นเสร็จ พร้อม outcome แบบปลอดภัย เช่น จำนวนรายการที่พบหรือผล validation ผ่านหรือไม่
4. `ai_step_failed` เมื่อขั้นล้มเหลว พร้อม error class/code ที่ไม่เปิดเผยข้อมูลลับ และระบุว่า retry ได้หรือไม่
5. `ai_run_completed` หรือ `ai_run_failed` เมื่อปิด run พร้อมสถานะรวมและเวลารวม

ตัวอย่าง event เมื่อ masking ผ่าน (ตัวอย่าง schema เป้าหมาย ไม่ใช่ output ที่มีในปัจจุบัน):

```json
{"timestamp":"2026-10-20T04:15:30.124Z","level":"info","event":"ai_step_completed","requestId":"9cc99a72-65ae-4904-97c6-67dc1517ff88","runId":"ai-73b4a2","stepId":"step-02","step":"pii_masking","status":"success","durationMs":2.1,"result":{"inputAccepted":true,"redactionCount":2,"redactionTypes":["email","phone"]}}
```

แนะนำฟิลด์ร่วมสำหรับ AI event: `timestamp`, `level`, `event`, `requestId`, `runId`, `stepId`, `step`, `status`, `durationMs`, `provider`, `model`, `attempt` และ `result` แบบสรุปที่ผ่านการตรวจข้อมูลแล้ว สำหรับความล้มเหลวใช้ `errorType`, `errorCode`, `retryable` และ `result` สรุปสาเหตุ ห้ามบันทึกข้อความ exception จาก provider ตรง ๆ โดยไม่ sanitize

### Integration contract สำหรับทีม AI

AI adapter ควรรับ event sink หรือ callback ที่ backend ส่งให้ แทนการเขียน log อิสระหลายรูปแบบ ตัวอย่าง interface ที่ framework ใดก็ปรับใช้ได้:

```ts
type AiStepEvent = {
  runId: string;
  stepId: string;
  step: string;
  phase: "started" | "completed" | "failed";
  status?: "success" | "error";
  durationMs?: number;
  provider?: string;
  model?: string;
  resultSummary?: Record<string, string | number | boolean | string[]>;
  errorType?: string;
  errorCode?: string;
  retryable?: boolean;
};

type AiEventSink = (event: AiStepEvent) => void | Promise<void>;
```

ให้ adapter ส่งเฉพาะชื่อขั้น สถานะ และ summary ที่อนุญาตไว้ ไม่ส่ง prompt, completion, chain-of-thought, customer profile, secret, access token หรือ raw exception เข้า sink ระบบ backend ควรเติม `requestId`, `actorRole` (ถ้าทราบ), timestamp และเขียนผ่าน logger กลาง ห้ามให้ provider เป็นผู้กำหนด `requestId` หรือเขียน raw log ลง shared storage โดยตรง

หาก output summary มาจากข้อความอิสระของ model ให้แปลงเป็น enum/ตัวเลขที่ schema กำหนดก่อนเขียน log เช่น `resultCount`, `schemaValid`, `decisionCategory`; หลีกเลี่ยงการบันทึกคำตอบที่ model สร้างขึ้นทั้งประโยค เพราะอาจสะท้อนข้อมูลผู้ใช้กลับมา

### ข้อห้ามด้านข้อมูลใน AI logs

- ไม่ log prompt/input/output ดิบ รวมถึงข้อความที่ผ่านการ mask แล้ว หากยังมีรายละเอียดธุรกิจหรือการเงิน
- ไม่ log ชื่อ อีเมล โทรศัพท์ เลขบัญชี เลขประจำตัว ที่อยู่ ยอดเงิน หรือข้อมูลระบุตัวบุคคลใน `resultSummary`
- ใช้ opaque IDs (`requestId`, `runId`, `stepId`) และจำกัดสิทธิ์เข้าถึง log
- บันทึกจำนวน/ประเภทการ redact ได้ แต่ห้ามบันทึกค่าก่อนหรือหลัง redact
- ห้ามบันทึก secret, API key, cookie, authorization header, provider URL ที่มี credential หรือ chain-of-thought
- กำหนด retention, การลบ, encryption at rest, access audit และ alert ก่อนใช้กับข้อมูลจริง

## อ่าน log ในเครื่อง

```bash
# ดู log ของวันนี้ตามเวลา UTC
tail -F "backend/.data/logs/$(date -u +%F).jsonl"

# ดูเฉพาะ request ที่ได้ 200
jq 'select(.event == "http_request" and .status == 200)' backend/.data/logs/"$(date -u +%F).jsonl"

# ค้น request ตาม request ID
jq 'select(.requestId == "<request-id>")' backend/.data/logs/"$(date -u +%F).jsonl"
```

ถ้ารัน backend ใน terminal ที่เปิดอยู่ จะเห็น JSONL ที่ stdout/stderr ด้วย ถ้ารันเป็น service/container ให้ใช้ log viewer ของ process manager/container และเก็บไฟล์หรือส่ง stdout ไป centralized log platform โดยคง schema เดิม

## Operational gaps ที่ควรทำก่อน production

- เพิ่ม AI run/step event sink ตาม contract ข้างต้น
- เพิ่ม audit event สำหรับการเปลี่ยนแปลงข้อมูลสำคัญ เช่น update profile, create transaction, update ticket และการอ่าน profile โดย admin โดยบันทึก resource ID แบบ opaque และผลสำเร็จ/ล้มเหลว ห้ามเก็บ payload
- เพิ่ม log rotation/retention, centralized collection, monitoring/alert และทดสอบกรณี log store ล่ม
- ทบทวน CSRF/origin policy ก่อนเปิด API ให้เข้าถึงจากเครือข่ายอื่น
- เปลี่ยน rate limiter เป็น shared store เมื่อมีหลาย instance และกำหนด trusted proxy ให้เหมาะกับ deployment
