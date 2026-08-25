import "./globals.css";
import {Nav} from "@/components/Nav";
import type { Metadata, Viewport } from "next";
export const metadata: Metadata={title:"IMPOSSIBLE POV Content Studio",description:"Semi-automatic YouTube AI production dashboard",manifest:"/manifest.webmanifest",appleWebApp:{capable:true,title:"POV Studio",statusBarStyle:"black-translucent"},icons:{apple:"/icon-192.png"}};
export const viewport: Viewport={width:"device-width",initialScale:1,maximumScale:1,themeColor:"#d31313",viewportFit:"cover"};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body><main className="shell"><Nav/>{children}</main></body></html>}
