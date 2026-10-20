import { Router } from 'express';
import { login, logout, register, session } from '../controllers/auth-controller.js';
import { authRateLimit } from '../middleware/auth-rate-limit.js';
import { authenticate } from '../middleware/authenticate.js';
import { validate } from '../middleware/validate.js';
import { loginSchema, registerSchema } from '../schemas/auth.js';
import { asyncHandler } from '../utils/async-handler.js';

const router = Router();
router.post('/register', authRateLimit, validate(registerSchema), asyncHandler(register));
router.post('/login', authRateLimit, validate(loginSchema), asyncHandler(login));
router.post('/logout', authenticate, asyncHandler(logout));
router.get('/session', authenticate, asyncHandler(session));
export default router;
