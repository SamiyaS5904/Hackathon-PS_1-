import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Gate } from "@/components/layout/Gate";
import { AuthProvider } from "@/lib/auth";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Timetabl.ai",
  description: "Clash-free college timetables, for any college.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <AuthProvider>
          <Gate>{children}</Gate>
        </AuthProvider>
      </body>
    </html>
  );
}
