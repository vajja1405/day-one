# Day One website

[Live site](https://vajja1405.github.io/day-one/) · [Full source](https://github.com/vajja1405/day-one)

An independent synthetic proposal for Clover Health /COMMIT by Rahul Chowdary Vajja.

React + TypeScript with Vite. All displayed data is precomputed and bundled. No runtime model key, clinical backend, or external record connector is used.

```sh
npm ci
npm run dev
npm run build
npm run deploy
```

`npm run build` type-checks and builds to `dist/` with the `/day-one/` base path. `npm run deploy` publishes that directory to the repository's `gh-pages` branch. GitHub Pages is configured to serve that branch's root.

`npm run build:offline` creates `offline-dist/day-one-offline.html`. The original backup remains `../day-one-offline.html` and is included in every normal deployment. Open it directly from your laptop with no network.

Build hooks consolidate `public/data/` into `app/demo-data.json`. The Python pipeline, generator, audit records, 30-case evaluation and tests live at the repository root. Run `make export` there to refresh the site's data, then rebuild here.

Scores are uncalibrated heuristics. The evaluation is synthetic regression coverage, not clinical validation.
