import { Router } from 'express';
import { getCustomerProfile, getMyProfile, listCustomerProfiles, updateMyProfile } from '../controllers/customer-controller.js';
import { getRecommendations, listFinancingProducts } from '../controllers/financing-controller.js';
import { createTicket, listTickets, updateTicketStatus } from '../controllers/support-controller.js';
import { createTransactionSchema } from '../schemas/transaction.js';
import { updateProfileSchema } from '../schemas/auth.js';
import { recommendationsSchema } from '../schemas/financing.js';
import { createSupportTicketSchema, listSupportTicketsSchema, updateSupportTicketSchema } from '../schemas/support-ticket.js';
import { asyncHandler } from '../utils/async-handler.js';
import { validate } from '../middleware/validate.js';
import { authenticate, requireRole } from '../middleware/authenticate.js';
import { createTransaction, getMyDashboard, listMyTransactions } from '../controllers/transaction-controller.js';
import { chat } from '../controllers/assistant-controller.js';
import { chatSchema } from '../schemas/assistant.js';
import { customerIdSchema } from '../schemas/customer-id.js';

const router = Router();

router.get('/customers', authenticate, requireRole('admin'), asyncHandler(listCustomerProfiles));
router.get('/customers/me', authenticate, asyncHandler(getMyProfile));
router.patch('/customers/me', authenticate, validate(updateProfileSchema), asyncHandler(updateMyProfile));
router.get('/customers/me/dashboard', authenticate, asyncHandler(getMyDashboard));
router.get('/customers/:customerId', authenticate, requireRole('admin'), validate(customerIdSchema), asyncHandler(getCustomerProfile));
router.get('/financing/products', asyncHandler(listFinancingProducts));
router.post('/financing/recommendations', authenticate, validate(recommendationsSchema), asyncHandler(getRecommendations));
router.post('/transactions', authenticate, validate(createTransactionSchema), asyncHandler(createTransaction));
router.get('/transactions', authenticate, asyncHandler(listMyTransactions));
router.post('/assistant/chat', authenticate, validate(chatSchema), asyncHandler(chat));
router.post('/support/tickets', authenticate, validate(createSupportTicketSchema), asyncHandler(createTicket));
router.get('/support/tickets', authenticate, validate(listSupportTicketsSchema), asyncHandler(listTickets));
router.patch('/support/tickets/:ticketId', authenticate, requireRole('admin'), validate(updateSupportTicketSchema), asyncHandler(updateTicketStatus));

export default router;
