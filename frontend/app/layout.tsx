import type { Metadata } from "next";
import { Geist_Mono, Inter } from "next/font/google";
import { Gate } from "@/components/layout/Gate";
import { AuthProvider } from "@/lib/auth";
import { THEME_SCRIPT } from "@/lib/theme";
import "./globals.css";

const inter = Inter({ variable: "--font-sans", subsets: ["latin"], display: "swap" });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Timetabl.ai",
  description: "Clash-free college timetables, for any college.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className={`${inter.variable} ${geistMono.variable} antialiased`}>
        <AuthProvider>
          <Gate>{children}</Gate>
        </AuthProvider>
      </body>
    </html>
  );
}
