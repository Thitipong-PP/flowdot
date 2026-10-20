const patterns = [
  { name: 'email', pattern: /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/giu },
  { name: 'thai_national_id', pattern: /\b\d{1}-?\d{4}-?\d{5}-?\d{2}-?\d{1}\b/g },
  { name: 'phone', pattern: /(?<!\d)(?:\+?66|0)[\s-]?(?:\d[\s-]?){8,9}(?!\d)/g },
  { name: 'account_number', pattern: /\b\d{10,16}\b/g },
  { name: 'street_address', pattern: /\b\d{1,5}\s+(?:[\w.]+\s+){0,4}(?:street|road|rd\.?|soi|moo|lane|avenue|ave\.?|ตำบล|อำเภอ|ถนน)\b/giu },
  { name: 'person_name', pattern: /\b(?:my name is|i am|i'm|ชื่อ(?:ของฉัน)?คือ)\s+[\p{L}][\p{L}'-]*(?:\s+[\p{L}][\p{L}'-]*){0,2}/giu },
  { name: 'thai_person_name', pattern: /(?:ฉันชื่อ|ผมชื่อ|ดิฉันชื่อ|หนูชื่อ)\s*[\p{L}]+(?:\s+[\p{L}]+)?/gu },
];

export function maskPii(value) {
  if (typeof value === 'string') {
    return patterns.reduce((text, { name, pattern }) => text.replace(pattern, `[${name.toUpperCase()}_REDACTED]`), value);
  }
  if (Array.isArray(value)) return value.map(maskPii);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [
      key,
      /(?:name|email|phone|address|national.?id|passport|account.?number|tax.?id|date.?of.?birth)/i.test(key)
        ? `[${key.toUpperCase()}_REDACTED]`
        : maskPii(item),
    ]));
  }
  return value;
}
