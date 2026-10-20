import { SupportTicket } from '../models/support-ticket.js';
import { HttpError } from '../utils/http-error.js';

export async function createTicket(req, res) {
  if (!req.auth.customerId) throw new HttpError(403, 'This account has no customer profile.');
  const ticket = await SupportTicket.create({ ...req.validated.body, customerId: req.auth.customerId });
  return res.status(201).json({ data: ticket });
}

export async function listTickets(req, res) {
  const filter = {
    ...(req.auth.role === 'admin' ? {} : { customerId: req.auth.customerId }),
    ...(req.validated.query.status ? { status: req.validated.query.status } : {}),
  };
  const tickets = await SupportTicket.find(filter).populate('customerId', 'firstName lastName businessName').sort({ createdAt: -1 }).limit(100).lean();
  return res.json({ data: tickets });
}

export async function updateTicketStatus(req, res) {
  const ticket = await SupportTicket.findByIdAndUpdate(
    req.validated.params.ticketId,
    { status: req.validated.body.status },
    { new: true, runValidators: true },
  ).lean();
  if (!ticket) throw new HttpError(404, 'Support ticket not found.');
  return res.json({ data: ticket });
}
