import type { ReactNode } from "react";

export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <main>
      <header>
        <h1>Multi-Agent Learning Console</h1>
      </header>
      {children}
    </main>
  );
}
