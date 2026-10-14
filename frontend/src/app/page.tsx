import Link from "next/link";
export default function LandingPage() {
  return (
    <div className="shell welcome-shell">
      <header>
        <Link className="brand" href="/">
          Stride
        </Link>
        <Link href="/login">Sign in</Link>
      </header>
      <main>
        <div className="intro">
          <span className="eyebrow">YOUR NEXT STEP STARTS HERE</span>
          <h1>
            Make learning
            <br />
            <em>move you forward.</em>
          </h1>
          <p>
            Turn your materials into focused study, scenario practice, and
            useful explanations.
          </p>
          <div className="mt-8 flex flex-wrap gap-4">
            <Link
              className="rounded-lg bg-[#183832] px-6 py-4 text-white"
              href="/login"
            >
              Start learning
            </Link>
            <Link
              className="rounded-lg border border-[#dce3d9] px-6 py-4"
              href="/dashboard"
            >
              Open dashboard
            </Link>
          </div>
        </div>
        <section className="goal-grid">
          {[
            "Prepare for exams",
            "Practise for interviews",
            "Explore a new field",
          ].map((title) => (
            <article className="goal-card" key={title}>
              <h2>{title}</h2>
              <p>
                Focused guides, feedback on your answers, and a clear next step.
              </p>
            </article>
          ))}
        </section>
      </main>
    </div>
  );
}
