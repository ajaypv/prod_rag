# Groundwork frontend

Groundwork is a beginner-first RAG learning guide and interview-preparation experience. It uses a
structured curriculum, plain-language explanations, focused animated diagrams, technical details,
and short interview answers to teach the complete retrieval-augmented generation flow without
assuming prior knowledge.

The frontend is a standalone React application. It does not require the Python CLI, a model
provider, or Qdrant because the lessons are explanatory rather than connected to live production
data. Examples are provider-neutral so learners can apply the concepts to different model and
vector-database stacks.

## Learning experience

- Start Here page that explains RAG as **find, select, answer**
- React Flow hero playground with functional retrieval controls and a live high-DPI evidence canvas
- Nine lessons ordered from fundamentals through production readiness
- Interactive React Flow diagrams with an automatically guided stage explanation
- Optional technical detail sections so the first view stays approachable
- Scroll-triggered interviewer/candidate conversations with live question progress
- Watch mode, answer-first practice mode, deep-dive follow-ups, and copy controls
- Simple glossary cards that open source-backed newspaper chapters with local educational GIFs
- Numbered links to primary research and official technical documentation
- Progress saved locally in the browser
- Responsive sidebar on desktop and a curriculum drawer on mobile

## Run locally

```powershell
Set-Location C:\Users\AJay\Documents\ogent\refernce\ocigeniworkshop\prodrag\frontend
pnpm install
pnpm dev
```

Open `http://127.0.0.1:4173`.

## Production build

```powershell
pnpm build
pnpm preview
```

The optimized static site is written to `dist/`. The project-local `.npmrc` intentionally points
pnpm at the official npm registry, overriding any inherited corporate registry configuration.
