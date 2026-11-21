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
import { StatusBadge } from "@/components/status-badge";
import Link from "next/link";

export default function DashboardPage() {
  const { t } = useLocale();

  const pipeline = useQuery({
    queryKey: ["pipeline"],
    queryFn: () => crmApi.pipeline(),
  });
  const businesses = useQuery({
    queryKey: ["businesses-summary"],
    queryFn: () => businessesApi.list({ page: 1, limit: 5 }),
  });
  const discovery = useQuery({
    queryKey: ["discovery-summary"],
    queryFn: () => discoveryApi.list({ page: 1, limit: 5 }),
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

  const totalLeads = businesses.data?.meta?.total ?? 0;
  const discoveryJobs = discovery.data?.meta?.total ?? 0;

  return (
    <div>
      <PageHeader
        title={t("Dashboard", "لوحة التحكم")}
        description={t(
          "Pipeline health, recent discovery, and queue pressure at a glance.",
          "صحة المسار وآخر الاكتشافات وحالة الطوابير بنظرة واحدة.",
        )}
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { label: t("Total leads", "إجمالي العملاء"), value: totalLeads },
          { label: t("Discovery jobs", "مهام الاكتشاف"), value: discoveryJobs },
          {
            label: t("Qualified", "مؤهلون"),
            value: pipeline.data?.qualified_count ?? byStatus.qualified ?? 0,
          },
          {
            label: t("Processing queue", "قيد المعالجة"),
            value:
              (queue.data?.discovery as Record<string, number> | undefined)
                ?.processing ?? 0,
          },
        ].map((stat) => (
          <Card key={stat.label}>
            <CardContent className="pt-5">
              <p className="text-sm text-slate-500">{stat.label}</p>
              <p className="mt-2 font-[family-name:var(--font-display)] text-3xl font-semibold text-slate-900">
                {formatNumber(Number(stat.value))}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <h3 className="font-semibold text-slate-900">
              {t("Lead pipeline", "مسار العملاء")}
            </h3>
          </CardHeader>
          <CardContent className="h-72">
            {chartData.length ? (
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
            ) : (
              <p className="text-sm text-slate-500">
                {t("No pipeline data yet.", "لا توجد بيانات مسار بعد.")}
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <h3 className="font-semibold text-slate-900">
              {t("Recent leads", "أحدث العملاء")}
            </h3>
            <Link href="/leads" className="text-sm text-teal-700 hover:underline">
              {t("View all", "عرض الكل")}
            </Link>
          </CardHeader>
          <CardContent className="space-y-3">
            {(businesses.data?.data || []).map((b) => (
              <Link
                key={b.id}
                href={`/leads/${b.id}`}
                className="flex items-center justify-between rounded-xl border border-slate-100 px-3 py-2.5 hover:bg-slate-50"
              >
                <div>
                  <p className="font-medium text-slate-900">{b.business_name}</p>
                  <p className="text-xs text-slate-500">
                    score {b.qualification_score}
                  </p>
                </div>
                <StatusBadge status={b.lead_status} />
              </Link>
            ))}
            {!businesses.data?.data?.length ? (
              <p className="text-sm text-slate-500">
                {t("No leads yet. Start a discovery job.", "لا عملاء بعد. ابدأ مهمة اكتشاف.")}
              </p>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
