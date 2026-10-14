function Placeholder({ className = "" }: { className?: string }) {
  return (
    <div
      className={`rounded-lg bg-[#e3e9e4] motion-safe:animate-pulse ${className}`}
    />
  );
}

export function WorkspaceSkeleton() {
  return (
    <div
      role="status"
      aria-label="Loading your workspace"
      aria-busy="true"
      className="min-h-screen bg-[#f4f6f7]"
    >
      <span className="sr-only">Loading your workspace</span>
      <div
        aria-hidden="true"
        className="flex min-h-screen flex-col md:flex-row"
      >
        <aside className="flex shrink-0 flex-col gap-5 bg-[#112a27] p-6 md:fixed md:inset-y-0 md:left-0 md:w-[252px]">
          <Placeholder className="h-7 w-40 opacity-25" />
          <div className="flex gap-3 overflow-hidden md:mt-10 md:flex-col">
            {Array.from({ length: 6 }, (_, i) => (
              <Placeholder
                key={i}
                className="h-10 w-28 shrink-0 opacity-15 md:w-full"
              />
            ))}
          </div>
          <Placeholder className="h-11 w-full opacity-15 md:mt-6" />
        </aside>
        <div className="min-w-0 flex-1 px-5 md:ml-[252px] md:px-10">
          <div className="flex h-[83px] items-center justify-between border-b border-[#e4e9e7]">
            <Placeholder className="h-3 w-28" />
            <Placeholder className="h-9 w-32 rounded-full" />
          </div>
          <main className="mx-auto max-w-[1260px] py-8">
            <Placeholder className="h-3 w-36" />
            <Placeholder className="mt-4 h-9 w-3/4 max-w-96" />
            <Placeholder className="mt-3 h-4 w-2/3 max-w-80" />
            <div className="mt-8 rounded-xl border border-[#dbe6d2] bg-[#e7eee0] p-6">
              <Placeholder className="h-3 w-40" />
              <Placeholder className="mt-4 h-7 w-2/3 max-w-80" />
              <Placeholder className="mt-3 h-4 w-4/5" />
              <Placeholder className="mt-5 h-10 w-36" />
            </div>
            <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
              {Array.from({ length: 4 }, (_, i) => (
                <div
                  key={i}
                  className="rounded-xl border border-[#e4e9e7] bg-white p-5"
                >
                  <Placeholder className="h-3 w-4/5" />
                  <Placeholder className="mt-4 h-9 w-12" />
                  <Placeholder className="mt-3 h-3 w-3/4" />
                </div>
              ))}
            </div>
            <div className="mt-6 grid gap-5 lg:grid-cols-2">
              {Array.from({ length: 2 }, (_, i) => (
                <div
                  key={i}
                  className="rounded-xl border border-[#e4e9e7] bg-white p-6"
                >
                  <Placeholder className="h-5 w-36" />
                  {Array.from({ length: 3 }, (_, row) => (
                    <div key={row} className="mt-6 flex items-center gap-4">
                      <Placeholder className="h-9 w-9 shrink-0 rounded-full" />
                      <div className="flex-1">
                        <Placeholder className="h-4 w-3/4" />
                        <Placeholder className="mt-2 h-3 w-1/2" />
                      </div>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
