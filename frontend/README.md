# Frontend

Next.js 14 static dashboard for OSymandias. Built as a static export (`output: "export"`) — served by nginx in Docker when running via `osy serve`, or locally with `npm run dev`.

## Stack

| | |
|-|-|
| Framework | Next.js 14 (App Router, static export) |
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
│   ├── jobs/                # Job list + detail view
│   │   └── [id]/
│   │       ├── page.tsx         # generateStaticParams (server)
│   │       └── JobDetailClient.tsx  # Full detail UI (client)
│   ├── agents/              # Agent registry + builder
│   ├── tools/               # Tool registry
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
│   └── useJobStream.ts      # SSE (EventSource) hook — base URL: 47760
├── lib/
│   ├── api.ts               # Typed API client (default base: localhost:47760)
│   └── utils.ts             # formatTokens, formatCost, formatDuration
└── types/index.ts           # TypeScript interfaces
```

## Development

```bash
npm install
npm run dev    # http://localhost:3000 — hot reload, proxies API manually
```

Set `NEXT_PUBLIC_API_URL` to point at the running FastAPI instance:

```env
NEXT_PUBLIC_API_URL=http://localhost:47760
```

If the variable is not set, `api.ts` defaults to `http://localhost:47760`.

## Production build

```bash
npm run build   # outputs to frontend/out/
```

`osy serve` picks up `frontend/out/` automatically and mounts it into nginx (port 47759).
