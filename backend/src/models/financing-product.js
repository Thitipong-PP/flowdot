import mongoose from 'mongoose';

const { Schema, model, models } = mongoose;

const financingProductSchema = new Schema({
  code: { type: String, required: true, unique: true, trim: true },
  name: { type: String, required: true, trim: true },
  lender: { type: String, required: true, trim: true },
  description: { type: String, default: '' },
  maximumAmount: { type: Number, required: true, min: 0 },
  startingAnnualRate: { type: Number, required: true, min: 0 },
  minBusinessAgeMonths: { type: Number, default: 0, min: 0 },
  acceptedEntityTypes: [{ type: String }],
  acceptedRevenueBands: [{ type: String }],
  requiresVatRegistration: { type: Boolean, default: false },
  requiresCollateral: { type: Boolean, default: false },
  active: { type: Boolean, default: true, index: true },
}, { timestamps: true, versionKey: false });

export const FinancingProduct = models.FinancingProduct ?? model('FinancingProduct', financingProductSchema);
