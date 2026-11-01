"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const LINKS = [
  { href: "/", label: "Ask" },
  { href: "/debate", label: "Debate" },
  { href: "/break", label: "Break the Pundit" },
  { href: "/numbers", label: "Numbers" },
];

export default function Header() {
  const path = usePathname();
  const [demo, setDemo] = useState(false);

  useEffect(() => {
    api<{ data_version: string }>("/api/health")
      .then((h) => setDemo(h.data_version.startsWith("demo")))
      .catch(() => {});
  }, []);

  return (
    <>
      {demo && (
        <div className="demo-banner" role="status">
          <div className="wrap">Demo data: these clubs and players are invented. Real stats load after the first data refresh.</div>
        </div>
      )}
      <header className="site-header">
        <div className="wrap">
          <Link href="/" className="wordmark">The Pundit</Link>
          <nav className="nav" aria-label="Modes">
            {LINKS.map((l) => (
              <Link key={l.href} href={l.href} aria-current={path === l.href ? "page" : undefined}>
                {l.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>
    </>
  );
}
