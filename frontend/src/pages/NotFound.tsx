import type { ReactElement } from 'react';

import { Button } from '../components/ui/button';

/**
 * The 404 page the catch-all route renders. A module of its own so the route
 * can be lazy loaded and boundary wrapped like every other page.
 */
function NotFound(): ReactElement {
  return (
    <div className="container mx-auto px-4 py-20 text-center">
      <div className="border border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5 rounded-2xl p-12 max-w-md mx-auto animate-fadeInScale">
        <h1 className="text-4xl font-bold text-gradient mb-4">404</h1>
        <p className="text-muted-foreground mb-6">Page not found</p>
        <Button asChild>
          <a href="/">Go Home</a>
        </Button>
      </div>
    </div>
  );
}

export default NotFound;
