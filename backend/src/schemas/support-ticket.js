import { z } from 'zod';

export const createSupportTicketSchema = z.object({
  body: z.object({
    subject: z.string().trim().min(1).max(160),
    message: z.string().trim().min(1).max(4000),
  }).strict(),
  params: z.object({}),
  query: z.object({}),
});

export const updateSupportTicketSchema = z.object({
  body: z.object({ status: z.enum(['open', 'in_progress', 'resolved']) }).strict(),
  params: z.object({ ticketId: z.string().regex(/^[a-f\d]{24}$/i) }),
  query: z.object({}),
});

export const listSupportTicketsSchema = z.object({
  body: z.object({}).optional(),
  params: z.object({}),
  query: z.object({ status: z.enum(['open', 'in_progress', 'resolved']).optional() }),
});
