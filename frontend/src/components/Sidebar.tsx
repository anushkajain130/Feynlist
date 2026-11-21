"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, BarChart3, MessageSquare, Info } from "lucide-react";
import clsx from "clsx";

const nav = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/council", label: "Council", icon: MessageSquare },
  { href: "/about", label: "About", icon: Info },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside
      style={{
        width: "72px",
        background: "var(--surface)",
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "24px 0",
        gap: "8px",
        flexShrink: 0,
      }}
    >
      {/* Logo */}
      <div
        style={{
          width: "40px",
          height: "40px",
          borderRadius: "12px",
          background: "linear-gradient(135deg, #7c5cfc, #5eead4)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: "24px",
          fontSize: "16px",
          fontWeight: 700,
          color: "white",
        }}
      >
        F
      </div>

      {/* Nav items */}
      {nav.map(({ href, label, icon: Icon }) => {
        const active = pathname === href;
        return (
          <Link
            key={href}
            href={href}
            title={label}
            style={{
              width: "48px",
              height: "48px",
              borderRadius: "12px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: active ? "var(--accent)" : "var(--text-muted)",
              background: active ? "var(--accent-glow)" : "transparent",
              border: active ? "1px solid rgba(124,92,252,0.4)" : "1px solid transparent",
              transition: "all 0.15s",
              textDecoration: "none",
            }}
          >
            <Icon size={20} />
          </Link>
        );
      })}
    </aside>
  );
}
