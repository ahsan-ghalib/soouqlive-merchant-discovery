"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { StatusBadge } from "@/components/status-badge";
import { useLocale } from "@/components/locale-provider";
import {
  businessesApi,
  consentApi,
  crmApi,
  enrichmentApi,
} from "@/services/api";

const TRANSITIONS = [
  "new",
  "researching",
  "qualified",
  "contacted",
  "interested",
  "follow_up",
  "registered",
  "rejected",
  "do_not_contact",
];

type ScoreReason = {
  score?: number;
  note?: string;
  scored_at?: string;
  components?: Record<string, number>;
  details?: {
    has_email?: boolean;
    has_phone?: boolean;
    has_website?: boolean;
    category_slug?: string | null;
    delivery_ready?: boolean;
    website_domain?: string | null;
    contact_quality?: string;
    monetization_packs?: string[];
  };
};

const COMPONENT_LABELS: Record<string, { en: string; ar: string }> = {
  relevant_category: { en: "Relevant category", ar: "تصنيف مناسب" },
  active_website: { en: "Active website", ar: "موقع نشط" },
  verified_public_contact: { en: "Public contact", ar: "تواصل عام" },
  relevant_delivery_service: { en: "Delivery fit", ar: "ملاءمة التوصيل" },
  strong_soouqlive_fit: { en: "SoouqLive fit", ar: "ملاءمة سوق لايف" },
  website_gap_opportunity: { en: "No-website opportunity", ar: "فرصة بدون موقع" },
};

const PACK_LABELS: Record<string, { en: string; ar: string }> = {
  no_website_site_build: { en: "Pitch: build website", ar: "عرض: بناء موقع" },
  website_upgrade: { en: "Pitch: website upgrade", ar: "عرض: تطوير الموقع" },
  restaurant_portal: { en: "Pitch: restaurant portal", ar: "عرض: بوابة مطعم" },
  real_estate_portal: { en: "Pitch: real-estate portal", ar: "عرض: بوابة عقارات" },
  needs_email_enrichment: { en: "Needs email enrichment", ar: "يحتاج إثراء بريد" },
};

function asScoreReason(raw: unknown): ScoreReason {
  if (!raw || typeof raw !== "object") return {};
  return raw as ScoreReason;
}

export default function LeadDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useLocale();
  const qc = useQueryClient();
  const [nextStatus, setNextStatus] = useState("qualified");
  const [msg, setMsg] = useState<string | null>(null);

  const business = useQuery({
    queryKey: ["business", id],
    queryFn: () => businessesApi.get(id),
  });
  const score = useQuery({
    queryKey: ["score", id],
    queryFn: () => crmApi.getScore(id),
  });
  const consent = useQuery({
    queryKey: ["consent", id],
    queryFn: () => consentApi.forBusiness(id),
  });
  const eligibility = useQuery({
    queryKey: ["eligibility", id],
    queryFn: () =>
      consentApi.checkEligibility({
        business_id: id,
        purpose: "marketing",
        channel: "email",
      }),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["business", id] });
    qc.invalidateQueries({ queryKey: ["score", id] });
    qc.invalidateQueries({ queryKey: ["consent", id] });
    qc.invalidateQueries({ queryKey: ["eligibility", id] });
  };

  const scoreMut = useMutation({
    mutationFn: () => crmApi.score(id, { auto_qualify: false }),
    onSuccess: (data) => {
      setMsg(`Scored ${data.score}`);
      invalidate();
    },
    onError: (e: Error) => setMsg(e.message),
  });

  const enrichMut = useMutation({
    mutationFn: () => enrichmentApi.run(id),
    onSuccess: () => {
      setMsg("Enrichment queued");
      invalidate();
    },
    onError: (e: Error) => setMsg(e.message),
  });

  const transitionMut = useMutation({
    mutationFn: () => crmApi.transition(id, nextStatus),
    onSuccess: () => {
      setMsg(`Moved to ${nextStatus}`);
      invalidate();
    },
    onError: (e: Error) => setMsg(e.message),
  });

  if (business.isLoading) {
    return <p className="text-slate-500">{t("Loading…", "جارٍ التحميل…")}</p>;
  }
  if (!business.data) {
    return <p className="text-rose-600">{t("Lead not found", "العميل غير موجود")}</p>;
  }

  const b = business.data;
  const reason = asScoreReason(
    score.data?.qualification_reason || b.qualification_reason,
  );
  const details = reason.details || {};
  const components = reason.components || {};
  const packs =
    details.monetization_packs ||
    (b.qualification_reason as { monetization?: string[] } | null)?.monetization ||
    [];
  const totalScore = reason.score ?? b.qualification_score;

  return (
    <div>
      <PageHeader
        title={b.business_name}
        description={b.business_name_ar || b.website_url || undefined}
        actions={<StatusBadge status={b.lead_status} />}
      />

      {msg ? (
        <p className="mb-4 rounded-lg bg-teal-50 px-3 py-2 text-sm text-teal-800">
          {msg}
        </p>
      ) : null}

      <div className="mb-6 grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <h3 className="font-semibold">{t("Overview", "نظرة عامة")}</h3>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p>
              <span className="text-slate-500">{t("Score", "النقاط")}: </span>
              <strong>{totalScore}</strong>
            </p>
            <p>
              <span className="text-slate-500">{t("Business status", "حالة النشاط")}: </span>
              {b.business_status}
            </p>
            <p>
              <span className="text-slate-500">{t("Phone", "الهاتف")}: </span>
              <strong className="text-slate-900">
                {b.primary_phone ||
                  b.contacts?.find((c) => c.contact_type === "business_phone")
                    ?.contact_value ||
                  "—"}
              </strong>
            </p>
            <p>
              <span className="text-slate-500">{t("Email", "البريد")}: </span>
              <strong className="text-slate-900">
                {b.primary_email ||
                  b.contacts?.find((c) => c.contact_type === "business_email")
                    ?.contact_value ||
                  "—"}
              </strong>
              {!b.primary_email && b.website_url ? (
                <span className="ms-2 text-xs text-amber-700">
                  {t("(run Enrich)", "(شغّل Enrich)")}
                </span>
              ) : null}
            </p>
            <p>
              <span className="text-slate-500">{t("Website", "الموقع")}: </span>
              {b.website_url ? (
                <a
                  href={b.website_url}
                  target="_blank"
                  rel="noreferrer"
                  className="break-all text-teal-700 hover:underline"
                >
                  {b.website_url}
                </a>
              ) : (
                "—"
              )}
            </p>
            <p>
              <span className="text-slate-500">{t("Address", "العنوان")}: </span>
              {b.address || "—"}
            </p>
            <p>
              <span className="text-slate-500">{t("District", "الحي")}: </span>
              {b.district || "—"}
            </p>
            <p className="text-slate-500">
              {t("Last enriched", "آخر إثراء")}:{" "}
              {b.last_enriched_at
                ? new Date(b.last_enriched_at).toLocaleString()
                : "—"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h3 className="font-semibold">{t("Actions", "إجراءات")}</h3>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button
              className="w-full"
              disabled={scoreMut.isPending}
              onClick={() => scoreMut.mutate()}
            >
              {t("Rescore lead", "إعادة التقييم")}
            </Button>
            <Button
              className="w-full"
              variant="secondary"
              disabled={enrichMut.isPending}
              onClick={() => enrichMut.mutate()}
            >
              {t("Enrich", "إثراء")}
            </Button>
            <div className="flex gap-2">
              <Select
                value={nextStatus}
                onChange={(e) => setNextStatus(e.target.value)}
              >
                {TRANSITIONS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </Select>
              <Button
                variant="outline"
                disabled={transitionMut.isPending}
                onClick={() => transitionMut.mutate()}
              >
                {t("Move", "نقل")}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h3 className="font-semibold">
              {t("Consent eligibility", "أهلية الموافقة")}
            </h3>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p>
              {eligibility.data?.eligible
                ? t("Eligible for email marketing", "مؤهل للتسويق عبر البريد")
                : t("Not eligible", "غير مؤهل")}
            </p>
            <ul className="list-disc ps-5 text-slate-600">
              {(eligibility.data?.reasons || []).map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
            <p className="pt-2 text-slate-500">
              {t("Consent records", "سجلات الموافقة")}:{" "}
              {(consent.data || []).length}
            </p>
            {(consent.data || []).slice(0, 3).map((c) => (
              <p key={c.id} className="text-xs text-slate-500">
                {c.channel} · {c.purpose} · {c.consent_status}
              </p>
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <h3 className="font-semibold">
              {t("Sales opportunities", "فرص البيع")}
            </h3>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p>
              {details.has_website || b.website_url
                ? t("Has website", "لديه موقع")
                : t("No website — pitch site build", "بدون موقع — اعرض بناء موقع")}
              {details.website_domain ? (
                <span className="text-slate-500"> · {details.website_domain}</span>
              ) : null}
            </p>
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs">
                {details.has_phone
                  ? t("Phone available", "هاتف متوفر")
                  : t("No phone", "لا هاتف")}
              </span>
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs">
                {details.has_email
                  ? t("Email available", "بريد متوفر")
                  : t("No email", "لا بريد")}
              </span>
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs">
                {details.delivery_ready
                  ? t("Delivery ready", "جاهز للتوصيل")
                  : t("Not delivery ready", "غير جاهز للتوصيل")}
              </span>
            </div>
            <ul className="flex flex-wrap gap-2">
              {packs.map((pack) => (
                <li
                  key={pack}
                  className="rounded-full bg-amber-50 px-2.5 py-1 text-xs text-amber-900"
                >
                  {t(
                    PACK_LABELS[pack]?.en || pack.replaceAll("_", " "),
                    PACK_LABELS[pack]?.ar || pack.replaceAll("_", " "),
                  )}
                </li>
              ))}
              {!packs.length ? (
                <li className="text-xs text-slate-500">
                  {t("No packs yet — rescore the lead.", "لا عروض بعد — أعد التقييم.")}
                </li>
              ) : null}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-3">
            <h3 className="font-semibold">{t("Score breakdown", "تفصيل النقاط")}</h3>
            <span className="rounded-full bg-teal-700 px-3 py-1 text-sm font-semibold text-white">
              {totalScore}/100
            </span>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="space-y-2">
              {Object.entries(components).map(([key, value]) => {
                const label = COMPONENT_LABELS[key];
                return (
                  <div key={key} className="flex items-center justify-between gap-3">
                    <span className="text-slate-600">
                      {label ? t(label.en, label.ar) : key.replaceAll("_", " ")}
                    </span>
                    <span className="font-medium text-slate-900">{value}</span>
                  </div>
                );
              })}
              {!Object.keys(components).length ? (
                <p className="text-slate-500">
                  {t("No score yet — click Rescore.", "لا نقاط بعد — اضغط إعادة التقييم.")}
                </p>
              ) : null}
            </div>

            <div className="grid gap-2 rounded-xl bg-slate-50 p-3 text-slate-700 sm:grid-cols-2">
              <p>
                <span className="text-slate-500">{t("Category", "التصنيف")}: </span>
                {details.category_slug || "—"}
              </p>
              <p>
                <span className="text-slate-500">{t("Contact quality", "جودة التواصل")}: </span>
                {(details.contact_quality || "—").replaceAll("_", " ")}
              </p>
              <p>
                <span className="text-slate-500">{t("Website", "الموقع")}: </span>
                {details.has_website ? t("Yes", "نعم") : t("No", "لا")}
              </p>
              <p>
                <span className="text-slate-500">{t("Phone / Email", "هاتف / بريد")}: </span>
                {details.has_phone ? t("Phone", "هاتف") : "—"}
                {" / "}
                {details.has_email ? t("Email", "بريد") : "—"}
              </p>
            </div>

            {reason.scored_at ? (
              <p className="text-xs text-slate-400">
                {t("Scored at", "وقت التقييم")}:{" "}
                {new Date(reason.scored_at).toLocaleString()}
              </p>
            ) : null}
            <p className="text-xs text-slate-400">
              {t(
                "Consent is separate from scoring — check eligibility above.",
                "الموافقة منفصلة عن النقاط — راجع الأهلية أعلاه.",
              )}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
