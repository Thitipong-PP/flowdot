import { CustomerProfile } from '../models/customer-profile.js';
import { HttpError } from '../utils/http-error.js';

function toPublicProfile(profile) {
  if (!profile) return null;
  const { _id, __v, ...safeProfile } = profile;
  return { id: _id?.toString() ?? profile.id, ...safeProfile };
}

export async function getMyProfile(req, res) {
  if (!req.auth.customerId) throw new HttpError(403, 'This account has no customer profile.');
  const profile = await CustomerProfile.findById(req.auth.customerId).lean();
  if (!profile) throw new HttpError(404, 'Customer profile not found.');
  return res.json({ data: toPublicProfile(profile) });
}

export async function updateMyProfile(req, res) {
  if (!req.auth.customerId) throw new HttpError(403, 'This account has no customer profile.');
  const profile = await CustomerProfile.findByIdAndUpdate(req.auth.customerId, req.validated.body, { new: true, runValidators: true }).lean();
  if (!profile) throw new HttpError(404, 'Customer profile not found.');
  return res.json({ data: toPublicProfile(profile) });
}

export async function listCustomerProfiles(_req, res) {
  const profiles = await CustomerProfile.find().select('firstName lastName email businessName industry createdAt').sort({ createdAt: -1 }).limit(200).lean();
  return res.json({ data: profiles.map(toPublicProfile) });
}

export async function getCustomerProfile(req, res) {
  const profile = await CustomerProfile.findById(req.validated.params.customerId).select('-__v').lean();
  if (!profile) throw new HttpError(404, 'Customer profile not found.');
  return res.json({ data: toPublicProfile(profile) });
}
