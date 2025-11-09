# MGX Frontend Setup Guide

## Prerequisites

- Node.js 18+ and npm
- Backend API running on `http://localhost:8000`

## Quick Start

### 1. Install Dependencies

```bash
cd mgx-frontend
npm install
```

### 2. Configure Environment

Create a `.env` file:

```bash
cp .env.example .env
```

Edit `.env` and set:
```
VITE_API_URL=http://localhost:8000
```

### 3. Run Development Server

```bash
npm run dev
```

The app will be available at `http://localhost:5173` (or the port Vite assigns).

## Project Structure

```
mgx-frontend/
├── src/
│   ├── api/
│   │   ├── client.ts          # Axios HTTP client
│   │   └── websocket.ts       # WebSocket client
│   ├── components/
│   │   ├── Header.tsx         # App header
│   │   ├── TaskCard.tsx       # Task card component
│   │   ├── EventStream.tsx    # Real-time event stream
│   │   └── ui/                # shadcn/ui components
│   ├── pages/
│   │   ├── Home.tsx           # Task list page
│   │   └── TaskDetail.tsx     # Task detail page
│   ├── store/
│   │   └── taskStore.ts       # Zustand state management
│   ├── types/
│   │   └── task.ts            # TypeScript types
│   ├── lib/
│   │   └── utils.ts           # Utility functions
│   ├── App.tsx                # Main app component
│   └── main.tsx               # Entry point
├── .env                       # Environment variables
├── tailwind.config.js         # TailwindCSS config
├── vite.config.ts             # Vite config
└── tsconfig.json              # TypeScript config
```

## Configuration Files

### `vite.config.ts`
- Configures Vite with React plugin
- Sets up path alias `@/` → `src/`

### `tailwind.config.js`
- TailwindCSS configuration
- Includes shadcn/ui theme variables
- Dark mode support

### `tsconfig.app.json`
- TypeScript configuration
- Path aliases for `@/` imports

### `components.json`
- shadcn/ui configuration
- Component aliases and paths

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

## Adding shadcn/ui Components

To add more shadcn/ui components:

```bash
npx shadcn@latest add [component-name]
```

Example:
```bash
npx shadcn@latest add dialog dropdown-menu
```

## Features

### ✅ Implemented

- Task creation and listing
- Task detail view
- Real-time WebSocket event streaming
- Task status monitoring
- Responsive design
- Modern UI with shadcn/ui

### 🔄 State Management

Uses Zustand for state management:
- `useTaskStore` - Manages tasks, events, and task state
- Automatic WebSocket connection on task detail page
- Real-time event updates

### 🌐 API Integration

- REST API via Axios (`src/api/client.ts`)
- WebSocket client (`src/api/websocket.ts`)
- Automatic reconnection on disconnect

## Troubleshooting

### Port Already in Use

If port 5173 is in use, Vite will automatically use the next available port.

### WebSocket Connection Failed

1. Check that backend is running on `http://localhost:8000`
2. Verify `VITE_API_URL` in `.env` matches backend URL
3. Check browser console for WebSocket errors

### TypeScript Errors

If you see TypeScript errors:
1. Run `npm install` to ensure all dependencies are installed
2. Check `tsconfig.app.json` has correct path aliases
3. Restart your IDE/editor

### Build Errors

If build fails:
1. Clear `node_modules` and reinstall: `rm -rf node_modules && npm install`
2. Check for missing dependencies
3. Verify all imports use correct path aliases (`@/`)

## Next Steps

1. **Start Backend**: Make sure the backend API is running
2. **Create Tasks**: Use the "Create New Task" button
3. **Monitor Execution**: View task details to see real-time events
4. **Customize**: Add more components and features as needed

## Development Tips

- Use React DevTools for debugging
- Check Network tab for API calls
- Monitor WebSocket messages in browser console
- Use TailwindCSS classes for styling
- Follow shadcn/ui patterns for new components

