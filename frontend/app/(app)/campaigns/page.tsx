"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { StatusBadge } from "@/components/status-badge";
import { useLocale } from "@/components/locale-provider";
import { campaignsApi } from "@/services/api";

export default function CampaignsPage() {
  const { t } = useLocale();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [campaignType, setCampaignType] = useState("merchant_acquisition");
  const [channel, setChannel] = useState("whatsapp");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  const campaigns = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => campaignsApi.list({ page: 1, limit: 50 }),
  });

  const create = useMutation({
    mutationFn: () =>
      campaignsApi.create({
        name,
        description:
          description ||
          `${channel} outreach — consent required before send`,
        campaign_type: campaignType,
        status: "draft",
        target_filters: {
          channel,
          requires_consent: true,
        },
      }),
    onSuccess: async () => {
      setName("");
      setDescription("");
      setError(null);
      await qc.invalidateQueries({ queryKey: ["campaigns"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  return (
    <div>
      <PageHeader
        title={t("Campaigns", "الحملات")}
        description={t(
          "Build WhatsApp/email lists from discovered leads. Consent is required before outreach.",
          "ابنِ قوائم واتساب/بريد من العملاء المكتشفين. الموافقة مطلوبة قبل التواصل.",
        )}
      />

      <div className="grid gap-6 xl:grid-cols-[340px_1fr]">
        <Card>
          <CardHeader>
            <h3 className="font-semibold">{t("Create campaign", "إنشاء حملة")}</h3>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input
              placeholder={t("Name", "الاسم")}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <Input
              placeholder={t("Description", "الوصف")}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
            <Select
              value={campaignType}
              onChange={(e) => setCampaignType(e.target.value)}
            >
              <option value="merchant_acquisition">merchant_acquisition</option>
              <option value="advertising_research">advertising_research</option>
              <option value="market_research">market_research</option>
            </Select>
            <Select value={channel} onChange={(e) => setChannel(e.target.value)}>
              <option value="whatsapp">{t("WhatsApp", "واتساب")}</option>
              <option value="email">{t("Email", "بريد")}</option>
              <option value="phone">{t("Phone", "هاتف")}</option>
            </Select>
            <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900">
              {t(
                "Do not blast cold WhatsApp/email without consent. Enrich first, record consent, then outreach.",
                "لا ترسل واتساب/بريد بارد بدون موافقة. أثْر أولاً، سجّل الموافقة، ثم تواصل.",
              )}
            </p>
            <Button
              className="w-full"
              disabled={!name || create.isPending}
              onClick={() => create.mutate()}
            >
              {t("Create", "إنشاء")}
            </Button>
            {error ? <p className="text-sm text-rose-600">{error}</p> : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h3 className="font-semibold">{t("All campaigns", "كل الحملات")}</h3>
          </CardHeader>
          <CardContent className="space-y-2">
            {(campaigns.data?.data || []).map((c) => (
              <Link
                key={c.id}
                href={`/campaigns/${c.id}`}
                className="flex items-center justify-between rounded-xl border border-slate-100 px-3 py-3 hover:bg-slate-50"
              >
                <div>
                  <p className="font-medium text-slate-900">{c.name}</p>
                  <p className="text-xs text-slate-500">
                    {c.campaign_type}
                    {c.target_filters &&
                    typeof c.target_filters === "object" &&
                    "channel" in c.target_filters
                      ? ` · ${String((c.target_filters as { channel?: string }).channel)}`
                      : ""}
                  </p>
                </div>
                <StatusBadge status={c.status} />
              </Link>
            ))}
            {!campaigns.data?.data?.length ? (
              <p className="py-6 text-center text-sm text-slate-500">
                {t("No campaigns yet.", "لا حملات بعد.")}
              </p>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
