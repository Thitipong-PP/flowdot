import mongoose from 'mongoose';

const { Schema, model, models } = mongoose;

const userAccountSchema = new Schema({
  email: { type: String, required: true, unique: true, lowercase: true, trim: true, index: true },
  passwordHash: { type: String, required: true, select: false },
  customerId: { type: Schema.Types.ObjectId, ref: 'CustomerProfile', default: null, index: true },
  role: { type: String, enum: ['customer', 'admin'], default: 'customer', required: true },
  active: { type: Boolean, default: true, required: true },
  sessionVersion: { type: Number, default: 0, required: true },
  lastLoginAt: { type: Date, default: null },
}, { timestamps: true, versionKey: false });

export const UserAccount = models.UserAccount ?? model('UserAccount', userAccountSchema);
