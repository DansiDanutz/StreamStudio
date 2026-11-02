# StreamStudio web

## Overview
The StreamStudio editor, Program window and render view: a React 19 + Vite + TypeScript app with zustand stores. All source lives in `src/`; this folder holds the build and test configuration. The repo's `../assets` folder is served at the web root in development (`vite.config.ts:publicDir`) and by FastAPI in production.

## Subdirectories & Boundaries
- src: [./src/README.md](./src/README.md) - app entry, the editor and its subsystems (stage, director, agent, avatar, library, output, overlays, publish).

## Interface
- `package.json` scripts: `dev` (vite), `build` (`tsc -b && vite build`), `lint` (`oxlint`), `preview`.
- `vite.config.ts`: `publicDir` = `../assets`; dev server on port 5173 proxying `/api` (including WebSockets) to `http://127.0.0.1:8787`; build to `dist` with `emptyOutDir`.
- `vitest.config.ts`: merges the Vite config with `environment: 'jsdom'` and `globals: true`.
- `index.html`: mounts `/src/main.tsx` into `#root`; loads Manrope, Instrument Serif, JetBrains Mono and Caveat from Google Fonts.

## Invariants
- Static assets referenced as `/studio/...`, `/avatar/...`, `/objects/...`, `/brand/...` resolve to `../assets` in development (`vite.config.ts:publicDir`).
- Files matching `*.test.ts` / `*.test.tsx` are vitest tests and are not part of the shipped app.

## Side Effects
- The dev server proxies `/api` to the local API (`vite.config.ts:server.proxy`); `npm run build` writes `web/dist`.

## Verification
- Run: `cd web && npx vitest run`
- Lint and typecheck: `cd web && npx tsc -b && npx oxlint`
- Repo-wide: `make test` (from the repository root).

## Developer notes (Vite template)

This project started from the React + TypeScript + Vite template, which provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

### React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

### Expanding the Oxlint configuration

If you are developing a production application, we recommend enabling type-aware lint rules by installing `oxlint-tsgolint` and editing `.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "options": {
    "typeAware": true
  },
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

See the [Oxlint rules documentation](https://oxc.rs/docs/guide/usage/linter/rules) for the full list of rules and categories.
