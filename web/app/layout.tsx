import type { Metadata } from "next";
import { Geist, Source_Serif_4 } from "next/font/google";
import Link from "next/link";

import { Logo } from "@/components/Logo";
import { SignOutButton } from "@/components/SignOutButton";
import { getMe } from "@/lib/api";

import "./globals.css";

const sans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const serif = Source_Serif_4({ variable: "--font-serif-display", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "Their Take", template: "%s · Their Take" },
  description: "What people think, with sources.",
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const me = await getMe().catch(() => null);
  return (
    <html lang="en" className={`${sans.variable} ${serif.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans">
        <header className="border-b border-border">
          <nav className="mx-auto flex max-w-3xl items-center gap-5 px-4 py-4 text-sm">
            <Link
              href="/"
              className="mr-auto flex items-center gap-2 font-serif text-xl font-semibold tracking-tight"
            >
              <Logo />
              Their Take
            </Link>
            <Link href="/people" className="text-muted hover:text-fg">
              People
            </Link>
            <Link href="/search" className="text-muted hover:text-fg">
              Search
            </Link>
            {me?.is_admin && (
              <Link href="/admin" className="text-muted hover:text-fg">
                Admin
              </Link>
            )}
            {me ? (
              <SignOutButton />
            ) : (
              <Link href="/login" className="rounded-md bg-fg px-3 py-1.5 text-bg hover:opacity-90">
                Sign in
              </Link>
            )}
          </nav>
        </header>
        <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
