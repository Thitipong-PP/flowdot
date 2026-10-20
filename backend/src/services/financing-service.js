import { FinancingProduct } from '../models/financing-product.js';

const AGE_MONTHS = {
  under_6_months: 3,
  '6_months_to_1_year': 9,
  '1_to_3_years': 24,
  '3_to_5_years': 48,
  over_5_years: 72,
};

export async function recommendFinancing(profile) {
  const products = await FinancingProduct.find({ active: true }).lean();
  return products
    .filter((product) => {
      if (profile.legalEntityType && product.acceptedEntityTypes.length && !product.acceptedEntityTypes.includes(profile.legalEntityType)) return false;
      if (profile.annualRevenueBand && product.acceptedRevenueBands.length && !product.acceptedRevenueBands.includes(profile.annualRevenueBand)) return false;
      if (profile.vatRegistered === false && product.requiresVatRegistration) return false;
      if (profile.collateralAvailable === false && product.requiresCollateral) return false;
      if (profile.businessAge && AGE_MONTHS[profile.businessAge] < product.minBusinessAgeMonths) return false;
      return true;
    })
    .map((product) => ({
      id: product._id,
      code: product.code,
      name: product.name,
      lender: product.lender,
      description: product.description,
      maximumAmount: product.maximumAmount,
      startingAnnualRate: product.startingAnnualRate,
    }));
}
