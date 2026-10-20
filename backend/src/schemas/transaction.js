import { z } from 'zod';

export const createTransactionSchema = z.object({
  body: z.object({
    type: z.enum(['income', 'expense']), description: z.string().trim().min(1).max(160),
    category: z.string().trim().min(1).max(80), amount: z.number().positive(),
    occurredAt: z.iso.datetime().optional(), source: z.enum(['manual', 'receipt']).default('manual'),
  }).strict(), params: z.object({}), query: z.object({}),
});
