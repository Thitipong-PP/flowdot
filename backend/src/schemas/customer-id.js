import { z } from 'zod';

export const customerIdSchema = z.object({
  body: z.object({}).optional(),
  params: z.object({ customerId: z.string().regex(/^[a-f\d]{24}$/i) }),
  query: z.object({}),
});
