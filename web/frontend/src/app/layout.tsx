/**
 * Root layout for the Next.js application.
 *
 * NEXT.JS CONCEPT — Layout:
 * This file wraps EVERY page in the app. It's like a base template
 * in Django/Jinja2. The `{children}` prop receives the page content.
 * Layouts persist across page navigations (they don't re-mount),
 * making them ideal for persistent UI like headers, sidebars, and providers.
 *
 * NEXT.JS CONCEPT — Server vs Client Components:
 * This layout is a SERVER component (no "use client" directive).
 * It renders on the server and sends HTML to the browser.
 * The ThemeProvider and TooltipProvider inside are CLIENT components
 * that hydrate on the browser. This split gives you fast initial loads
 * (server-rendered HTML) with interactive features (client-side JS).
 *
 * NEXT.JS CONCEPT — Metadata:
 * The `metadata` export sets <title> and <meta> tags for SEO.
 * Unlike React SPAs where you'd use react-helmet, Next.js handles
 * this natively through a simple export.
 */
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ThemeProvider } from "@/providers/theme-provider";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import { Header } from "@/components/header";
import "./globals.css";

/**
 * NEXT.JS CONCEPT — Font optimization:
 * `next/font/google` automatically downloads and self-hosts Google Fonts.
 * This eliminates render-blocking font requests and avoids layout shift.
 * The `variable` prop creates a CSS custom property we apply to <body>.
 */
const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Securities Classifier",
  description: "AI-powered private securities classification with live streaming",
};

/**
 * REACT CONCEPT — Readonly<{ children: React.ReactNode }>:
 * `Readonly` makes all properties immutable (can't reassign children).
 * `React.ReactNode` is the broadest type for renderable content —
 * strings, numbers, JSX elements, arrays, null, etc.
 * Like Python's `Union[str, int, Element, list, None]`.
 */
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      {/*
        suppressHydrationWarning: Prevents React warnings when the
        server-rendered HTML doesn't match the client (which happens
        with theme switching — server doesn't know the user's theme).
      */}
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {/*
          Provider pattern — wraps the app in context providers:
          - ThemeProvider: Manages dark/light/grey theme
          - TooltipProvider: Required by shadcn/ui Tooltip components
          - Toaster: Renders toast notifications (from sonner library)

          This is similar to Python's context managers stacking:
          with theme(), tooltips(), toaster(): ...
        */}
        <ThemeProvider>
          <TooltipProvider>
            <Header />
            {/* max-w-6xl constrains content width on large screens */}
            <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
            <Toaster />
          </TooltipProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
