import Link from "next/link";
export function Nav(){return <>
  <div className="topbar"><Link className="brand" href="/"><img className="brandimg" src="/icon-192.png" alt=""/><div>IMPOSSIBLE <span>POV</span></div></Link><div className="desktopNav nav"><Link href="/">Dashboard</Link><Link href="/videos/new">Create</Link><Link href="/settings">Settings</Link><Link href="/setup">Setup</Link></div></div>
  <nav className="mobileNav" aria-label="Primary"><Link href="/"><span>⌂</span><small>Home</small></Link><Link href="/videos/new" className="createFab"><span>＋</span><small>Create</small></Link><Link href="/settings"><span>⚙</span><small>Settings</small></Link></nav>
</>}
