# CIIS investigator frontend

React, TypeScript and Vite interface for case intake, evidence review,
investigation artifacts, timeline exploration and report downloads.

## Development

From the repository root, the supported entry point is:

```bash
./dev.sh up
./dev.sh test
```

For frontend-only work:

```bash
cd ciis_frontend
npm install
npm run dev
npm run typecheck
npm test
npm run build
```

## Relationship graph

The backend stores one complete `RelationshipGraph` artifact. Frontend code
under `src/features/graph/` derives presentation-only views; it never changes
backend findings or the stored JSON.

### Views

| View | Purpose |
|---|---|
| Evidence map | Default overview. One node per evidence item and one aggregated edge per related evidence pair. |
| Entity map | Evidence-to-entity detail, ranked by evidence reach and threat/cross-case significance. |
| Cross-case | Other cases, matching entities and their source evidence. |
| Threats | Threat-intelligence relationships and contextual evidence. |
| Full graph | Complete technical graph, including single-mention detail. |

An Evidence map edge retains frontend metadata identifying every source edge,
relationship type and shared entity. Selecting it opens the details panel;
**Reveal shared entities** expands only that evidence pair. The original graph
artifact remains untouched.

### Search and filters

- Search scans node IDs, labels and properties across the complete artifact and
  reveals matches with one contextual hop.
- Confidence thresholds support all, 50%+ and 75%+ relationships.
- Timestamp provenance filters distinguish actual, inferred and unresolved
  timestamps.
- Node-type and relationship-type chips can be independently toggled.
- Upload-time fallback relationships are hidden by default because a common
  upload batch describes investigator workflow, not necessarily criminal activity.

Quick views reset conflicting filters and configure the graph for overview,
strong leads, cross-case indicators, threat hits, cryptocurrency trails or
actual-time relationships.

### Performance and state

- Investigation, Graph, Timeline, Analytics and Reports are separate lazy
  chunks and download only when their tab is first opened. Overview and
  Evidence remain in the initial case bundle for immediate case navigation.
- Evidence projection prevents a shared entity from producing a large visible
  bipartite graph in the default view.
- Overview and focused-neighbourhood budgets prevent unreadable canvases.
- Cytoscape elements are diffed and updated in place instead of recreating the
  renderer for every filter or expansion.
- Labels are progressively disclosed through importance, hover and zoom.
- View, layout, filters, expanded evidence pairs, focus, zoom and pan are saved
  per case in browser local storage.

### Important files

| File | Responsibility |
|---|---|
| `src/features/graph/GraphTab.tsx` | Investigator controls, modes, filters and details panel |
| `src/features/graph/GraphCanvas.tsx` | Cytoscape rendering, incremental updates and interactions |
| `src/features/graph/relevance.ts` | Entity relevance, confidence and neighbourhood selection |
| `src/features/graph/views.ts` | Evidence projection, special views, search and relationship filtering |
| `src/features/graph/__tests__/` | Relevance and projection regression tests |

The current backend graph implementation is pure Python and does not require
NetworkX. Cytoscape.js is responsible only for the interactive browser view.
