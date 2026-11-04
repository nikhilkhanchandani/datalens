# DataLens frontend

The Next.js (App Router, TypeScript, Tailwind, Recharts) UI for DataLens. It only
renders data that the Python API computes; it doesn't calculate statistics itself.

- `npm install`, then `cp .env.example .env.local` (or copy it on Windows).
- `npm run dev` starts the dev server at http://localhost:3000.
- `npm run build` creates a production build. `npm start` serves it.
- `npx tsc --noEmit` and `npm run lint` check types and style.

See the [project README](../README.md) for the full setup, architecture, and API
notes.
