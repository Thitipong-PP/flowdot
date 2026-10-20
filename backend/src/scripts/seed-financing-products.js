import { connectDatabase, disconnectDatabase } from '../config/database.js';
import { FinancingProduct } from '../models/financing-product.js';

const products = [
  {
    code: 'KBANK-SME-WORKING-CAPITAL',
    name: 'SME Working Capital',
    lender: 'Kasikornbank',
    description: 'Unsecured working capital loan for eligible SMEs.',
    maximumAmount: 1_500_000,
    startingAnnualRate: 7.5,
    minBusinessAgeMonths: 12,
    acceptedEntityTypes: ['individual', 'commercial_registration', 'limited_partnership', 'limited_company'],
    acceptedRevenueBands: ['up_to_75m', '75m_to_500m'],
  },
  {
    code: 'SCB-SME-EXPRESS',
    name: 'Business Boost',
    lender: 'SCB',
    description: 'SME Express financing for business growth.',
    maximumAmount: 800_000,
    startingAnnualRate: 8.2,
    minBusinessAgeMonths: 6,
    acceptedEntityTypes: ['individual', 'commercial_registration', 'limited_partnership', 'limited_company'],
    acceptedRevenueBands: ['up_to_75m', '75m_to_500m'],
  },
];

try {
  await connectDatabase();
  await Promise.all(products.map(({ code, ...product }) => FinancingProduct.updateOne(
    { code },
    { $set: { code, ...product } },
    { upsert: true, runValidators: true },
  )));
  console.info(`Seeded ${products.length} illustrative financing products.`);
} catch (error) {
  console.error(`Unable to seed financing products: ${error.message}`);
  process.exitCode = 1;
} finally {
  await disconnectDatabase();
}
