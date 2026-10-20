import { z } from 'zod';

export const recommendationsSchema = z.object({
  body: z.object({}).strict(),
  params: z.object({}),
  query: z.object({}),
});
