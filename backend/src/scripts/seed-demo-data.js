import 'dotenv/config';
import { connectDatabase, disconnectDatabase } from '../config/database.js';
import { CustomerProfile } from '../models/customer-profile.js';
import { SupportTicket } from '../models/support-ticket.js';
import { Transaction } from '../models/transaction.js';
import { UserAccount } from '../models/user-account.js';
import { hashPassword } from '../services/auth-service.js';

const profileInput = {
  firstName: 'Ploy', lastName: 'Pattanakul', email: process.env.DEMO_CUSTOMER_EMAIL?.toLowerCase(), phone: '0812345678',
  businessName: 'Baan Kafe Demo', legalEntityType: 'limited_company', vatRegistered: true,
  businessAge: '3_to_5_years', ownerAge: '36_to_50', ownerNationality: 'Thai', industry: 'Food & beverage',
  annualRevenueBand: 'up_to_75m', minimumCashReserve: 50000, monthlyDebtPayment: 25000,
  outstandingDebt: 420000, nextPaymentDueDay: 25, fixedMonthlyExpenses: 80000,
  financingPurpose: 'working_capital', collateralAvailable: false, latePaymentOver90Days: 'no', financialDataConsent: true,
};

if (!profileInput.email || !process.env.DEMO_CUSTOMER_PASSWORD || !process.env.ADMIN_EMAIL || !process.env.ADMIN_PASSWORD) {
  throw new Error('Set ADMIN_EMAIL, ADMIN_PASSWORD, DEMO_CUSTOMER_EMAIL, and DEMO_CUSTOMER_PASSWORD in backend/.env first.');
}

try {
  await connectDatabase();
  let profile = await CustomerProfile.findOne({ email: profileInput.email });
  if (!profile) profile = await CustomerProfile.create(profileInput);
  await UserAccount.updateOne(
    { email: profile.email },
    { $setOnInsert: { email: profile.email, customerId: profile._id, passwordHash: await hashPassword(process.env.DEMO_CUSTOMER_PASSWORD), role: 'customer', active: true } },
    { upsert: true },
  );
  await UserAccount.updateOne(
    { email: process.env.ADMIN_EMAIL.toLowerCase() },
    { $setOnInsert: { email: process.env.ADMIN_EMAIL.toLowerCase(), passwordHash: await hashPassword(process.env.ADMIN_PASSWORD), role: 'admin', active: true } },
    { upsert: true },
  );

  if (await Transaction.countDocuments({ customerId: profile._id }) === 0) {
    const now = Date.now();
    await Transaction.insertMany([
      { customerId: profile._id, type: 'income', description: 'Catering order', category: 'Sales', amount: 18200, occurredAt: new Date(now - 2 * 86400000), source: 'manual' },
      { customerId: profile._id, type: 'expense', description: 'Coffee bean supplier', category: 'Inventory', amount: 4250, occurredAt: new Date(now - 86400000), source: 'receipt' },
      { customerId: profile._id, type: 'expense', description: 'Cafe utilities', category: 'Utilities', amount: 1850, occurredAt: new Date(now - 6 * 3600000), source: 'manual' },
    ]);
  }
  if (await SupportTicket.countDocuments({ customerId: profile._id }) === 0) {
    await SupportTicket.create({ customerId: profile._id, subject: 'Question about financing eligibility', message: 'I would like to understand which documents are needed for an application.', status: 'open' });
  }
  console.info('Demo customer, admin account, transactions, and support ticket are ready. Credentials are stored in backend/.env.');
} finally {
  await disconnectDatabase();
}
