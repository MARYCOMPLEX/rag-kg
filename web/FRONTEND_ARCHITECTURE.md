# Frontend Architecture

This app is being migrated from a high-fidelity Stitch reconstruction into a maintainable Vue frontend that can connect to a backend without rewriting screens.

## Source Of Truth

- Visual fidelity: Stitch exported implementation and the current approved reconstruction.
- Interaction detail: `G:/anyfast/reasearch-front/ui-interaction-spec`.
- Deprecated visual references: local image drafts and old exported screenshots that conflict with Stitch.

## Layering

```text
src/views + src/components
  -> src/stores
  -> src/services/<domain>/*Repository.ts
  -> src/mocks or src/services/api/httpClient.ts
  -> src/domain/<domain>/types.ts
```

The UI should not know whether data came from mock records or an HTTP API. Stores own loading, selected entities, errors, and mutations. Repositories own data transport. Domain files define data contracts.

## Data Source Switching

Local mock mode:

```bash
VITE_DATA_SOURCE=mock
```

Backend mode:

```bash
VITE_DATA_SOURCE=api
VITE_API_BASE_URL=http://localhost:8000
```

Current repository-backed domains:

- Documents: list, details drawer, retry ingestion, upload queue feedback.
- Libraries: list, active library data, create library.

Seed-backed domains with mock boundaries prepared:

- Chat
- Review
- Evaluation
- Knowledge Graph
- Command/search/navigation

Those modules should be migrated to repository-backed stores before real backend integration.

## Styling Contract

`src/styles/design-tokens.css` is the only place for raw design constants. Business components consume variables such as `--color-*`, `--radius-*`, `--shadow-*`, `--z-*`, and `--motion-*`.

`src/styles/prototype.css` is retained only as a compatibility layer for existing Stitch-derived class names. New business styling belongs in base components, feature components, or page-scoped styles using tokens.

## Component Contract

Shared primitives live in `src/components/base/`. A new modal, drawer, dropdown, selector, icon button, field, status pill, or repeated interactive primitive should be implemented there first, then consumed by pages.

Shell components live in `src/components/layout/`. The sidebar, topbar, route frame, and content width rules must remain consistent across pages. Special pages can request layout options, but should not replace the shell.

## Migration Notes

The old `prototypeApi`, `types/prototype`, `usePrototypeNavigation`, and `prototype-*` store IDs have been removed from application code. Mock data now lives under `src/mocks/`, with API-ready repository seams for Documents and Libraries.
