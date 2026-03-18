import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "Report Dashboard",
  description: "Corporate Annual Report Data Dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-slate-950 text-slate-100 min-h-screen">
        <Sidebar />
        <main className="ml-56 p-6 min-h-screen">{children}</main>
      </body>
    </html>
  );
}
