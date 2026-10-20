import mongoose from 'mongoose';

const { Schema, model, models } = mongoose;

const customerProfileSchema = new Schema({
  firstName: { type: String, required: true, trim: true, maxlength: 80 },
  lastName: { type: String, required: true, trim: true, maxlength: 80 },
  email: { type: String, required: true, trim: true, lowercase: true, unique: true, index: true },
  phone: { type: String, required: true, trim: true, maxlength: 24 },
  businessName: { type: String, required: true, trim: true, maxlength: 160 },
  legalEntityType: { type: String, required: true, enum: ['individual', 'commercial_registration', 'limited_partnership', 'limited_company'] },
  vatRegistered: { type: Boolean, required: true },
  businessAge: { type: String, required: true, enum: ['under_6_months', '6_months_to_1_year', '1_to_3_years', '3_to_5_years', 'over_5_years'] },
  ownerAge: { type: String, required: true, enum: ['under_20', '20_to_35', '36_to_50', '51_to_65', 'over_65'] },
  ownerNationality: { type: String, required: true, trim: true, maxlength: 60 },
  industry: { type: String, required: true, trim: true, maxlength: 100 },
  annualRevenueBand: { type: String, required: true, enum: ['up_to_75m', '75m_to_500m', 'over_500m'] },
  minimumCashReserve: { type: Number, required: true, min: 0 },
  monthlyDebtPayment: { type: Number, required: true, min: 0 },
  outstandingDebt: { type: Number, required: true, min: 0 },
  nextPaymentDueDay: { type: Number, required: true, min: 1, max: 31 },
  fixedMonthlyExpenses: { type: Number, required: true, min: 0 },
  financingPurpose: { type: String, required: true, enum: ['working_capital', 'inventory_or_receivables', 'equipment_or_investment', 'business_expansion'] },
  collateralAvailable: { type: Boolean, required: true },
  latePaymentOver90Days: { type: String, required: true, enum: ['no', 'yes', 'prefer_not_to_say'] },
  financialDataConsent: { type: Boolean, required: true, validate: { validator: Boolean, message: 'Financial data consent is required.' } },
}, { timestamps: true, versionKey: false });

export const CustomerProfile = models.CustomerProfile ?? model('CustomerProfile', customerProfileSchema);
