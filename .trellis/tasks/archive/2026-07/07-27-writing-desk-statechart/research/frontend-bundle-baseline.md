# Frontend Bundle Baseline

Recorded: 2026-07-31

Command:

```text
cd frontend
npm run build
```

Environment:

```text
node v24.15.0
npm 11.12.1
vite 7.1.9
```

Budget output before adding XState or Playwright:

```text
JS total gzip: 436.34 KB / 480 KB
CSS total gzip: 86.77 KB / 90 KB
WritingDesk route chunk gzip: 49.86 KB
```

The build passed the existing hard budgets. It emitted the existing warnings for JS
total gzip above 430 KB and the main CSS asset above 24 KB. Final comparison must use
the same `npm run build` command and keep the existing hard budgets unchanged.

## Final Statechart Build

Recorded: 2026-07-31

```text
JS total gzip: 446.93 KB / 480 KB  (+10.59 KB)
CSS total gzip: 85.19 KB / 90 KB   (-1.58 KB)
WritingDesk route chunk gzip: 49.37 KB (-0.49 KB)
```

The production build and the unchanged hard budgets passed. The existing JS-total and
single-CSS-file warning thresholds still emit warnings. The lazy WritingDesk route chunk
did not grow, and the Playwright development dependency is absent from the production graph.
