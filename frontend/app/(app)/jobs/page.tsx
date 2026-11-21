"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Select } from "@/components/ui/select";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { StatusBadge } from "@/components/status-badge";
import { useLocale } from "@/components/locale-provider";
import { jobsApi } from "@/services/api";
import { formatNumber } from "@/lib/utils";

export default function JobsPage() {
  const { t } = useLocale();
  const [jobType, setJobType] = useState("discovery");
  const [status, setStatus] = useState("");

  const jobs = useQuery({
    queryKey: ["jobs", jobType, status],
    queryFn: () =>
      jobsApi.list({
        page: 1,
        limit: 50,
        job_type: jobType,
        status: status || undefined,
      }),
    refetchInterval: 5000,
  });

  const queue = useQuery({
    queryKey: ["queue-stats"],
    queryFn: () => jobsApi.queueStats(),
    refetchInterval: 5000,
  });

  return (
    <div>
      <PageHeader
        title={t("Jobs", "المهام")}
        description={t(
          "Monitor discovery and enrichment workers across queues.",
          "راقب عمّال الاكتشاف والإثراء عبر الطوابير.",
        )}
      />

      <div className="mb-6 grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <h3 className="font-semibold">{t("Queue stats", "إحصاءات الطابور")}</h3>
          </CardHeader>
          <CardContent>
            <pre className="overflow-x-auto rounded-xl bg-slate-950 p-4 text-xs text-emerald-200">
              {JSON.stringify(queue.data || {}, null, 2)}
            </pre>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <h3 className="font-semibold">{t("Filters", "فلاتر")}</h3>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            <Select value={jobType} onChange={(e) => setJobType(e.target.value)}>
              <option value="discovery">discovery</option>
              <option value="enrichment">enrichment</option>
            </Select>
            <Select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">{t("All statuses", "كل الحالات")}</option>
              {[
                "pending",
                "queued",
                "processing",
                "completed",
                "failed",
                "cancelled",
                "paused",
              ].map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardContent className="overflow-x-auto pt-5">
          <table className="w-full min-w-[700px] text-left text-sm">
            <thead className="text-xs uppercase text-slate-500">
              <tr>
                <th className="pb-3 font-medium">ID / Name</th>
                <th className="pb-3 font-medium">{t("Status", "الحالة")}</th>
                <th className="pb-3 font-medium">{t("Progress", "التقدم")}</th>
                <th className="pb-3 font-medium">{t("Created", "أُنشئت")}</th>
              </tr>
            </thead>
            <tbody>
              {(jobs.data?.data || []).map((j) => (
                <tr key={j.id} className="border-t border-slate-100">
                  <td className="py-3">
                    <p className="font-medium">{j.name || j.job_type || j.job_family}</p>
                    <p className="font-mono text-xs text-slate-400">{j.id}</p>
                  </td>
                  <td className="py-3">
                    <StatusBadge status={j.status} />
                  </td>
                  <td className="py-3 text-slate-600">
                    {j.total_processed != null
                      ? `${formatNumber(j.total_processed)}/${formatNumber(j.total_expected || 0)}`
                      : j.attempts != null
                        ? `attempts ${j.attempts}`
                        : "—"}
                  </td>
                  <td className="py-3 text-slate-500">
                    {j.created_at
                      ? new Date(j.created_at).toLocaleString()
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!jobs.data?.data?.length ? (
            <p className="py-8 text-center text-sm text-slate-500">
              {t("No jobs in this view.", "لا مهام في هذا العرض.")}
            </p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
