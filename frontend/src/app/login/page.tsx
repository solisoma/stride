"use client";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AccountForm } from "@/components/account-form";
export default function LoginPage() {
  const router = useRouter();
  return (
    <div className="shell welcome-shell">
      <header>
        <Link className="brand" href="/">
          Stride
        </Link>
      </header>
      <main>
        <AccountForm
          onAccount={async () => {
            const next = new URLSearchParams(window.location.search).get(
              "next",
            );
            router.replace(
              next && /^\/dashboard(?:\/|$)/.test(next) ? next : "/dashboard",
            );
          }}
        />
      </main>
    </div>
  );
}
