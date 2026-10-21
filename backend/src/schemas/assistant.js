import { z } from 'zod';

export const chatSchema = z.object({
  body: z.object({
    message: z.string().trim().max(4000).default(''),
    image: z.string().max(15_000_000).optional(),
  }).refine((data) => Boolean((data.message && data.message.length > 0) || data.image), {
    message: 'Either message or image must be provided.',
  }),
  params: z.object({}), query: z.object({}),
});
