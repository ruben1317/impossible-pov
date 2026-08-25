import type { MetadataRoute } from "next";
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "IMPOSSIBLE POV Studio",
    short_name: "POV Studio",
    description: "Mobile production dashboard for IMPOSSIBLE POV YouTube videos",
    start_url: "/",
    display: "standalone",
    background_color: "#050505",
    theme_color: "#d31313",
    icons: [
      {src:"/icon-192.png",sizes:"192x192",type:"image/png"},
      {src:"/icon-512.png",sizes:"512x512",type:"image/png"}
    ]
  };
}
