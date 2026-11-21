"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { useLocale } from "@/components/locale-provider";
import { businessesApi, crmApi, discoveryApi, jobsApi } from "@/services/api";
import { formatNumber } from "@/lib/utils";

export default function AnalyticsPage() {
  const { t } = useLocale();

  const pipeline = useQuery({
    queryKey: ["pipeline"],
    queryFn: () => crmApi.pipeline(),
  });
  const businesses = useQuery({
    queryKey: ["businesses-count"],
    queryFn: () => businessesApi.list({ page: 1, limit: 1 }),
  });
  const discovery = useQuery({
    queryKey: ["discovery-count"],
    queryFn: () => discoveryApi.list({ page: 1, limit: 1 }),
  });
  const queue = useQuery({
    queryKey: ["queue-stats"],
    queryFn: () => jobsApi.queueStats(),
  });

  const byStatus = pipeline.data?.by_status || {};
  const chartData = Object.entries(byStatus).map(([name, value]) => ({
    name: name.replaceAll("_", " "),
    value: Number(value) || 0,
  }));

  return (
    <div>
      <PageHeader
        title={t("Analytics", "التحليلات")}
        description={t(
          "Operational metrics from pipeline, discovery, and queues.",
          "مقاييس تشغيلية من المسار والاكتشاف والطوابير.",
        )}
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="pt-5">
            <p className="text-sm text-slate-500">{t("Leads", "العملاء")}</p>
            <p className="mt-1 text-3xl font-semibold">
              {formatNumber(businesses.data?.meta?.total ?? 0)}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5">
            <p className="text-sm text-slate-500">
              {t("Discovery jobs", "مهام الاكتشاف")}
            </p>
            <p className="mt-1 text-3xl font-semibold">
              {formatNumber(discovery.data?.meta?.total ?? 0)}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5">
            <p className="text-sm text-slate-500">{t("Qualified", "مؤهلون")}</p>
            <p className="mt-1 text-3xl font-semibold">
              {formatNumber(
                pipeline.data?.qualified_count ?? byStatus.qualified ?? 0,
              )}
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <h3 className="font-semibold">{t("Pipeline", "المسار")}</h3>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} />
                <Tooltip
                  formatter={(value) => [Number(value) || 0, "count"]}
                  labelFormatter={(label) => String(label)}
                />
                <Bar dataKey="value" fill="#0f766e" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <h3 className="font-semibold">{t("Queue snapshot", "لقطة الطابور")}</h3>
          </CardHeader>
          <CardContent>
            <pre className="overflow-x-auto rounded-xl bg-slate-950 p-4 text-xs text-emerald-200">
              {JSON.stringify(queue.data || {}, null, 2)}
            </pre>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
