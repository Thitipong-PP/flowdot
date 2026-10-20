import app from './app.js';
import { connectDatabase, disconnectDatabase } from './config/database.js';
import { env } from './config/env.js';
import { UserAccount } from './models/user-account.js';
import { hashPassword } from './services/auth-service.js';

let server;

try {
  if (!env.authSecret || env.authSecret.length < 32) throw new Error('AUTH_SECRET must contain at least 32 characters.');
  await connectDatabase();
  if (env.adminEmail && env.adminPassword) {
    await UserAccount.updateOne(
      { email: env.adminEmail },
      { $setOnInsert: { email: env.adminEmail, passwordHash: await hashPassword(env.adminPassword), role: 'admin', active: true } },
      { upsert: true },
    );
  }
  server = app.listen(env.port, env.host, () => {
    console.info(`Flow API listening on http://${env.host}:${env.port}`);
  });
} catch (error) {
  console.error(`Unable to start the API: ${error.message}`);
  process.exitCode = 1;
}

async function shutdown(signal) {
  console.info(`${signal} received; shutting down API.`);
  if (server) {
    await new Promise((resolve) => server.close(resolve));
  }
  await disconnectDatabase();
}

process.once('SIGINT', () => shutdown('SIGINT'));
process.once('SIGTERM', () => shutdown('SIGTERM'));
