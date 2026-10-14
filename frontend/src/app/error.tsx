"use client";
import { useEffect } from 'react';
import { logger } from '@/utils/logger';
export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => { logger.error('render_error', { errorType: error.name, digest: error.digest }); }, [error]);
  return <main className="mx-auto max-w-xl p-8"><h1 className="text-2xl font-semibold">This page could not load.</h1><p className="my-4">Please try again. If the problem continues, share the reference below when asking for help.{error.digest ? ` Reference: ${error.digest}` : ''}</p><button onClick={reset}>Try again</button></main>;
}
