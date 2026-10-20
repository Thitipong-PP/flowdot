import { z } from 'zod';

export const chatSchema = z.object({
  body: z.object({ message: z.string().trim().min(1).max(4000) }).strict(),
  params: z.object({}), query: z.object({}),
});
