"use client";

import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { useLocale } from "@/components/locale-provider";
import { taxonomyApi } from "@/services/api";

export default function LocationsPage() {
  const { t, locale } = useLocale();

  const countries = useQuery({
    queryKey: ["countries"],
    queryFn: () => taxonomyApi.countries(),
  });
  const cities = useQuery({
    queryKey: ["cities"],
    queryFn: () => taxonomyApi.cities(),
  });
  const districts = useQuery({
    queryKey: ["districts"],
    queryFn: () => taxonomyApi.districts(),
  });

  return (
    <div>
      <PageHeader
        title={t("Locations", "المواقع")}
        description={t(
          "Saudi geography hierarchy for discovery scoping.",
          "التسلسل الجغرافي السعودي لنطاق الاكتشاف.",
        )}
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <h3 className="font-semibold">{t("Countries", "الدول")}</h3>
          </CardHeader>
          <CardContent className="space-y-2">
            {(countries.data || []).map((c) => (
              <div key={c.id} className="rounded-lg border border-slate-100 px-3 py-2">
                <p className="font-medium">
                  {locale === "ar" ? c.name_ar || c.name : c.name}
                </p>
                <p className="text-xs text-slate-500">
                  {c.iso_code} {c.phone_code || ""}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h3 className="font-semibold">{t("Cities", "المدن")}</h3>
          </CardHeader>
          <CardContent className="max-h-[480px] space-y-2 overflow-y-auto">
            {(cities.data || []).map((c) => (
              <div key={c.id} className="rounded-lg border border-slate-100 px-3 py-2">
                <p className="font-medium">
                  {locale === "ar" ? c.name_ar || c.name : c.name}
                </p>
                <p className="text-xs text-slate-500">{c.slug}</p>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h3 className="font-semibold">{t("Districts", "الأحياء")}</h3>
          </CardHeader>
          <CardContent className="max-h-[480px] space-y-2 overflow-y-auto">
            {(districts.data || []).map((d) => (
              <div key={d.id} className="rounded-lg border border-slate-100 px-3 py-2">
                <p className="font-medium">
                  {locale === "ar" ? d.name_ar || d.name : d.name}
                </p>
                <p className="text-xs text-slate-500">{d.slug}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
