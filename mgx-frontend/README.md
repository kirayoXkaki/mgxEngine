# MGX Frontend

A React + TypeScript + Vite frontend for the MGX Engine multi-agent system.

## Tech Stack

- **React 19** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **TailwindCSS** - Utility-first CSS
- **shadcn/ui** - Component library
- **Zustand** - State management
- **React Router** - Routing
- **Axios** - HTTP client

## Project Structure

```
src/
  api/
    client.ts          # Axios configuration
    websocket.ts       # WebSocket client
  components/
    Header.tsx         # App header
    TaskCard.tsx       # Task card component
    EventStream.tsx    # Real-time event stream
    ui/                # shadcn/ui components
  pages/
    Home.tsx           # Task list page
    TaskDetail.tsx     # Task detail page
  store/
    taskStore.ts      # Zustand store
  types/
    task.ts           # TypeScript types
  lib/
    utils.ts          # Utility functions
  App.tsx             # Main app component
  main.tsx            # Entry point
```

## Setup

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env and set VITE_API_URL
   ```

3. **Run development server:**
   ```bash
   npm run dev
   ```

4. **Build for production:**
   ```bash
   npm run build
   ```

5. **Preview production build:**
   ```bash
   npm run preview
   ```

## Environment Variables

- `VITE_API_URL` - Backend API URL (default: `http://localhost:8000`)

## Features

- ✅ Task creation and management
- ✅ Real-time event streaming via WebSocket
- ✅ Task status monitoring
- ✅ Agent execution tracking
- ✅ Responsive design with TailwindCSS
- ✅ Modern UI with shadcn/ui components

## Development

### Adding shadcn/ui Components

```bash
npx shadcn@latest add [component-name]
```

### Path Aliases

The project uses `@/` as an alias for `src/`:

```typescript
import { Button } from '@/components/ui/button';
import { useTaskStore } from '@/store/taskStore';
```

## Backend Integration

Make sure the backend is running on `http://localhost:8000` (or update `VITE_API_URL`).

The frontend connects to:
- REST API: `GET/POST /api/tasks`
- WebSocket: `ws://localhost:8000/ws/tasks/{task_id}`

## License

MIT
