import cors from 'cors';
import express from 'express';
import helmet from 'helmet';
import { env } from './config/env.js';
import { errorHandler } from './middleware/error-handler.js';
import { notFoundHandler } from './middleware/not-found.js';
import { requestLogger } from './middleware/request-logger.js';
import { requireTrustedOrigin } from './middleware/require-trusted-origin.js';
import apiRoutes from './routes/api-routes.js';
import authRoutes from './routes/auth-routes.js';
import healthRoutes from './routes/health-routes.js';

const app = express();

app.disable('x-powered-by');
app.use(helmet());
app.use(requestLogger);
const allowedOrigins = env.frontendOrigin.split(',').map((origin) => origin.trim());
app.use(cors({ origin: allowedOrigins, credentials: true }));
app.use(requireTrustedOrigin);
app.use(express.json({ limit: '1mb' }));
app.use('/api/v1/auth', authRoutes);
app.use('/api/health', healthRoutes);
app.use('/api/v1', apiRoutes);
app.use(notFoundHandler);
app.use(errorHandler);

export default app;
