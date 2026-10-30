import { Compass, LogOut, Menu, MessageCircle, ShieldCheck, Ticket, X } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import Logo from "../components/Logo";
import { useAuth } from "../lib/auth";
import { cx } from "../lib/format";

const NAV = [
  { to: "/app", label: "Ask Sara", icon: <MessageCircle size={18} />, end: true },
  { to: "/app/strategist", label: "Strategist", icon: <Compass size={18} /> },
  { to: "/app/trips", label: "My Trips", icon: <Ticket size={18} /> },
  { to: "/app/account", label: "Account & Security", icon: <ShieldCheck size={18} /> },
];

export default function AppLayout() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);

  const nav = (
    <nav className="flex flex-1 flex-col gap-1">
      {NAV.map((n) => (
        <NavLink key={n.to} to={n.to} end={n.end} onClick={() => setOpen(false)}
          className={({ isActive }) => cx("flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition",
            isActive ? "bg-mustard-500 text-ink-950" : "text-ink-300 hover:bg-ink-800 hover:text-cream")}>
          {n.icon} {n.label}
        </NavLink>
      ))}
    </nav>
  );

  const footer = (
    <div className="border-t border-ink-800 pt-4">
      <div className="flex items-center gap-3 px-1">
        <span className="grid size-9 place-items-center rounded-full bg-mustard-500 font-display font-bold text-ink-950">{user?.name.charAt(0).toUpperCase()}</span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold text-cream">{user?.name}</div>
          <div className="truncate text-xs text-ink-400">{user?.email}</div>
        </div>
        <button onClick={logout} className="rounded-lg p-2 text-ink-400 hover:bg-ink-800 hover:text-cream" aria-label="Log out" title="Log out">
          <LogOut size={18} />
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex h-dvh bg-cream">
      <aside className="hidden w-64 shrink-0 flex-col gap-6 bg-ink-950 p-4 lg:flex">
        <div className="px-1 pt-1"><Logo dark to="/app" /></div>
        {nav}
        {footer}
      </aside>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-ink-950/50" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-72 flex-col gap-6 bg-ink-950 p-4">
            <div className="flex items-center justify-between px-1 pt-1">
              <Logo dark to="/app" />
              <button onClick={() => setOpen(false)} className="text-ink-300" aria-label="Close menu"><X size={22} /></button>
            </div>
            {nav}
            {footer}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-ink-100 bg-white px-4 py-3 lg:hidden">
          <button onClick={() => setOpen(true)} aria-label="Open menu"><Menu size={22} /></button>
          <Logo to="/app" />
          <span className="w-6" />
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
