import type { ReactNode } from "react";
import { TopBar, type TopBarProps } from "./TopBar";
import { Footer } from "./Footer";

export function PublicLayout({
  children,
  topBar,
}: {
  children: ReactNode;
  topBar?: TopBarProps;
}) {
  return (
    <div className="min-h-dvh flex flex-col bg-background text-foreground">
      <TopBar {...topBar} />
      <main className="flex-1">{children}</main>
      <Footer />
    </div>
  );
}
