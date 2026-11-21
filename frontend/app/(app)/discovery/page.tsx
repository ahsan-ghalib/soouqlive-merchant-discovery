"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { StatusBadge } from "@/components/status-badge";
import { useLocale } from "@/components/locale-provider";
import { discoveryApi, providersApi, taxonomyApi } from "@/services/api";
import { formatNumber } from "@/lib/utils";

const DISCOVERY_PROVIDERS = new Set([
  "licensed_directory",
  "places_api",
  "manual_import",
]);

const PROVIDER_HELP: Record<string, { en: string; ar: string }> = {
  places_api: {
    en: "Paid Google Places → creates candidates (name, phone, website, category, place_id). Email comes after website enrich.",
    ar: "Places المدفوع → مرشحون (اسم، هاتف، موقع، تصنيف، place_id). البريد بعد إثراء الموقع.",
  },
  licensed_directory: {
    en: "Licensed directory API → full CRM leads when credentials are set.",
    ar: "دليل مرخّص → عملاء كاملون عند ضبط المفاتيح.",
  },
  manual_import: {
    en: "Use bulk import API for CSV/JSON; discovery search needs preloaded rows.",
    ar: "للاستيراد استخدم bulk-import؛ البحث يحتاج صفوفاً محملة مسبقاً.",
  },
};

const SCRAPE_CATEGORIES = [
  { value: "all", en: "All businesses", ar: "كل الأعمال" },
  { value: "restaurants", en: "Restaurants", ar: "مطاعم" },
  { value: "cafes", en: "Cafes", ar: "مقاهي" },
  { value: "pharmacies", en: "Pharmacies", ar: "صيدليات" },
  { value: "real-estate", en: "Real estate", ar: "عقارات" },
];

export default function DiscoveryPage() {
  const { t } = useLocale();
  const qc = useQueryClient();
  const [name, setName] = useState("Riyadh restaurants Places");
  const [city, setCity] = useState("Riyadh");
  const [keyword, setKeyword] = useState("restaurant");
  const [provider, setProvider] = useState("places_api");
  const [limit, setLimit] = useState(100);
  const [categoryId, setCategoryId] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [sweepMode, setSweepMode] = useState("districts");
  const [countryId, setCountryId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [countryCode, setCountryCode] = useState("SA");
  const [scrapeCategory, setScrapeCategory] = useState("restaurants");

  const jobs = useQuery({
    queryKey: ["discovery-jobs"],
    queryFn: () => discoveryApi.list({ page: 1, limit: 100 }),
    refetchInterval: 5000,
  });
  const providers = useQuery({
    queryKey: ["providers"],
    queryFn: () => providersApi.list(),
  });
  const categories = useQuery({
    queryKey: ["categories"],
    queryFn: () => taxonomyApi.categories(),
  });
  const countries = useQuery({
    queryKey: ["countries"],
    queryFn: () => taxonomyApi.countries(),
  });
  const cities = useQuery({
    queryKey: ["cities", countryId],
    queryFn: () => taxonomyApi.cities(countryId || undefined),
    enabled: true,
  });

  useEffect(() => {
    if (!countryId && countries.data?.length) {
      const sa =
        countries.data.find((c) => c.iso_code === "SA") || countries.data[0];
      setCountryId(sa.id);
      setCountryCode(sa.iso_code || "SA");
    }
  }, [countries.data, countryId]);

  useEffect(() => {
    if (!locationId && cities.data?.length) {
      const riyadh =
        cities.data.find((c) => c.slug === "riyadh" || c.name === "Riyadh") ||
        cities.data[0];
      setLocationId(riyadh.id);
      setCity(riyadh.name);
    }
  }, [cities.data, locationId]);

  const adapterKeys = useMemo(() => {
    const keys = providers.data?.adapter_keys || [
      "places_api",
      "licensed_directory",
      "manual_import",
    ];
    return keys.filter((k) => DISCOVERY_PROVIDERS.has(k));
  }, [providers.data]);

  const help = PROVIDER_HELP[provider];
  const selectedCity = cities.data?.find((c) => c.id === locationId);

  const create = useMutation({
    mutationFn: () =>
      discoveryApi.create({
        name,
        city,
        country_code: countryCode,
        country_id: countryId || null,
        location_id: locationId || null,
        provider,
        keywords: [keyword],
        search_keyword: keyword,
        limit,
        category_id: categoryId || null,
        language: "both",
      }),
    onSuccess: async (job) => {
      setMessage(`Created ${job.name}`);
      await qc.invalidateQueries({ queryKey: ["discovery-jobs"] });
    },
    onError: (err: Error) => setMessage(err.message),
  });

  const cityScrape = useMutation({
    mutationFn: () =>
      discoveryApi.cityScrape({
        name: `Full city scrape — ${city}`,
        city,
        country_code: countryCode,
        country_id: countryId || null,
        location_id: locationId || null,
        category: scrapeCategory,
        provider: "places_api",
        limit_per_query: 60,
        max_queries:
          scrapeCategory === "restaurants" || scrapeCategory === "cafes"
            ? 250
            : 100,
        grid:
          scrapeCategory === "restaurants" || scrapeCategory === "cafes" ? 7 : 5,
        auto_start: true,
        language: "en",
        latitude: selectedCity?.latitude ?? null,
        longitude: selectedCity?.longitude ?? null,
      }),
    onSuccess: async (data) => {
      setMessage(
        `City scrape started: ${data.queries_planned} Places queries, ~${data.total_expected} expected. ${data.note || ""}`,
      );
      await qc.invalidateQueries({ queryKey: ["discovery-jobs"] });
    },
    onError: (err: Error) => setMessage(err.message),
  });

  const sweep = useMutation({
    mutationFn: () =>
      discoveryApi.coverageSweep({
        city,
        category: "restaurants",
        provider: "places_api",
        mode: sweepMode,
        limit_per_query: 60,
        auto_start: true,
        max_jobs: sweepMode === "full" ? 40 : 24,
        language: "en",
        country_code: countryCode,
      }),
    onSuccess: async (data) => {
      setMessage(
        `Coverage sweep: ${data.jobs_created} jobs created, ${data.jobs_started} started. ${data.note || ""}`,
      );
      await qc.invalidateQueries({ queryKey: ["discovery-jobs"] });
    },
    onError: (err: Error) => setMessage(err.message),
  });

  const action = useMutation({
    mutationFn: async ({
      id,
      op,
    }: {
      id: string;
      op: "start" | "pause" | "cancel" | "retry";
    }) => {
      if (op === "start") return discoveryApi.start(id);
      if (op === "pause") return discoveryApi.pause(id);
      if (op === "cancel") return discoveryApi.cancel(id);
      return discoveryApi.retry(id);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["discovery-jobs"] }),
    onError: (err: Error) => setMessage(err.message),
  });

  return (
    <div>
      <PageHeader
        title={t("Discovery", "الاكتشاف")}
        description={t(
          "Pick any country/city and run a full Places scrape — one job covers districts, keywords, and a geo grid.",
          "اختر أي دولة/مدينة وشغّل مسحاً كاملاً عبر Places — مهمة واحدة تغطي الأحياء والكلمات والشبكة الجغرافية.",
        )}
      />

      <div className="grid gap-6 xl:grid-cols-[360px_1fr]">
        <Card>
          <CardHeader>
            <h3 className="font-semibold">
              {t("Full city scrape", "مسح المدينة الكامل")}
            </h3>
          </CardHeader>
          <CardContent className="space-y-3">
            <Select
              value={countryId}
              onChange={(e) => {
                const id = e.target.value;
                setCountryId(id);
                setLocationId("");
                const c = countries.data?.find((x) => x.id === id);
                if (c?.iso_code) setCountryCode(c.iso_code);
              }}
            >
              <option value="">{t("Select country", "اختر الدولة")}</option>
              {(countries.data || []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.iso_code})
                </option>
              ))}
            </Select>
            {(cities.data || []).length > 0 ? (
              <Select
                value={locationId}
                onChange={(e) => {
                  const id = e.target.value;
                  setLocationId(id);
                  const c = cities.data?.find((x) => x.id === id);
                  if (c) setCity(c.name);
                }}
              >
                <option value="">{t("Select city", "اختر المدينة")}</option>
                {(cities.data || []).map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
            ) : null}
            <Input
              placeholder={t("City name (any city)", "اسم المدينة (أي مدينة)")}
              value={city}
              onChange={(e) => {
                setCity(e.target.value);
                setLocationId("");
              }}
            />
            <Select
              value={scrapeCategory}
              onChange={(e) => setScrapeCategory(e.target.value)}
            >
              {SCRAPE_CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {t(c.en, c.ar)}
                </option>
              ))}
            </Select>
            <Button
              className="w-full"
              disabled={
                cityScrape.isPending || !city || provider !== "places_api"
              }
              onClick={() => {
                setProvider("places_api");
                cityScrape.mutate();
              }}
            >
              {cityScrape.isPending
                ? t("Scraping city…", "جارٍ مسح المدينة…")
                : t("Start full city scrape", "بدء مسح المدينة الكامل")}
            </Button>
            <p className="text-xs text-slate-500">
              {t(
                "One job: districts + business keywords + geo-grid. Dedupes by place_id. Uses Places quota.",
                "مهمة واحدة: أحياء + كلمات أعمال + شبكة جغرافية. دمج بـ place_id. يستهلك حصة Places.",
              )}
            </p>

            <div className="border-t border-slate-100 pt-3">
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
                {t("Single query job", "مهمة استعلام واحد")}
              </p>
              <Input
                placeholder={t("Job name", "اسم المهمة")}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <Input
                className="mt-2"
                placeholder={t("Keyword (e.g. restaurant)", "كلمة مفتاحية")}
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
              />
              <Select
                className="mt-2"
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
              >
                {adapterKeys.map((key) => (
                  <option key={key} value={key}>
                    {key}
                  </option>
                ))}
              </Select>
              {help ? (
                <p className="mt-2 rounded-lg bg-teal-50 px-3 py-2 text-xs text-teal-900">
                  {t(help.en, help.ar)}
                </p>
              ) : null}
              <Select
                className="mt-2"
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
              >
                <option value="">{t("Any category", "أي تصنيف")}</option>
                {(categories.data || []).map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
              <Input
                className="mt-2"
                type="number"
                min={1}
                max={1000}
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
              />
              <Button
                className="mt-2 w-full"
                variant="secondary"
                disabled={create.isPending}
                onClick={() => create.mutate()}
              >
                {create.isPending
                  ? t("Creating…", "جارٍ الإنشاء…")
                  : t("Create single job", "إنشاء مهمة واحدة")}
              </Button>
            </div>

            <div className="border-t border-slate-100 pt-3">
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-teal-800">
                {t("Multi-job sweep (legacy)", "مسح متعدد المهام")}
              </p>
              <Select
                value={sweepMode}
                onChange={(e) => setSweepMode(e.target.value)}
              >
                <option value="districts">
                  {t("Districts", "أحياء")}
                </option>
                <option value="cuisines">
                  {t("Cuisines city-wide", "مطابخ على مستوى المدينة")}
                </option>
                <option value="full">
                  {t("Full (districts + cuisines)", "كامل (أحياء + مطابخ)")}
                </option>
              </Select>
              <Button
                className="mt-2 w-full"
                variant="outline"
                disabled={sweep.isPending || provider !== "places_api"}
                onClick={() => sweep.mutate()}
              >
                {sweep.isPending
                  ? t("Launching sweep…", "جارٍ تشغيل المسح…")
                  : t("Launch multi-job sweep", "تشغيل مسح متعدد")}
              </Button>
            </div>

            {message ? (
              <p className="text-sm text-slate-600">{message}</p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h3 className="font-semibold">{t("Jobs", "المهام")}</h3>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="text-xs uppercase text-slate-500">
                <tr>
                  <th className="pb-3 font-medium">{t("Name", "الاسم")}</th>
                  <th className="pb-3 font-medium">{t("Status", "الحالة")}</th>
                  <th className="pb-3 font-medium">{t("Progress", "التقدم")}</th>
                  <th className="pb-3 font-medium">{t("Created", "أُنشئت")}</th>
                  <th className="pb-3 font-medium">{t("Actions", "إجراءات")}</th>
                </tr>
              </thead>
              <tbody>
                {(jobs.data?.data || []).map((job) => (
                  <tr key={job.id} className="border-t border-slate-100">
                    <td className="py-3">
                      <Link
                        href={`/discovery/${job.id}`}
                        className="font-medium text-teal-800 hover:underline"
                      >
                        {job.name}
                      </Link>
                      <p className="text-xs text-slate-500">{job.search_keyword}</p>
                    </td>
                    <td className="py-3">
                      <StatusBadge status={job.status} />
                    </td>
                    <td className="py-3 text-slate-600">
                      {formatNumber(job.total_processed)}/
                      {formatNumber(job.total_expected)} · +
                      {formatNumber(job.total_created)} new
                    </td>
                    <td className="py-3 text-slate-500">
                      {new Date(job.created_at).toLocaleString()}
                    </td>
                    <td className="py-3">
                      <div className="flex flex-wrap gap-1">
                        {["start", "pause", "cancel", "retry"].map((op) => (
                          <Button
                            key={op}
                            size="sm"
                            variant="outline"
                            disabled={action.isPending}
                            onClick={() =>
                              action.mutate({
                                id: job.id,
                                op: op as "start" | "pause" | "cancel" | "retry",
                              })
                            }
                          >
                            {op}
                          </Button>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!jobs.data?.data?.length ? (
              <p className="py-8 text-center text-sm text-slate-500">
                {t("No discovery jobs yet.", "لا مهام اكتشاف بعد.")}
              </p>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
