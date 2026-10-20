import { requestLlmCompletion } from '../services/llm-gateway.js';

export async function chat(req, res) {
  const completion = await requestLlmCompletion({
    system: 'You are Flow, a business finance assistant. Give general information, do not claim to approve loans, and encourage users to verify lender terms.',
    messages: [{ role: 'user', content: req.validated.body.message }],
  });
  const text = completion.choices?.[0]?.message?.content ?? completion.output_text ?? completion.message;
  if (typeof text !== 'string') throw new Error('LLM response did not include a text completion.');
  return res.json({ data: { message: text } });
}
