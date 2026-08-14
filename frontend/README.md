# RAG Textbook frontend

The public frontend is a Hugo-generated learning book with two focused sections:

- A 129-concept RAG glossary arranged from foundations through production operations
- Interview Practice with nine interviewer/candidate conversations and a reveal-first practice mode

The site does not require the Python CLI, a model provider, Qdrant, Node.js, React, or React Flow.
Hugo renders the glossary and interview content as static HTML. A small vanilla JavaScript file
provides search, chapter page turning, reading progress, and interview answer reveals.

## Content structure

- `data/glossary.json` — chapter content, citations, learning order, and related concepts
- `data/interviews.json` — interview questions, answers, follow-ups, trade-offs, and sources
- `layouts/` — Hugo templates for the textbook and interview pages
- `assets/css/main.css` — responsive textbook visual system
- `assets/js/book.js` — lightweight client-side chapter and practice interactions
- `static/media/glossary/` — local educational GIFs

## Run locally

```powershell
Set-Location C:\Users\AJay\Documents\ogent\refernce\ocigeniworkshop\prodrag\frontend
$cachePath = Join-Path (Resolve-Path -LiteralPath .).Path ".hugo_cache"
hugo server --cacheDir $cachePath --baseURL http://127.0.0.1:4173/prod_rag/ --appendPort=false
```

Open `http://127.0.0.1:4173/prod_rag/`.

## Production build

```powershell
$cachePath = Join-Path (Resolve-Path -LiteralPath .).Path ".hugo_cache"
hugo --minify --cacheDir $cachePath
```

The static site is written to `dist/` and deployed to GitHub Pages by `.github/workflows/pages.yml`.
