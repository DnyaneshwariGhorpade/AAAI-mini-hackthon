import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MediRAG",
  description: "Hybrid retrieval chat over medical abstracts (shard 01)",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
