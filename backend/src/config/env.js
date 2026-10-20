import 'dotenv/config';

const port = Number(process.env.PORT ?? 4000);

export const env = {
  nodeEnv: process.env.NODE_ENV ?? 'development',
  port: Number.isInteger(port) && port > 0 ? port : 4000,
  host: process.env.HOST ?? (process.env.NODE_ENV === 'production' ? '0.0.0.0' : '127.0.0.1'),
  frontendOrigin: process.env.FRONTEND_ORIGIN ?? 'http://localhost:3000',
  authSecret: process.env.AUTH_SECRET,
  authCookieName: 'flow_session',
  adminEmail: process.env.ADMIN_EMAIL?.toLowerCase(),
  adminPassword: process.env.ADMIN_PASSWORD,
  demoCustomerEmail: process.env.DEMO_CUSTOMER_EMAIL?.toLowerCase(),
  demoCustomerPassword: process.env.DEMO_CUSTOMER_PASSWORD,
  mongoUri: process.env.MONGODB_URI,
  aiServiceUrl: process.env.AI_SERVICE_URL?.replace(/\/$/, ''),
  aiServiceToken: process.env.AI_SERVICE_TOKEN,
  aiServiceTimeoutMs: Number(process.env.AI_SERVICE_TIMEOUT_MS ?? 180000),
};
