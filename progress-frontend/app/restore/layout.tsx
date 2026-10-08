import type { Metadata } from "next";

/** Reached only from a letter, with a token: without one a crawler would see nothing
 *  but a broken-link screen. */
export const metadata: Metadata = {
  title: "Восстановление аккаунта",
  robots: { index: false, follow: false },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
