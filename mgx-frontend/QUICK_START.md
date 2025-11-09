# Quick Start Guide

## Setup Commands

```bash
# 1. Install dependencies
npm install

# 2. Install TailwindCSS dependencies (if not already installed)
npm install -D tailwindcss postcss autoprefixer

# 3. Install shadcn/ui dependencies
npm install tailwindcss-animate class-variance-authority clsx tailwind-merge lucide-react

# 4. Initialize shadcn/ui components
npx shadcn@latest add button card badge input label textarea

# 5. Create .env file
echo "VITE_API_URL=http://localhost:8000" > .env

# 6. Start development server
npm run dev
```

## Key Files Created

### Configuration
- `vite.config.ts` - Vite config with path aliases
- `tailwind.config.js` - TailwindCSS config
- `tsconfig.app.json` - TypeScript config with path aliases
- `components.json` - shadcn/ui config
- `.env` - Environment variables

### Source Files
- `src/api/client.ts` - Axios HTTP client
- `src/api/websocket.ts` - WebSocket client
- `src/store/taskStore.ts` - Zustand state management
- `src/types/task.ts` - TypeScript types
- `src/components/Header.tsx` - App header
- `src/components/TaskCard.tsx` - Task card component
- `src/components/EventStream.tsx` - Real-time event stream
- `src/pages/Home.tsx` - Task list page
- `src/pages/TaskDetail.tsx` - Task detail page
- `src/App.tsx` - Main app component

## Running the App

1. **Start Backend** (in another terminal):
   ```bash
   cd backend
   python3 -m uvicorn app.main:app --reload
   ```

2. **Start Frontend**:
   ```bash
   cd mgx-frontend
   npm run dev
   ```

3. **Open Browser**: http://localhost:5173

## Troubleshooting

### Components Not Found
If you see errors about missing UI components:
```bash
npx shadcn@latest add [component-name] --overwrite
```

### TypeScript Errors
Make sure all dependencies are installed:
```bash
npm install
```

### WebSocket Connection Failed
1. Check backend is running on port 8000
2. Verify `VITE_API_URL` in `.env`
3. Check browser console for errors

