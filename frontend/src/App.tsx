import { NavLink, Outlet } from "react-router-dom";

const tabs = [
  { to: "/", label: "Review", end: true },
  { to: "/rules", label: "Rules" },
  { to: "/brain", label: "Brain" },
  { to: "/settings", label: "Settings" },
];

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="text-lg font-semibold">📬 Inbox Autopilot</span>
            <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
              review &amp; send
            </span>
          </div>
          <nav className="flex gap-1">
            {tabs.map((t) => (
              <NavLink
                key={t.to}
                to={t.to}
                end={t.end}
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 text-sm font-medium transition ${
                    isActive
                      ? "bg-ink text-white"
                      : "text-slate-600 hover:bg-slate-100"
                  }`
                }
              >
                {t.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
