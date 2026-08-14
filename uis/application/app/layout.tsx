import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Brasaland - Directorio de Proveedores",
  description: "Aplicación de gestión de proveedores para Brasaland",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body className="bg-stone-950 text-stone-100 antialiased">
        {children}
      </body>
    </html>
  );
}
