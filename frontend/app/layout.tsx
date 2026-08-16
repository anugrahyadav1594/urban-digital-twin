import type { Metadata, Viewport } from "next";
import Script from "next/script";
import "./globals.css";

export const metadata: Metadata = {
  title: "NAGAR-X · Urban Digital Twin Workspace",
  description: "Floating-window geospatial planning workspace over a Cesium 3D city"
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#070b12" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* CesiumJS is served statically from /public/cesium (see scripts/copy-cesium.mjs)
            so webpack never has to bundle its 4 MB build + workers. */}
        <link rel="stylesheet" href="/cesium/Widgets/widgets.css" />
        <link rel="icon" href="data:," />
        <Script id="cesium-base-url" strategy="beforeInteractive">{`window.CESIUM_BASE_URL='/cesium';`}</Script>
        <Script src="/cesium/Cesium.js" strategy="beforeInteractive" />
      </head>
      <body>{children}</body>
    </html>
  );
}
