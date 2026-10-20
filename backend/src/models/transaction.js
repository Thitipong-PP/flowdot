import mongoose from 'mongoose';

const { Schema, model, models } = mongoose;
const transactionSchema = new Schema({
  customerId: { type: Schema.Types.ObjectId, ref: 'CustomerProfile', required: true, index: true },
  type: { type: String, enum: ['income', 'expense'], required: true },
  description: { type: String, required: true, trim: true, maxlength: 160 },
  category: { type: String, required: true, trim: true, maxlength: 80 },
  amount: { type: Number, required: true, min: 0.01 },
  occurredAt: { type: Date, required: true },
  source: { type: String, enum: ['manual', 'receipt'], default: 'manual', required: true },
}, { timestamps: true, versionKey: false });

export const Transaction = models.Transaction ?? model('Transaction', transactionSchema);
