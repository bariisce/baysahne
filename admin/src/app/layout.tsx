import type { Metadata } from "next";
import { Inter, Playfair_Display } from "next/font/google";
import { FeedbackProvider } from "@/components/feedback";
import "./globals.css";

// Typefaces used on baysahne.com. next/font self-hosts them at build time (no runtime Google requests).
const inter = Inter({ subsets: ["latin", "latin-ext"], variable: "--font-inter", display: "swap" });
const playfair = Playfair_Display({ subsets: ["latin", "latin-ext"], variable: "--font-playfair", display: "swap" });

export const metadata: Metadata = {
  title: "Bay Sahne · Yönetim Paneli",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr" className={`${inter.variable} ${playfair.variable}`}>
      <body>
        <FeedbackProvider>{children}</FeedbackProvider>
      </body>
    </html>
  );
}
