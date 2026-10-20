import mongoose from 'mongoose';

const { Schema, model, models } = mongoose;

const supportTicketSchema = new Schema({
  customerId: { type: Schema.Types.ObjectId, ref: 'CustomerProfile', required: true, index: true },
  subject: { type: String, required: true, trim: true, maxlength: 160 },
  message: { type: String, required: true, trim: true, maxlength: 4000 },
  status: { type: String, enum: ['open', 'in_progress', 'resolved'], default: 'open', index: true },
}, { timestamps: true, versionKey: false });

export const SupportTicket = models.SupportTicket ?? model('SupportTicket', supportTicketSchema);
