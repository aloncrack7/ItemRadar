import Link from 'next/link';
import { ItemRadarLogo } from '@/components/icons/item-radar-logo';
import { Button } from '@/components/ui/button';
import { Lightbulb, Search } from 'lucide-react';

export function Header() {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-16 max-w-screen-2xl items-center justify-between">
        <Link href="/" className="flex items-center space-x-2" aria-label="ItemRadar Home">
          <ItemRadarLogo className="h-6 w-auto" />
        </Link>
        <nav className="flex items-center space-x-2">
          <Button variant="ghost" asChild>
            <Link href="/report-lost">
              <Search className="mr-2 h-4 w-4" /> Report Lost
            </Link>
          </Button>
          <Button variant="ghost" asChild>
            <Link href="/report-found">
              <Lightbulb className="mr-2 h-4 w-4" /> Report Found
            </Link>
          </Button>
        </nav>
      </div>
    </header>
  );
}
