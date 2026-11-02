import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Dicer Lab · Procesamiento de dsRNA",
  description: "Laboratorio local y reproducible para explorar el modelo de fase de Dicer.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="es"><body>{children}</body></html>;
}
