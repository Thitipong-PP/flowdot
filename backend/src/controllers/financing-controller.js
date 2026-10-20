import { FinancingProduct } from '../models/financing-product.js';
import { CustomerProfile } from '../models/customer-profile.js';
import { recommendFinancing } from '../services/financing-service.js';
import { HttpError } from '../utils/http-error.js';

export async function listFinancingProducts(_req, res) {
  const products = await FinancingProduct.find({ active: true }).select('-__v -acceptedEntityTypes -acceptedRevenueBands').lean();
  return res.json({ data: products });
}

export async function getRecommendations(req, res) {
  if (!req.auth?.customerId) throw new HttpError(403, 'A customer profile is required to find financing.');
  const profile = await CustomerProfile.findById(req.auth.customerId).select('legalEntityType vatRegistered businessAge annualRevenueBand collateralAvailable').lean();
  if (!profile) throw new HttpError(404, 'Customer profile not found.');
  const products = await recommendFinancing(profile);
  return res.json({ data: products });
}
