import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';

export function Header() {
  return (
    <header className="border-b bg-background">
      <div className="container mx-auto px-4 py-4 flex items-center justify-between">
        <Link to="/" className="text-2xl font-bold">
          MGX Engine
        </Link>
        <nav className="flex gap-4">
          <Button variant="ghost" asChild>
            <Link to="/">Home</Link>
          </Button>
        </nav>
      </div>
    </header>
  );
}

