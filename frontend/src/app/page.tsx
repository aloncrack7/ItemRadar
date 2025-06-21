import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Search, Lightbulb, ArrowRight, MessageCircle } from 'lucide-react';
import Image from 'next/image';
import { ItemRadarLogo } from '@/components/icons/item-radar-logo';

export default function HomePage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-8rem)] p-4 sm:p-6 md:p-8">
      <div className="text-center mb-12">
        <ItemRadarLogo className="h-12 w-auto mx-auto mb-4 text-primary" />
        <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold tracking-tight text-primary">
          Welcome to ItemRadar
        </h1>
        <p className="mt-4 max-w-xl mx-auto text-lg text-foreground">
          The easiest way to report lost & found items. Let our AI assistant help you.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 sm:gap-8 w-full max-w-2xl">
        <Card className="hover:shadow-lg transition-shadow">
          <CardHeader className="items-center">
            <Search className="h-10 w-10 text-primary mb-3" />
            <CardTitle className="text-2xl font-semibold">Lost an Item?</CardTitle>
            <CardDescription className="text-center">
              Chat with our AI assistant to report your lost item quickly.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex justify-center">
            <Button asChild size="lg" className="w-full sm:w-auto bg-primary hover:bg-primary/90 text-primary-foreground">
              <Link href="/chat/lost">
                <MessageCircle className="mr-2 h-5 w-5" /> Start Lost Item Report
              </Link>
            </Button>
          </CardContent>
        </Card>

        <Card className="hover:shadow-lg transition-shadow">
          <CardHeader className="items-center">
            <Lightbulb className="h-10 w-10 text-accent mb-3" />
            <CardTitle className="text-2xl font-semibold">Found an Item?</CardTitle>
            <CardDescription className="text-center">
             Chat with our AI assistant to report an item you've found.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex justify-center">
            <Button asChild size="lg" className="w-full sm:w-auto bg-accent hover:bg-accent/90 text-accent-foreground">
              <Link href="/chat/found">
                <MessageCircle className="mr-2 h-5 w-5" /> Start Found Item Report
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>
       <section className="mt-16 w-full max-w-3xl text-center">
        <h2 className="text-2xl font-semibold text-primary mb-6">How It Works</h2>
        <div className="grid sm:grid-cols-3 gap-6 text-sm">
          <div className="flex flex-col items-center p-4 bg-card rounded-lg shadow">
            <MessageCircle className="h-8 w-8 text-primary mb-2" />
            <h3 className="font-semibold mb-1">1. Start Chat</h3>
            <p className="text-muted-foreground">Choose whether you lost or found an item to begin a chat session.</p>
          </div>
          <div className="flex flex-col items-center p-4 bg-card rounded-lg shadow">
             <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-primary mb-2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg>
            <h3 className="font-semibold mb-1">2. Provide Details</h3>
            <p className="text-muted-foreground">Answer questions from our AI assistant and upload photos if helpful.</p>
          </div>
          <div className="flex flex-col items-center p-4 bg-card rounded-lg shadow">
            <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-primary mb-2"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
            <h3 className="font-semibold mb-1">3. Get Matched</h3>
            <p className="text-muted-foreground">We'll process your report and notify you of any potential matches.</p>
          </div>
        </div>
      </section>
    </div>
  );
}
