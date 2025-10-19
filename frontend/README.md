# DokTalk Frontend

Next.js 15 frontend for the DokTalk ambient clinical scribe system.

## Setup

### Prerequisites
- Node.js 22.x
- pnpm 9.x

### Installation

```bash
# Install dependencies
pnpm install
```

### Configuration

Environment variables are set in `.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
NEXT_PUBLIC_APP_NAME=DokTalk
```

### Running

```bash
# Development server
pnpm dev

# Build for production
pnpm build

# Start production server
pnpm start
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Testing

```bash
# Run unit tests
pnpm test

# Run tests in watch mode
pnpm test:watch

# Run tests with coverage
pnpm test:coverage

# Run E2E tests
pnpm test:e2e

# Run E2E tests with UI
pnpm test:e2e:ui
```

### Code Quality

```bash
# Lint
pnpm lint

# Format
pnpm format

# Type check
pnpm typecheck
```

## Project Structure

```
frontend/
├── app/              # Next.js 15 App Router
│   ├── layout.tsx    # Root layout
│   ├── page.tsx      # Home page
│   └── globals.css   # Global styles
├── components/       # React components
│   ├── ui/          # shadcn/ui components
│   └── ...          # Feature components
├── lib/             # Utilities and helpers
│   ├── api.ts       # API client
│   ├── utils.ts     # Common utilities
│   └── stores/      # Zustand stores
├── public/          # Static assets
└── styles/          # Additional styles
```

## Tech Stack

- **Framework:** Next.js 15 (App Router, React Server Components)
- **Styling:** Tailwind CSS + shadcn/ui
- **State Management:** Zustand
- **Forms:** React Hook Form + Zod
- **API Client:** Axios + TanStack Query
- **WebRTC:** simple-peer
- **Real-time:** Socket.IO client

## Features

- Server-side rendering (SSR) and incremental static regeneration (ISR)
- WebRTC video conferencing integration
- Real-time collaboration via WebSocket
- Responsive design for tablets and desktops
- Accessibility compliant (WCAG 2.1 AA)
- Russian language support (primary UI language)

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for development guidelines.
