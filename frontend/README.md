# Frontend

Next.js 14 App Router dashboard for OSymandias.

## Stack

| | |
|-|-|
| Framework | Next.js 14 (App Router) |
| Data fetching | TanStack Query v5 |
| Styling | Tailwind CSS + custom design tokens |
| Icons | Lucide React |
| Graph | ReactFlow (call graph view) |

## Structure

```
frontend/src/
├── app/
│   ├── layout.tsx           # Root layout: fonts, Sidebar, QueryProvider
│   ├── globals.css          # Design tokens + utility classes
│   ├── page.tsx             # Dashboard
│   ├── jobs/                # Process list + detail view
│   ├── agents/              # Agent registry
│   ├── tools/               # Syscall registry
│   ├── memory/              # Memory explorer
│   ├── events/              # Event stream
│   └── metrics/             # Aggregated metrics
├── components/
│   ├── Sidebar.tsx
│   ├── jobs/JobStatusBadge.tsx
│   └── execution/
│       ├── ExecutionTimeline.tsx
│       └── AgentGraph.tsx
├── hooks/
│   ├── useJobData.ts        # TanStack Query hooks
│   └── useJobStream.ts      # SSE (EventSource) hook
├── lib/
│   ├── api.ts               # Typed API client
│   └── utils.ts             # formatTokens, formatCost, formatDuration
└── types/index.ts           # TypeScript interfaces
```

## Development

```bash
npm install
npm run dev    # http://localhost:3000
```

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Each route has a `loading.tsx` — Next.js shows it instantly on navigation, eliminating the perceived click delay before data loads.
