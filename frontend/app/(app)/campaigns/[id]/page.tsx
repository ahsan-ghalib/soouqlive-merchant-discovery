"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { StatusBadge } from "@/components/status-badge";
import { useLocale } from "@/components/locale-provider";
import { businessesApi, campaignsApi, consentApi } from "@/services/api";

export default function CampaignDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useLocale();
  const qc = useQueryClient();
  const [leadIds, setLeadIds] = useState("");
  const [channel, setChannel] = useState("whatsapp");
  const [msg, setMsg] = useState<string | null>(null);

  const campaign = useQuery({
    queryKey: ["campaign", id],
    queryFn: () => campaignsApi.get(id),
  });
  const analytics = useQuery({
    queryKey: ["campaign-analytics", id],
    queryFn: () => campaignsApi.analytics(id),
  });

  const addLeads = useMutation({
    mutationFn: () => {
      const ids = leadIds
        .split(/[\s,]+/)
        .map((s) => s.trim())
        .filter(Boolean);
      return campaignsApi.addLeads(id, ids);
    },
    onSuccess: (data) => {
      setMsg(
        `Added ${(data as { added?: unknown[] }).added?.length ?? "?"} leads`,
      );
      setLeadIds("");
      qc.invalidateQueries({ queryKey: ["campaign-analytics", id] });
    },
    onError: (e: Error) => setMsg(e.message),
  });

  const pullContacts = useMutation({
    mutationFn: async () => {
      const list = await businessesApi.list({
        page: 1,
        limit: 100,
        minimum_score: 40,
        has_phone: channel === "whatsapp" || channel === "phone" ? true : undefined,
        has_email: channel === "email" ? true : undefined,
        has_website: undefined,
      });
      const rows = list.data || [];
      const eligible: string[] = [];
      const blocked: string[] = [];
      for (const b of rows) {
        try {
          const purpose =
            channel === "whatsapp"
              ? "promotional_whatsapp"
              : channel === "email"
                ? "promotional_email"
                : "business_follow_up";
          const check = await consentApi.checkEligibility({
            business_id: b.id,
            purpose,
            channel: channel === "phone" ? "phone" : channel,
          });
          if (check.eligible) eligible.push(b.id);
          else blocked.push(b.business_name);
        } catch {
          // No consent record yet → not eligible for marketing blast
          blocked.push(b.business_name);
        }
      }
      let addResult: Record<string, unknown> | null = null;
      if (eligible.length) {
        addResult = await campaignsApi.addLeads(id, eligible);
      }
      return { eligible, blocked, addResult, scanned: rows.length };
    },
    onSuccess: (data) => {
      setMsg(
        `Scanned ${data.scanned}. Consent-eligible added: ${data.eligible.length}. Blocked (no consent): ${data.blocked.length}.`,
      );
      qc.invalidateQueries({ queryKey: ["campaign-analytics", id] });
    },
    onError: (e: Error) => setMsg(e.message),
  });

  const qualify = useMutation({
    mutationFn: () => campaignsApi.qualify(id, 60),
    onSuccess: () => {
      setMsg(t("Qualification finished", "اكتمل التأهيل"));
      qc.invalidateQueries({ queryKey: ["campaign-analytics", id] });
      qc.invalidateQueries({ queryKey: ["campaign", id] });
    },
    onError: (e: Error) => setMsg(e.message),
  });

  if (campaign.isLoading) {
    return <p className="text-slate-500">{t("Loading…", "جارٍ التحميل…")}</p>;
  }
  if (!campaign.data) {
    return (
      <p className="text-rose-600">{t("Campaign not found", "الحملة غير موجودة")}</p>
    );
  }

  const c = campaign.data;
  const a = analytics.data || {};

  return (
    <div>
      <PageHeader
        title={c.name}
        description={c.description || c.campaign_type}
        actions={<StatusBadge status={c.status} />}
      />

      {msg ? (
        <p className="mb-4 rounded-lg bg-teal-50 px-3 py-2 text-sm text-teal-900">
          {msg}
        </p>
      ) : null}

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="pt-5">
            <p className="text-sm text-slate-500">{t("Leads in campaign", "عملاء الحملة")}</p>
            <p className="mt-1 text-2xl font-semibold">
              {String((a as { total_leads?: number }).total_leads ?? "—")}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5">
            <p className="text-sm text-slate-500">{t("Type", "النوع")}</p>
            <p className="mt-1 text-lg font-medium">{c.campaign_type}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5">
            <p className="text-sm text-slate-500">{t("Status", "الحالة")}</p>
            <p className="mt-1">
              <StatusBadge status={c.status} />
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <h3 className="font-semibold">
              {t("Build WhatsApp / email list", "بناء قائمة واتساب / بريد")}
            </h3>
          </CardHeader>
          <CardContent className="space-y-3">
            <Select value={channel} onChange={(e) => setChannel(e.target.value)}>
              <option value="whatsapp">WhatsApp</option>
              <option value="email">Email</option>
              <option value="phone">Phone</option>
            </Select>
            <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900">
              {t(
                "Pulls scored leads with that contact, then keeps only consent-eligible. Cold blast without consent is blocked.",
                "يجلب العملاء ذوي التواصل ثم يبقي من لديهم موافقة فقط. الإرسال البارد بدون موافقة ممنوع.",
              )}
            </p>
            <Button
              className="w-full"
              disabled={pullContacts.isPending}
              onClick={() => pullContacts.mutate()}
            >
              {pullContacts.isPending
                ? t("Checking consent…", "جارٍ فحص الموافقة…")
                : t("Pull consent-eligible leads", "جلب العملاء المؤهلين بالموافقة")}
            </Button>
            <Button
              className="w-full"
              variant="secondary"
              disabled={qualify.isPending}
              onClick={() => qualify.mutate()}
            >
              {t("Qualify campaign (score ≥ 60)", "تأهيل الحملة (≥ 60)")}
            </Button>
            <div className="border-t border-slate-100 pt-3">
              <p className="mb-2 text-xs text-slate-500">
                {t("Or paste business UUIDs", "أو الصق معرّفات")}
              </p>
              <Input
                placeholder="uuid, uuid, …"
                value={leadIds}
                onChange={(e) => setLeadIds(e.target.value)}
              />
              <Button
                className="mt-2"
                variant="outline"
                disabled={!leadIds || addLeads.isPending}
                onClick={() => addLeads.mutate()}
              >
                {t("Add manually", "إضافة يدوية")}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h3 className="font-semibold">{t("Campaign snapshot", "لقطة الحملة")}</h3>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-slate-700">
            <p>
              {t(
                "Next steps after discovery sweep:",
                "الخطوات بعد مسح الاكتشاف:",
              )}
            </p>
            <ol className="list-decimal space-y-1 ps-5">
              <li>{t("Enrich leads with websites (for email)", "أثْر العملاء ذوي المواقع (للبريد)")}</li>
              <li>{t("Record consent on lead / contact", "سجّل الموافقة على العميل")}</li>
              <li>{t("Pull eligible list here by channel", "اجلب القائمة المؤهلة حسب القناة")}</li>
              <li>{t("Export / send via your WhatsApp-Email tool", "صدّر / أرسل عبر أداة واتساب-بريد")}</li>
            </ol>
            {(a as { note?: string }).note ? (
              <p className="mt-3 text-xs text-slate-500">
                {String((a as { note?: string }).note)}
              </p>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
