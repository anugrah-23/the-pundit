import type { Metadata } from "next";
import "./globals.css";
import Header from "@/components/Header";

export const metadata: Metadata = {
  title: "The Pundit",
  description:
    "An AI football analyst for the Top 5 leagues that answers from real stats, with a semantic cache, an LLM judge and prompt-injection guardrails you can test yourself.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Big+Shoulders+Display:wght@700;800&display=swap"
        />
      </head>
      <body>
        <Header />
        <main>
          <div className="wrap">{children}</div>
        </main>
        <footer className="site-footer">
          <div className="wrap">
            Stats from Understat, refreshed weekly. Built by Anugrah Chari V. The fan-blog posts and admin key in Break the
            Pundit are fake and exist only for testing.
          </div>
        </footer>
      </body>
    </html>
  );
}
