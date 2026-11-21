"use client";

import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { authApi } from "@/services/api";
import { setSession } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { useLocale } from "@/components/locale-provider";

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});

type FormValues = z.infer<typeof schema>;

export default function LoginPage() {
  const router = useRouter();
  const { t, locale, setLocale } = useLocale();
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      email: "admin@soouqlive.example",
      password: "ChangeMeAdmin123!",
    },
  });

  async function onSubmit(values: FormValues) {
    setError(null);
    try {
      const data = await authApi.login(values.email, values.password);
      setSession(data.tokens, {
        id: data.user.id,
        full_name: data.user.full_name,
        email: data.user.email,
        role: data.user.role,
      });
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950 px-4">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(15,118,110,0.35),transparent_40%),radial-gradient(circle_at_80%_0%,rgba(245,158,11,0.2),transparent_35%),linear-gradient(160deg,#020617,#0f172a_55%,#134e4a)]" />
      <Card className="relative z-10 w-full max-w-md border-slate-200/20 bg-white/95 shadow-2xl">
        <CardHeader>
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-teal-700">
            SoouqLive
          </p>
          <h1 className="mt-2 font-[family-name:var(--font-display)] text-3xl font-semibold text-slate-900">
            {t("Merchant Discovery", "اكتشاف التجار")}
          </h1>
          <p className="text-sm text-slate-500">
            {t(
              "Sign in to run discovery, score leads, and manage campaigns.",
              "سجّل الدخول لتشغيل الاكتشاف وتقييم العملاء وإدارة الحملات.",
            )}
          </p>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">
                {t("Email", "البريد الإلكتروني")}
              </label>
              <Input type="email" autoComplete="username" {...register("email")} />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">
                {t("Password", "كلمة المرور")}
              </label>
              <Input
                type="password"
                autoComplete="current-password"
                {...register("password")}
              />
            </div>
            {error ? (
              <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {error}
              </p>
            ) : null}
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting
                ? t("Signing in…", "جارٍ تسجيل الدخول…")
                : t("Sign in", "تسجيل الدخول")}
            </Button>
          </form>
          <div className="mt-4 flex justify-end">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setLocale(locale === "en" ? "ar" : "en")}
            >
              {locale === "en" ? "عربي" : "EN"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
