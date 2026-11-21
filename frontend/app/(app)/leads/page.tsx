"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/status-badge";
import { useLocale } from "@/components/locale-provider";
import { businessesApi } from "@/services/api";

const STATUSES = [
  "",
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

export default function LeadsPage() {
  const { t } = useLocale();
  const [search, setSearch] = useState("");
  const [leadStatus, setLeadStatus] = useState("");
  const [minScore, setMinScore] = useState("");
  const [websiteFilter, setWebsiteFilter] = useState("");
  const [page, setPage] = useState(1);

  const leads = useQuery({
    queryKey: ["leads", search, leadStatus, minScore, websiteFilter, page],
    queryFn: () =>
      businessesApi.list({
        page,
        limit: 20,
        search: search || undefined,
        lead_status: leadStatus || undefined,
        minimum_score: minScore ? Number(minScore) : undefined,
        has_website:
          websiteFilter === "yes"
            ? true
            : websiteFilter === "no"
              ? false
              : undefined,
      }),
  });

  const total = leads.data?.meta?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / 20));

  return (
    <div>
      <PageHeader
        title={t("Leads", "العملاء")}
        description={t(
          "Search, filter, and open merchant leads for enrichment and outreach.",
          "ابحث وصفِّ وافتح عملاء التجار للإثراء والتواصل.",
        )}
      />

      <Card className="mb-4">
        <CardContent className="grid gap-3 pt-5 md:grid-cols-5">
          <Input
            placeholder={t("Search businesses…", "ابحث عن نشاط…")}
            value={search}
            onChange={(e) => {
              setPage(1);
              setSearch(e.target.value);
            }}
          />
          <Select
            value={leadStatus}
            onChange={(e) => {
              setPage(1);
              setLeadStatus(e.target.value);
            }}
          >
            {STATUSES.map((s) => (
              <option key={s || "all"} value={s}>
                {s || t("All statuses", "كل الحالات")}
              </option>
            ))}
          </Select>
          <Select
            value={websiteFilter}
            onChange={(e) => {
              setPage(1);
              setWebsiteFilter(e.target.value);
            }}
          >
            <option value="">{t("Any website", "أي موقع")}</option>
            <option value="yes">{t("Has website", "لديه موقع")}</option>
            <option value="no">{t("No website (pitch)", "بدون موقع")}</option>
          </Select>
          <Input
            type="number"
            min={0}
            max={100}
            placeholder={t("Min score", "الحد الأدنى للنقاط")}
            value={minScore}
            onChange={(e) => {
              setPage(1);
              setMinScore(e.target.value);
            }}
          />
          <p className="flex items-center text-sm text-slate-500">
            {total} {t("results", "نتيجة")}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="overflow-x-auto pt-5">
          <table className="w-full min-w-[800px] text-left text-sm">
            <thead className="text-xs uppercase text-slate-500">
              <tr>
                <th className="pb-3 font-medium">{t("Business", "النشاط")}</th>
                <th className="pb-3 font-medium">{t("Status", "الحالة")}</th>
                <th className="pb-3 font-medium">{t("Score", "النقاط")}</th>
                <th className="pb-3 font-medium">{t("Contact", "التواصل")}</th>
                <th className="pb-3 font-medium">{t("Updated", "حدّث")}</th>
              </tr>
            </thead>
            <tbody>
              {(leads.data?.data || []).map((b) => (
                <tr key={b.id} className="border-t border-slate-100">
                  <td className="py-3">
                    <Link
                      href={`/leads/${b.id}`}
                      className="font-medium text-teal-800 hover:underline"
                    >
                      {b.business_name}
                    </Link>
                    {b.business_name_ar ? (
                      <p className="text-xs text-slate-500">{b.business_name_ar}</p>
                    ) : null}
                  </td>
                  <td className="py-3">
                    <StatusBadge status={b.lead_status} />
                  </td>
                  <td className="py-3 font-medium">{b.qualification_score}</td>
                  <td className="py-3 text-slate-600">
                    <div className="max-w-[220px] truncate" title={b.website_url || undefined}>
                      {b.website_url || t("No website", "بدون موقع")}
                    </div>
                    <p className="text-xs text-slate-400">
                      {b.has_phone ? "phone ✓" : "phone —"}
                      {" · "}
                      {b.has_email ? "email ✓" : "email —"}
                    </p>
                  </td>
                  <td className="py-3 text-slate-500">
                    {new Date(b.updated_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!leads.data?.data?.length ? (
            <p className="py-8 text-center text-sm text-slate-500">
              {t("No leads match these filters.", "لا عملاء مطابقون لهذه الفلاتر.")}
            </p>
          ) : null}
          <div className="mt-4 flex items-center justify-between">
            <button
              className="text-sm text-teal-700 disabled:opacity-40"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              {t("Previous", "السابق")}
            </button>
            <span className="text-sm text-slate-500">
              {page} / {pages}
            </span>
            <button
              className="text-sm text-teal-700 disabled:opacity-40"
              disabled={page >= pages}
              onClick={() => setPage((p) => p + 1)}
            >
              {t("Next", "التالي")}
            </button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
