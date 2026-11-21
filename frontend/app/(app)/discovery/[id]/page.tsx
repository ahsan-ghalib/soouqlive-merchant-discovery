"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { StatusBadge } from "@/components/status-badge";
import { discoveryApi } from "@/services/api";
import { formatNumber } from "@/lib/utils";
import { useLocale } from "@/components/locale-provider";

export default function DiscoveryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useLocale();

  const job = useQuery({
    queryKey: ["discovery-job", id],
    queryFn: () => discoveryApi.get(id),
    refetchInterval: 4000,
  });
  const results = useQuery({
    queryKey: ["discovery-results", id],
    queryFn: () => discoveryApi.results(id, { page: 1, limit: 50 }),
    refetchInterval: 5000,
  });

  if (job.isLoading) {
    return <p className="text-slate-500">{t("Loading…", "جارٍ التحميل…")}</p>;
  }
  if (!job.data) {
    return <p className="text-rose-600">{t("Job not found", "المهمة غير موجودة")}</p>;
  }

  const j = job.data;

  return (
    <div>
      <PageHeader
        title={j.name}
        description={`${j.search_keyword} · ${j.status}`}
        actions={<StatusBadge status={j.status} />}
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {[
          ["Expected", j.total_expected],
          ["Processed", j.total_processed],
          ["Created", j.total_created],
          ["Duplicates", j.total_duplicates],
          ["Failed", j.total_failed],
        ].map(([label, value]) => (
          <Card key={String(label)}>
            <CardContent className="pt-5">
              <p className="text-sm text-slate-500">{String(label)}</p>
              <p className="mt-1 text-2xl font-semibold">
                {formatNumber(Number(value))}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <h3 className="font-semibold">{t("Results", "النتائج")}</h3>
        </CardHeader>
        <CardContent className="space-y-2">
          {(results.data?.data || []).map((b) => (
            <Link
              key={b.id}
              href={`/leads/${b.id}`}
              className="flex items-center justify-between rounded-xl border border-slate-100 px-3 py-2.5 hover:bg-slate-50"
            >
              <div>
                <p className="font-medium">{b.business_name}</p>
                <p className="text-xs text-slate-500">
                  {b.website_url || "—"} · score {b.qualification_score}
                </p>
              </div>
              <StatusBadge status={b.lead_status} />
            </Link>
          ))}
          {!results.data?.data?.length ? (
            <p className="text-sm text-slate-500">
              {t("No results yet.", "لا نتائج بعد.")}
            </p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
