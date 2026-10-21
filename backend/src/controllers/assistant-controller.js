import mongoose from 'mongoose';
import { CustomerProfile } from '../models/customer-profile.js';
import { Transaction } from '../models/transaction.js';
import { env } from '../config/env.js';
import { maskPii } from '../services/pii-masker.js';
import { HttpError } from '../utils/http-error.js';

const BUSINESS_AGE_YEARS = {
  under_6_months: 0.25,
  '6_months_to_1_year': 0.75,
  '1_to_3_years': 2,
  '3_to_5_years': 4,
  over_5_years: 6,
};

async function getAssistantProfileContext(customerId) {
  if (!customerId || !mongoose.isValidObjectId(customerId)) throw new HttpError(403, 'A customer profile is required to use the assistant.');
  const profile = await CustomerProfile.findById(customerId)
    .select('financialDataConsent businessAge monthlyDebtPayment fixedMonthlyExpenses collateralAvailable minimumCashReserve businessName')
    .lean();
  if (!profile) throw new HttpError(404, 'Customer profile not found.');
  if (profile.financialDataConsent !== true) throw new HttpError(403, 'Financial data consent is required to use the assistant.');

  const now = new Date();
  const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
  const [totals = {}] = await Transaction.aggregate([
    { $match: { customerId: new mongoose.Types.ObjectId(customerId) } },
    { $group: {
      _id: null,
      recentIncome: { $sum: { $cond: [{ $and: [{ $eq: ['$type', 'income'] }, { $gte: ['$occurredAt', monthAgo] }] }, '$amount', 0] } },
      recentExpenses: { $sum: { $cond: [{ $and: [{ $eq: ['$type', 'expense'] }, { $gte: ['$occurredAt', monthAgo] }] }, '$amount', 0] } },
    } },
  ]);
  const monthlyRevenue = Number(totals.recentIncome ?? 0);
  const monthlyExpenses = Number(totals.recentExpenses ?? 0);
  const startingReserve = Number(profile.minimumCashReserve ?? 120000);
  const currentCash = startingReserve + monthlyRevenue - monthlyExpenses;

  return {
    business_name: profile.businessName || 'Somchai Supermart Ltd.',
    current_cash: currentCash > 0 ? currentCash : startingReserve,
    upcoming_debt: Number(profile.monthlyDebtPayment ?? 0),
    daily_burn_rate: monthlyExpenses > 0 ? monthlyExpenses / 30 : Number(profile.fixedMonthlyExpenses ?? 0) / 30,
    monthly_revenue: monthlyRevenue,
    net_income: monthlyRevenue - monthlyExpenses,
    business_age_years: BUSINESS_AGE_YEARS[profile.businessAge] ?? 0,
    has_collateral: profile.collateralAvailable === true,
  };
}

export async function chat(req, res) {
  if (!env.aiServiceUrl || !env.aiServiceToken) throw new HttpError(503, 'AI assistant is not configured.');
  const profileContext = await getAssistantProfileContext(req.auth.customerId);
  const startedAt = process.hrtime.bigint();
  let upstream;
  try {
    upstream = await fetch(`${env.aiServiceUrl}/api/v1/chat`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', authorization: `Bearer ${env.aiServiceToken}`, 'x-request-id': req.requestId },
      body: JSON.stringify({
        // Identity is server-derived; browser-supplied user IDs are never accepted.
        user_id: req.auth.accountId,
        content: maskPii(req.validated.body.message || (req.validated.body.image ? 'Please analyze this financial document.' : '')),
        profile_context: profileContext,
        image_base64: req.validated.body.image || undefined,
      }),
      signal: AbortSignal.timeout(env.aiServiceTimeoutMs),
    });
  } catch (error) {
    console.error(JSON.stringify({ event: 'ai_upstream_request', requestId: req.requestId, status: 'unavailable', errorType: error.name, durationMs: Number(process.hrtime.bigint() - startedAt) / 1e6 }));
    throw new HttpError(503, 'AI assistant is temporarily unavailable. Please try again.');
  }

  const durationMs = Number(process.hrtime.bigint() - startedAt) / 1e6;
  if (!upstream.ok) {
    console.error(JSON.stringify({ event: 'ai_upstream_request', requestId: req.requestId, status: upstream.status, durationMs }));
    throw new HttpError(upstream.status >= 500 ? 503 : 502, 'AI assistant could not complete this request.');
  }
  const result = await upstream.json().catch(() => null);
  if (typeof result?.reply_text !== 'string' || !result.reply_text.trim()) {
    console.error(JSON.stringify({ event: 'ai_upstream_request', requestId: req.requestId, status: 'invalid_response', durationMs }));
    throw new HttpError(502, 'AI assistant returned an invalid response.');
  }
  console.info(JSON.stringify({ event: 'ai_upstream_request', requestId: req.requestId, status: upstream.status, durationMs }));
  return res.json({
    data: {
      message: result.reply_text,
      cashflow: result.cashflow ?? null,
      loans: Array.isArray(result.loans) ? result.loans : [],
      flowType: result.flow_type ?? null,
      income: result.income ?? 0,
      expense: result.expense ?? 0,
    },
  });
}
