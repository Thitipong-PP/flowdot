import { z } from 'zod';

export const registerSchema = z.object({
  body: z.object({
    firstName: z.string().trim().min(1).max(80), lastName: z.string().trim().min(1).max(80),
    email: z.email().max(254).transform((value) => value.toLowerCase()), phone: z.string().trim().min(8).max(24),
    password: z.string().min(12).max(128), businessName: z.string().trim().min(1).max(160),
    legalEntityType: z.enum(['individual', 'commercial_registration', 'limited_partnership', 'limited_company']),
    vatRegistered: z.boolean(), businessAge: z.enum(['under_6_months', '6_months_to_1_year', '1_to_3_years', '3_to_5_years', 'over_5_years']),
    ownerAge: z.enum(['under_20', '20_to_35', '36_to_50', '51_to_65', 'over_65']), ownerNationality: z.string().trim().min(1).max(60),
    industry: z.string().trim().min(1).max(100), annualRevenueBand: z.enum(['up_to_75m', '75m_to_500m', 'over_500m']),
    minimumCashReserve: z.number().nonnegative(), monthlyDebtPayment: z.number().nonnegative(), outstandingDebt: z.number().nonnegative(),
    nextPaymentDueDay: z.number().int().min(1).max(31), fixedMonthlyExpenses: z.number().nonnegative(),
    financingPurpose: z.enum(['working_capital', 'inventory_or_receivables', 'equipment_or_investment', 'business_expansion']),
    collateralAvailable: z.boolean(), latePaymentOver90Days: z.enum(['no', 'yes', 'prefer_not_to_say']), financialDataConsent: z.literal(true),
  }).strict(), params: z.object({}), query: z.object({}),
});

export const loginSchema = z.object({
  body: z.object({ email: z.email().transform((value) => value.toLowerCase()), password: z.string().min(1).max(128) }).strict(),
  params: z.object({}), query: z.object({}),
});

export const updateProfileSchema = z.object({
  body: z.object({
    firstName: z.string().trim().min(1).max(80).optional(),
    lastName: z.string().trim().min(1).max(80).optional(),
    phone: z.string().trim().min(8).max(24).optional(),
    businessName: z.string().trim().min(1).max(160).optional(),
    industry: z.string().trim().min(1).max(100).optional(),
  }).strict().refine((body) => Object.keys(body).length > 0, 'At least one field is required.'),
  params: z.object({}), query: z.object({}),
});
