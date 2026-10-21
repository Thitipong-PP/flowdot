import dns from 'node:dns';
import mongoose from 'mongoose';
import { env } from './env.js';

export async function connectDatabase() {
  if (!env.mongoUri) {
    throw new Error('MONGODB_URI is required. Copy backend/.env.example to backend/.env and configure MongoDB.');
  }

  // Windows c-ares resolver often fails with querySrv ECONNREFUSED on mongodb+srv://
  // Fall back to reliable public DNS resolvers (Google / Cloudflare)
  if (env.mongoUri.startsWith('mongodb+srv://')) {
    try {
      dns.setServers(['8.8.8.8', '1.1.1.1']);
    } catch {
      // Ignore if setServers is not supported in the current environment
    }
  }

  mongoose.set('strictQuery', true);
  await mongoose.connect(env.mongoUri, {
    serverSelectionTimeoutMS: 5000,
    dbName: env.mongoDbName || 'fintech_copilot',
  });
  console.info(`[Database] Connected to MongoDB (${mongoose.connection.host}/${mongoose.connection.name})`);
  return mongoose.connection;
}

export async function disconnectDatabase() {
  await mongoose.disconnect();
}
