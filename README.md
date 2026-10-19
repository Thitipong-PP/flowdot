# Flow — SME Finance Copilot demo

An interactive Next.js demo based on the supplied AI architecture and screen design files.

## Run locally

```bash
pnpm install
pnpm dev
```

Open `http://localhost:3000`.

## Structure

- `src/app/` contains the App Router entry point, shared metadata, and global design tokens/styles.
- `src/components/copilot-demo.tsx` contains the interactive demo island and its screen-level flows.
- The route itself is a Server Component. Interactive state is isolated behind the client component boundary.

## Demo behavior

User and Admin views use local sample data. The receipt upload, OCR result, agent trace, agent health, issue queue, and account forms are UI simulations; they are not connected to LINE, a database, OCR, an LLM, or a real authentication service.

The registration form uses the fields explicitly present in `design_template.txt` plus basic business profile fields (business name, monthly revenue, and years in business) because the referenced REF1 fields were not included in the supplied design files.
