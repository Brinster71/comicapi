export default function CuttingEdgeGenericWebpageDesign() {
  const lorem = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Integer posuere erat a ante venenatis dapibus posuere velit aliquet.";

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(250,204,21,0.35),transparent_26%),radial-gradient(circle_at_bottom_right,rgba(251,191,36,0.28),transparent_30%),radial-gradient(circle_at_80%_20%,rgba(253,224,71,0.22),transparent_22%),linear-gradient(180deg,#fff8db_0%,#fff1a8_52%,#ffe082_100%)] text-amber-950 overflow-hidden">
      <div className="absolute inset-0 pointer-events-none opacity-60">
        <div className="absolute -top-20 left-1/3 h-72 w-72 rounded-full bg-yellow-300/70 blur-3xl" />
        <div className="absolute top-1/3 -left-10 h-64 w-64 rounded-full bg-orange-200/70 blur-3xl" />
        <div className="absolute bottom-0 right-0 h-80 w-80 rounded-full bg-amber-300/60 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-7xl px-6 py-8 lg:px-10">
        <header className="mb-10 flex items-center justify-between rounded-full border border-amber-900/10 bg-white/45 px-5 py-3 backdrop-blur-xl shadow-2xl shadow-amber-900/10">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-amber-950 text-yellow-200 font-black">◈</div>
            <div>
              <div className="text-sm uppercase tracking-[0.25em] text-amber-900/50">Prototype</div>
              <div className="text-base font-semibold">Abstract Interface</div>
            </div>
          </div>
          <nav className="hidden md:flex items-center gap-8 text-sm text-amber-900/65">
            <a href="#" className="transition hover:text-amber-950">Overview</a>
            <a href="#" className="transition hover:text-amber-950">Modules</a>
            <a href="#" className="transition hover:text-amber-950">Signals</a>
            <a href="#" className="transition hover:text-amber-950">Contact</a>
          </nav>
          <button className="rounded-full border border-amber-900/10 bg-white/55 px-4 py-2 text-sm font-medium backdrop-blur transition hover:bg-white/75">
            Action
          </button>
        </header>

        <main className="grid gap-8 lg:grid-cols-[1.15fr_0.85fr]">
          <section className="rounded-[2rem] border border-amber-900/10 bg-white/35 p-8 backdrop-blur-2xl shadow-2xl shadow-amber-900/10">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-amber-700/15 bg-yellow-100/80 px-4 py-2 text-xs uppercase tracking-[0.3em] text-amber-900/75">
              Experimental Layout
            </div>
            <h1 className="max-w-3xl text-5xl font-black leading-[0.95] tracking-tight sm:text-6xl lg:text-7xl">
              A bright, playful shell for <span className="bg-gradient-to-r from-amber-500 via-yellow-500 to-orange-400 bg-clip-text text-transparent">undefined content</span>
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-amber-950/70">
              {lorem} Sed posuere consectetur est at lobortis. Donec id elit non mi porta gravida at eget metus.
            </p>
          </section>
        </main>
      </div>
    </div>
  );
}
