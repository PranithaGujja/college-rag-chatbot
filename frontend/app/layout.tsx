import type { Metadata, Viewport } from "next";
import "./globals.css";
import { COLLEGE_NAME, PORTAL_NAME } from "@/lib/brand";

export const metadata: Metadata = {
  title: `${PORTAL_NAME} | ${COLLEGE_NAME}`,
  description: "Ask questions about the official Student and Faculty handbooks and get answers with page references.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
