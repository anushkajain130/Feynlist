import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "Feynlist — Your Productivity OS",
  description: "AI-powered task management with The Council of five agents.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* App Router root layout: this <head> is shared by every page, so the
            pages-router-only "custom font" warning doesn't apply here. */}
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="flex h-screen overflow-hidden">
        <Sidebar />
        <main className="app-main flex-1 overflow-y-auto">
          {children}
        </main>
      </body>
    </html>
  );
}
