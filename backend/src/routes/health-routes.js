import { Router } from 'express';
import mongoose from 'mongoose';

const router = Router();

router.get('/', (_req, res) => {
  const database = mongoose.connection.readyState === 1 ? 'connected' : 'disconnected';
  const status = database === 'connected' ? 200 : 503;
  return res.status(status).json({ data: {
    status: database === 'connected' ? 'ok' : 'unavailable',
    database,
    assistant: process.env.LLM_API_URL && process.env.LLM_API_KEY && process.env.LLM_MODEL ? 'configured' : 'not_configured',
  } });
});

export default router;
