import { CustomerProfile } from '../models/customer-profile.js';
import { UserAccount } from '../models/user-account.js';
import { HttpError } from '../utils/http-error.js';
import { createSessionToken, hashPassword, sessionCookie, verifyPassword } from '../services/auth-service.js';

function publicAccount(account, profile = null) {
  return {
    id: account.id,
    role: account.role,
    email: account.email,
    profile: profile ? {
      id: profile.id, firstName: profile.firstName, lastName: profile.lastName, phone: profile.phone,
      businessName: profile.businessName, industry: profile.industry,
    } : null,
  };
}

export async function register(req, res) {
  const { password, ...profileInput } = req.validated.body;
  const profile = await CustomerProfile.create(profileInput);
  try {
    const account = await UserAccount.create({ email: profile.email, passwordHash: await hashPassword(password), customerId: profile._id });
    res.setHeader('Set-Cookie', sessionCookie(createSessionToken(account)));
    return res.status(201).json({ data: publicAccount(account, profile) });
  } catch (error) {
    await CustomerProfile.deleteOne({ _id: profile._id });
    throw error;
  }
}

export async function login(req, res) {
  const account = await UserAccount.findOne({ email: req.validated.body.email }).select('+passwordHash');
  const passwordMatches = await verifyPassword(req.validated.body.password, account?.passwordHash);
  if (!account || !passwordMatches || !account.active) throw new HttpError(401, 'Email or password is incorrect.');
  account.lastLoginAt = new Date();
  await account.save();
  const profile = account.customerId ? await CustomerProfile.findById(account.customerId).lean() : null;
  res.setHeader('Set-Cookie', sessionCookie(createSessionToken(account)));
  return res.json({ data: publicAccount(account, profile) });
}

export async function logout(_req, res) {
  await UserAccount.updateOne({ _id: _req.auth.accountId }, { $inc: { sessionVersion: 1 } });
  res.setHeader('Set-Cookie', sessionCookie('', 0));
  return res.json({ data: { success: true } });
}

export async function session(req, res) {
  const account = await UserAccount.findById(req.auth.accountId).select('email role customerId').lean();
  if (!account) throw new HttpError(401, 'Session expired. Please sign in again.');
  const profile = account.customerId ? await CustomerProfile.findById(account.customerId).lean() : null;
  return res.json({ data: publicAccount({ id: account._id.toString(), ...account }, profile) });
}
