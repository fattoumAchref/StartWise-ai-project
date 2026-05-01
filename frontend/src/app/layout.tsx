import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import { ThemeProvider } from "@/components/layout/theme-provider";
import { Toaster } from "sonner";
import { ProjectProvider } from "@/context/ProjectContext";
import StartWiseRoot from "@/components/startwise/StartWiseRoot";

export const metadata: Metadata = {
  title: "Startwise — AI Strategy Platform",
  description:
    "De l'idéation à l'analyse stratégique complète, propulsé par l'IA.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="fr"
      className={`${GeistSans.variable} ${GeistMono.variable}`}
      suppressHydrationWarning
    >
      <body className={`${GeistSans.className} antialiased`}>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange={false}
          storageKey="startwise-theme"
        >
          {/* ProjectContext: pont idéation ↔ StartWise */}
          <ProjectProvider>
            {/* AppProvider: WebSocket + agents state + i18n */}
            <StartWiseRoot>
              {children}
            </StartWiseRoot>
          </ProjectProvider>
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  );
}
