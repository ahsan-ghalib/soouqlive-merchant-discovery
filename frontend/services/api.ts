import { apiRequest } from "@/lib/api";
import type {
  ApiResponse,
  Business,
  BusinessContact,
  Campaign,
  Category,
  ConsentRecord,
  Country,
  DiscoveryJob,
  EligibilityResult,
  JobRow,
  Location,
  LoginData,
  PipelineSummary,
  Provider,
  ScoreInfo,
  ScoreResult,
  SmtpSettings,
  TokenPair,
  User,
} from "@/types/api";

type Query = Record<string, string | number | boolean | undefined | null>;

async function dataOf<T>(promise: Promise<ApiResponse<T>>): Promise<T> {
  const res = await promise;
  return res.data;
}

export const authApi = {
  login: (email: string, password: string) =>
    dataOf(apiRequest<LoginData>("/auth/login", { body: { email, password }, auth: false })),
  me: () => dataOf(apiRequest<User>("/auth/me")),
  refresh: (refresh_token: string) =>
    dataOf(
      apiRequest<TokenPair>("/auth/refresh", {
        body: { refresh_token },
        auth: false,
      }),
    ),
};

export const taxonomyApi = {
  categories: () => dataOf(apiRequest<Category[]>("/categories")),
  countries: () => dataOf(apiRequest<Country[]>("/locations/countries")),
  cities: (country_id?: string) =>
    dataOf(apiRequest<Location[]>("/locations/cities", { query: { country_id } })),
  districts: (parent_id?: string) =>
    dataOf(apiRequest<Location[]>("/locations/districts", { query: { parent_id } })),
  regions: (country_id?: string) =>
    dataOf(apiRequest<Location[]>("/locations/regions", { query: { country_id } })),
};

export const providersApi = {
  list: () =>
    dataOf(
      apiRequest<{ providers: Provider[]; adapter_keys: string[] }>("/providers"),
    ),
};

export const discoveryApi = {
  create: (body: Record<string, unknown>) =>
    dataOf(apiRequest<DiscoveryJob>("/discovery/jobs", { body })),
  list: (query?: Query) =>
    apiRequest<DiscoveryJob[]>("/discovery/jobs", { query }),
  get: (id: string) => dataOf(apiRequest<DiscoveryJob>(`/discovery/jobs/${id}`)),
  start: (id: string) =>
    dataOf(apiRequest<DiscoveryJob>(`/discovery/jobs/${id}/start`, { method: "POST" })),
  pause: (id: string) =>
    dataOf(apiRequest<DiscoveryJob>(`/discovery/jobs/${id}/pause`, { method: "POST" })),
  cancel: (id: string) =>
    dataOf(apiRequest<DiscoveryJob>(`/discovery/jobs/${id}/cancel`, { method: "POST" })),
  retry: (id: string) =>
    dataOf(apiRequest<DiscoveryJob>(`/discovery/jobs/${id}/retry`, { method: "POST" })),
  results: (id: string, query?: Query) =>
    apiRequest<Business[]>(`/discovery/jobs/${id}/results`, { query }),
  preview: (body: Record<string, unknown>) =>
    dataOf(apiRequest<Record<string, unknown>>("/discovery/preview", { body })),
  coverageSweep: (body: Record<string, unknown>) =>
    dataOf(
      apiRequest<{
        mode: string;
        city: string;
        jobs_created: number;
        jobs_started: number;
        job_ids: string[];
        note?: string;
      }>("/discovery/coverage-sweep", { body }),
    ),
  cityScrape: (body: Record<string, unknown>) =>
    dataOf(
      apiRequest<{
        mode: string;
        city: string;
        country_code: string;
        category: string;
        queries_planned: number;
        total_expected: number;
        job_id: string;
        auto_started: boolean;
        note?: string;
      }>("/discovery/city-scrape", { body }),
    ),
};

export const businessesApi = {
  list: (query?: Query) => apiRequest<Business[]>("/businesses", { query }),
  get: (id: string) => dataOf(apiRequest<Business>(`/businesses/${id}`)),
  update: (id: string, body: Record<string, unknown>) =>
    dataOf(apiRequest<Business>(`/businesses/${id}`, { method: "PATCH", body })),
  assign: (id: string, assigned_to: string | null) =>
    dataOf(
      apiRequest<Business>(`/businesses/${id}/assign`, {
        body: { assigned_to },
      }),
    ),
  contacts: (id: string) =>
    dataOf(apiRequest<BusinessContact[]>(`/businesses/${id}/contacts`)),
  activities: (id: string, query?: Query) =>
    apiRequest<unknown[]>(`/businesses/${id}/activities`, { query }),
};

export const crmApi = {
  getScore: (id: string) =>
    dataOf(apiRequest<ScoreInfo>(`/crm/businesses/${id}/score`)),
  score: (id: string, body?: { auto_qualify?: boolean; qualify_threshold?: number }) =>
    dataOf(
      apiRequest<ScoreResult>(`/crm/businesses/${id}/score`, {
        body: body ?? { auto_qualify: false },
      }),
    ),
  transition: (id: string, lead_status: string, note?: string) =>
    dataOf(
      apiRequest<Business>(`/crm/businesses/${id}/transition`, {
        body: { lead_status, note },
      }),
    ),
  pipeline: () => dataOf(apiRequest<PipelineSummary>("/crm/leads/pipeline")),
};

export const enrichmentApi = {
  run: (businessId: string) =>
    dataOf(
      apiRequest<{ id: string; status: string }>(
        `/enrichment/businesses/${businessId}/run`,
        { method: "POST" },
      ),
    ),
  results: (businessId: string) =>
    dataOf(apiRequest<unknown>(`/enrichment/businesses/${businessId}/results`)),
};

export const campaignsApi = {
  list: (query?: Query) => apiRequest<Campaign[]>("/campaigns", { query }),
  get: (id: string) => dataOf(apiRequest<Campaign>(`/campaigns/${id}`)),
  create: (body: Record<string, unknown>) =>
    dataOf(apiRequest<Campaign>("/campaigns", { body })),
  update: (id: string, body: Record<string, unknown>) =>
    dataOf(apiRequest<Campaign>(`/campaigns/${id}`, { method: "PATCH", body })),
  addLeads: (id: string, business_ids: string[]) =>
    dataOf(
      apiRequest<Record<string, unknown>>(`/campaigns/${id}/leads`, {
        body: { business_ids },
      }),
    ),
  analytics: (id: string) =>
    dataOf(apiRequest<Record<string, unknown>>(`/campaigns/${id}/analytics`)),
  qualify: (id: string, minimum_score = 60) =>
    dataOf(
      apiRequest<Record<string, unknown>>(`/campaigns/${id}/qualify`, {
        body: { minimum_score, rescore: true },
      }),
    ),
};

export const jobsApi = {
  list: (query?: Query) => apiRequest<JobRow[]>("/jobs", { query }),
  get: (id: string) => dataOf(apiRequest<Record<string, unknown>>(`/jobs/${id}`)),
  queueStats: () => dataOf(apiRequest<Record<string, unknown>>("/jobs/queue/stats")),
  retry: (id: string) =>
    dataOf(apiRequest<Record<string, unknown>>(`/jobs/${id}/retry`, { method: "POST" })),
};

export const consentApi = {
  forBusiness: (businessId: string) =>
    dataOf(apiRequest<ConsentRecord[]>(`/consent/businesses/${businessId}`)),
  checkEligibility: (body: {
    business_id: string;
    purpose: string;
    channel: string;
    contact_id?: string | null;
  }) => dataOf(apiRequest<EligibilityResult>("/consent/check-eligibility", { body })),
};

export const settingsApi = {
  getSmtp: () => dataOf(apiRequest<SmtpSettings>("/settings/smtp")),
  updateSmtp: (body: Record<string, unknown>) =>
    dataOf(apiRequest<SmtpSettings>("/settings/smtp", { method: "PUT", body })),
  testSmtp: (body: {
    to_email: string;
    subject?: string;
    body?: string;
    use_template?: boolean;
    template?: string;
  }) =>
    dataOf(
      apiRequest<{
        sent: boolean;
        to_email: string;
        subject?: string;
        template?: string | null;
      }>("/settings/smtp/test", {
        method: "POST",
        body,
      }),
    ),
};
