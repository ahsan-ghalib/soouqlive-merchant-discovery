"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart3,
  Briefcase,
  Building2,
  LayoutDashboard,
  LogOut,
  MapPin,
  Radar,
  Settings,
  Tags,
} from "lucide-react";
import { clearSession, getAccessToken } from "@/lib/auth";
import { useLocale } from "@/components/locale-provider";
import { cn } from "@/lib/utils";
import { useEffect, useState } from "react";
import { authApi } from "@/services/api";
import type { User } from "@/types/api";
import { Button } from "@/components/ui/button";

const nav = [
  { href: "/dashboard", en: "Dashboard", ar: "لوحة التحكم", icon: LayoutDashboard },
  { href: "/discovery", en: "Discovery", ar: "الاكتشاف", icon: Radar },
  { href: "/leads", en: "Leads", ar: "العملاء", icon: Building2 },
  { href: "/campaigns", en: "Campaigns", ar: "الحملات", icon: Briefcase },
  { href: "/jobs", en: "Jobs", ar: "المهام", icon: BarChart3 },
  { href: "/categories", en: "Categories", ar: "التصنيفات", icon: Tags },
  { href: "/locations", en: "Locations", ar: "المواقع", icon: MapPin },
  { href: "/analytics", en: "Analytics", ar: "التحليلات", icon: BarChart3 },
  { href: "/settings", en: "Settings", ar: "الإعدادات", icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { t, locale, setLocale } = useLocale();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }
    authApi
      .me()
      .then(setUser)
      .catch(() => {
        clearSession();
        router.replace("/login");
      });
  }, [router]);

  function logout() {
    clearSession();
    router.replace("/login");
  }

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-slate-500">
        {t("Loading…", "جارٍ التحميل…")}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(ellipse_at_top,_#ecfdf5_0%,_#f8fafc_45%,_#f1f5f9_100%)]">
      <div className="mx-auto flex min-h-screen max-w-[1400px]">
        <aside className="sticky top-0 flex h-screen w-64 shrink-0 flex-col border-e border-slate-200/80 bg-white/80 p-4 backdrop-blur">
          <div className="mb-8 px-2">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">
              SoouqLive
            </p>
            <h1 className="mt-1 font-[family-name:var(--font-display)] text-xl font-semibold text-slate-900">
              {t("Merchant Discovery", "اكتشاف التجار")}
            </h1>
          </div>
          <nav className="flex flex-1 flex-col gap-1 overflow-y-auto">
            {nav.map((item) => {
              const Icon = item.icon;
              const active =
                pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                    active
                      ? "bg-teal-700 text-white"
                      : "text-slate-600 hover:bg-slate-100",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {t(item.en, item.ar)}
                </Link>
              );
            })}
          </nav>
          <div className="mt-4 space-y-3 border-t border-slate-100 pt-4">
            <div className="px-2 text-sm">
              <p className="font-medium text-slate-900">{user.full_name}</p>
              <p className="text-xs text-slate-500">{user.email}</p>
              <p className="mt-1 text-xs uppercase tracking-wide text-teal-700">
                {user.role}
              </p>
            </div>
            <div className="flex gap-2 px-1">
              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={() => setLocale(locale === "en" ? "ar" : "en")}
              >
                {locale === "en" ? "عربي" : "EN"}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={logout}
                aria-label="Logout"
              >
                <LogOut className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </aside>
        <main className="flex-1 overflow-auto p-6 md:p-8">{children}</main>
      </div>
    </div>
  );
}
