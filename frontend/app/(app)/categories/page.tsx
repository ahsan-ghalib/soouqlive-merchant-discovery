"use client";

import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { useLocale } from "@/components/locale-provider";
import { taxonomyApi } from "@/services/api";

export default function CategoriesPage() {
  const { t, locale } = useLocale();
  const categories = useQuery({
    queryKey: ["categories"],
    queryFn: () => taxonomyApi.categories(),
  });

  return (
    <div>
      <PageHeader
        title={t("Categories", "التصنيفات")}
        description={t(
          "Business taxonomy used for discovery targeting and filters.",
          "تصنيف الأنشطة المستخدم لاستهداف الاكتشاف والفلاتر.",
        )}
      />
      <Card>
        <CardContent className="grid gap-2 pt-5 sm:grid-cols-2 lg:grid-cols-3">
          {(categories.data || []).map((c) => (
            <div
              key={c.id}
              className="rounded-xl border border-slate-100 px-4 py-3"
            >
              <p className="font-medium text-slate-900">
                {locale === "ar" ? c.name_ar || c.name : c.name}
              </p>
              <p className="text-xs text-slate-500">{c.slug}</p>
            </div>
          ))}
          {!categories.data?.length ? (
            <p className="text-sm text-slate-500">
              {t("No categories seeded.", "لا تصنيفات بعد.")}
            </p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
