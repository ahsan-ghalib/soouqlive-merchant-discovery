"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useLocale } from "@/components/locale-provider";
import { authApi, providersApi, settingsApi } from "@/services/api";
import { getStoredUser } from "@/lib/auth";

export default function SettingsPage() {
  const { t, locale, setLocale } = useLocale();
  const qc = useQueryClient();
  const me = useQuery({ queryKey: ["me"], queryFn: () => authApi.me() });
  const providers = useQuery({
    queryKey: ["providers"],
    queryFn: () => providersApi.list(),
  });
  const smtp = useQuery({
    queryKey: ["smtp-settings"],
    queryFn: () => settingsApi.getSmtp(),
  });
  const stored = getStoredUser();

  const [host, setHost] = useState("");
  const [port, setPort] = useState(587);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fromEmail, setFromEmail] = useState("");
  const [fromName, setFromName] = useState("");
  const [replyTo, setReplyTo] = useState("");
  const [security, setSecurity] = useState<"tls" | "ssl" | "none">("tls");
  const [enabled, setEnabled] = useState(false);
  const [testTo, setTestTo] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!smtp.data) return;
    setHost(smtp.data.host || "");
    setPort(smtp.data.port || 587);
    setUsername(smtp.data.username || "");
    setFromEmail(smtp.data.from_email || "");
    setFromName(smtp.data.from_name || "");
    setReplyTo(smtp.data.reply_to || "");
    setEnabled(Boolean(smtp.data.is_enabled));
    if (smtp.data.use_ssl) setSecurity("ssl");
    else if (smtp.data.use_tls) setSecurity("tls");
    else setSecurity("none");
    if (!testTo && (me.data?.email || stored?.email)) {
      setTestTo(me.data?.email || stored?.email || "");
    }
  }, [smtp.data, me.data?.email, stored?.email, testTo]);

  const save = useMutation({
    mutationFn: () =>
      settingsApi.updateSmtp({
        host,
        port,
        username: username || null,
        password: password || null,
        from_email: fromEmail,
        from_name: fromName || null,
        reply_to: replyTo || null,
        use_tls: security === "tls",
        use_ssl: security === "ssl",
        is_enabled: enabled,
      }),
    onSuccess: async () => {
      setPassword("");
      setMessage(t("SMTP settings saved.", "تم حفظ إعدادات SMTP."));
      await qc.invalidateQueries({ queryKey: ["smtp-settings"] });
    },
    onError: (err: Error) => setMessage(err.message),
  });

  const test = useMutation({
    mutationFn: () =>
      settingsApi.testSmtp({
        to_email: testTo,
        use_template: true,
        template: "vendor_outreach",
      }),
    onSuccess: (data) =>
      setMessage(
        t(
          `Vendor outreach template sent to ${data.to_email}`,
          `تم إرسال قالب تواصل التجار إلى ${data.to_email}`,
        ),
      ),
    onError: (err: Error) => setMessage(err.message),
  });

  return (
    <div>
      <PageHeader
        title={t("Settings", "الإعدادات")}
        description={t(
          "Account, SMTP outbound mail, and provider policy.",
          "الحساب وبريد SMTP الصادر وسياسات المزودين.",
        )}
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <h3 className="font-semibold">
              {t("SMTP email", "بريد SMTP")}
            </h3>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-xs text-slate-500">
              {t(
                "Save your mail server here. Campaign sending will use this later — for now configure and test only.",
                "احفظ خادم البريد هنا. إرسال الحملات سيستخدمه لاحقاً — الآن الإعداد والاختبار فقط.",
              )}
            </p>
            <Input
              placeholder={t("Host (e.g. smtp.gmail.com)", "المضيف")}
              value={host}
              onChange={(e) => setHost(e.target.value)}
            />
            <Input
              type="number"
              min={1}
              max={65535}
              placeholder="Port"
              value={port}
              onChange={(e) => setPort(Number(e.target.value))}
            />
            <Input
              placeholder={t("Username", "اسم المستخدم")}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="off"
            />
            <Input
              type="password"
              placeholder={
                smtp.data?.password_set
                  ? t("Password (leave blank to keep)", "كلمة المرور (اتركها فارغة للإبقاء)")
                  : t("Password", "كلمة المرور")
              }
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
            />
            <Input
              placeholder={t("From email", "البريد المرسل")}
              value={fromEmail}
              onChange={(e) => setFromEmail(e.target.value)}
            />
            <Input
              placeholder={t("From name", "اسم المرسل")}
              value={fromName}
              onChange={(e) => setFromName(e.target.value)}
            />
            <Input
              placeholder={t("Reply-To (optional)", "الرد إلى (اختياري)")}
              value={replyTo}
              onChange={(e) => setReplyTo(e.target.value)}
            />
            <Select
              value={security}
              onChange={(e) =>
                setSecurity(e.target.value as "tls" | "ssl" | "none")
              }
            >
              <option value="tls">
                {t("TLS / STARTTLS (port 587)", "TLS / STARTTLS (منفذ 587)")}
              </option>
              <option value="ssl">
                {t("SSL (port 465)", "SSL (منفذ 465)")}
              </option>
              <option value="none">{t("No encryption", "بدون تشفير")}</option>
            </Select>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
              />
              {t("Enable SMTP for outbound mail", "تفعيل SMTP للبريد الصادر")}
            </label>
            <Button
              className="w-full"
              disabled={save.isPending}
              onClick={() => save.mutate()}
            >
              {save.isPending
                ? t("Saving…", "جارٍ الحفظ…")
                : t("Save SMTP settings", "حفظ إعدادات SMTP")}
            </Button>

            <div className="border-t border-slate-100 pt-3">
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
                {t("Send test email", "إرسال بريد تجريبي")}
              </p>
              <p className="mb-2 text-xs text-slate-500">
                {t(
                  "Uses vendor-outreach-email.html (SoouqLive merchant invite template).",
                  "يستخدم قالب vendor-outreach-email.html (دعوة تاجر سوق لايف).",
                )}
              </p>
              <Input
                placeholder={t("To email", "إلى بريد")}
                value={testTo}
                onChange={(e) => setTestTo(e.target.value)}
              />
              <Button
                className="mt-2 w-full"
                variant="secondary"
                disabled={test.isPending || !testTo}
                onClick={() => test.mutate()}
              >
                {test.isPending
                  ? t("Sending…", "جارٍ الإرسال…")
                  : t("Send vendor outreach test", "إرسال اختبار قالب التاجر")}
              </Button>
            </div>

            {message ? (
              <p className="text-sm text-slate-600">{message}</p>
            ) : null}
            {smtp.data?.password_set ? (
              <p className="text-xs text-teal-800">
                {t("Password is saved (encrypted).", "كلمة المرور محفوظة (مشفّرة).")}
              </p>
            ) : null}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <h3 className="font-semibold">{t("Account", "الحساب")}</h3>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <p>
                <span className="text-slate-500">{t("Name", "الاسم")}: </span>
                {me.data?.full_name || stored?.full_name}
              </p>
              <p>
                <span className="text-slate-500">{t("Email", "البريد")}: </span>
                {me.data?.email || stored?.email}
              </p>
              <p>
                <span className="text-slate-500">{t("Role", "الدور")}: </span>
                {me.data?.role || stored?.role}
              </p>
              <div className="pt-3">
                <p className="mb-2 text-slate-500">{t("Language", "اللغة")}</p>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant={locale === "en" ? "default" : "outline"}
                    onClick={() => setLocale("en")}
                  >
                    English
                  </Button>
                  <Button
                    size="sm"
                    variant={locale === "ar" ? "default" : "outline"}
                    onClick={() => setLocale("ar")}
                  >
                    العربية
                  </Button>
                </div>
              </div>
              <p className="pt-4 text-xs text-slate-400">
                API: {process.env.NEXT_PUBLIC_API_BASE_URL}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <h3 className="font-semibold">
                {t("Providers & retention", "المزودون والاحتفاظ")}
              </h3>
            </CardHeader>
            <CardContent className="space-y-3">
              {(providers.data?.providers || []).map((p) => (
                <div
                  key={p.id}
                  className="rounded-xl border border-slate-100 px-3 py-3 text-sm"
                >
                  <p className="font-medium">{p.name}</p>
                  <p className="text-xs text-slate-500">
                    {p.adapter_key} · {p.provider_type}
                  </p>
                  {p.policy ? (
                    <pre className="mt-2 overflow-x-auto rounded-lg bg-slate-50 p-2 text-[11px] text-slate-600">
                      {JSON.stringify(p.policy, null, 2)}
                    </pre>
                  ) : null}
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
