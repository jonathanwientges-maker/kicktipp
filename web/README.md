# Bundesliga Hub — website

German-language, statically-exported Next.js site built from the JSON that
`python -m src.export_web` writes into `web/public/data/`. Installable as a
PWA; opens offline.

## Local development

```bash
cd web
npm install
npm run dev        # http://localhost:3000
```

The pages read `web/public/data/**` off the filesystem at build time.
Regenerate that tree from the repo root with:

```bash
python -m src.export_web
```

## Production build

```bash
npm run build      # runs `next build` then scripts/gen-sw.mjs
```

Output is a fully static site in `web/out/`. `scripts/gen-sw.mjs` stamps
the service worker's `CACHE_VERSION` from `manifest.json`'s `generated_at`
so each weekly deploy invalidates the previous offline cache. The source
`public/sw.js` keeps the `__CACHE_VERSION__` placeholder in git.

## Vercel setup

| Setting | Value |
|---|---|
| Root Directory | `web` |
| Framework Preset | Next.js |
| Build Command | `npm run build` |
| Output Directory | `out` |
| Install Command | `npm install` |

### Ignored Build Step

Set the project's *Ignored Build Step* command to:

```
git diff --quiet HEAD^ HEAD -- web/
```

so the Friday and Tuesday prediction commits (which never touch `web/`) do
not trigger a rebuild. The single weekly deploy comes from the
`results_refresh` workflow, which commits `data/` and `web/public/data/`
together in one commit after the completed matchday's results are scored.

## Data provenance

Understat (xG, shots, rosters), football-data.co.uk (kickoff times). No
forward-looking model output, probabilities or odds are ever published;
the only forward-looking artefact is the season simulation, derived from
Dixon-Coles ratings alone.
