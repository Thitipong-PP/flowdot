import mongoose from 'mongoose';
import { Transaction } from '../models/transaction.js';
import { HttpError } from '../utils/http-error.js';

function requireCustomerId(req) {
  if (!req.auth.customerId) throw new HttpError(403, 'This account has no customer profile.');
  return req.auth.customerId;
}

export async function createTransaction(req, res) {
  const transaction = await Transaction.create({
    ...req.validated.body,
    occurredAt: req.validated.body.occurredAt ?? new Date(),
    customerId: requireCustomerId(req),
  });
  return res.status(201).json({ data: transaction });
}

export async function listMyTransactions(req, res) {
  const transactions = await Transaction.find({ customerId: requireCustomerId(req) }).sort({ occurredAt: -1 }).limit(100).lean();
  return res.json({ data: transactions });
}

export async function getMyDashboard(req, res) {
  const customerId = requireCustomerId(req);
  const rows = await Transaction.aggregate([
    { $match: { customerId: new mongoose.Types.ObjectId(customerId) } },
    { $group: { _id: '$type', total: { $sum: '$amount' }, count: { $sum: 1 } } },
  ]);
  const totals = Object.fromEntries(rows.map((row) => [row._id, { total: row.total, count: row.count }]));
  const transactions = await Transaction.find({ customerId }).sort({ occurredAt: -1 }).limit(20).lean();
  return res.json({ data: { source: 'stored_transactions', totals: {
    income: totals.income ?? { total: 0, count: 0 }, expense: totals.expense ?? { total: 0, count: 0 },
  }, transactions } });
}
