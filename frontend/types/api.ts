export type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T;
  meta?: {
    page?: number;
    limit?: number;
    total?: number;
  } | null;
};

export type User = {
  id: string;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
  last_login_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export type LoginData = {
  user: User;
  tokens: TokenPair;
};

export type Business = {
  id: string;
  business_name: string;
  business_name_ar?: string | null;
  normalized_name?: string | null;
  category_id?: string | null;
  location_id?: string | null;
  address?: string | null;
  district?: string | null;
  website_url?: string | null;
  description?: string | null;
  description_ar?: string | null;
  latitude?: number | string | null;
  longitude?: number | string | null;
  business_status: string;
  lead_status: string;
  qualification_score: number;
  qualification_reason?: Record<string, unknown> | null;
  assigned_to?: string | null;
  first_discovered_at?: string | null;
  last_enriched_at?: string | null;
  created_at: string;
  updated_at: string;
  has_email?: boolean | null;
  has_phone?: boolean | null;
  has_website?: boolean | null;
  primary_phone?: string | null;
  primary_email?: string | null;
  contacts?: BusinessContact[];
};

export type DiscoveryJob = {
  id: string;
  name: string;
  country_id?: string | null;
  location_id?: string | null;
  category_id?: string | null;
  provider_id?: string | null;
  search_keyword: string;
  search_keyword_ar?: string | null;
  search_parameters?: Record<string, unknown> | null;
  status: string;
  total_expected: number;
  total_processed: number;
  total_created: number;
  total_duplicates: number;
  total_failed: number;
  started_at?: string | null;
  completed_at?: string | null;
  created_by?: string | null;
  created_at: string;
};

export type Campaign = {
  id: string;
  name: string;
  description?: string | null;
  campaign_type: string;
  target_location_id?: string | null;
  target_category_id?: string | null;
  target_filters?: Record<string, unknown> | null;
  status: string;
  start_date?: string | null;
  end_date?: string | null;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
};

export type CoverageSweepResult = {
  mode: string;
  city: string;
  jobs_created: number;
  jobs_started: number;
  job_ids: string[];
  note?: string;
};

export type Category = {
  id: string;
  parent_id?: string | null;
  name: string;
  name_ar: string;
  slug: string;
  description?: string | null;
};

export type Location = {
  id: string;
  country_id: string;
  parent_id?: string | null;
  name: string;
  name_ar: string;
  slug: string;
  location_type: string;
  latitude?: number | null;
  longitude?: number | null;
};

export type Country = {
  id: string;
  name: string;
  name_ar: string;
  iso_code: string;
  phone_code?: string | null;
};

export type Provider = {
  id: string;
  name: string;
  provider_type: string;
  adapter_key: string;
  is_active: boolean;
  policy_reference?: string | null;
  policy?: Record<string, unknown> | null;
};

export type JobRow = {
  id: string;
  job_family: string;
  job_type?: string;
  name?: string;
  business_id?: string | null;
  provider_id?: string | null;
  status: string;
  attempts?: number;
  total_expected?: number;
  total_processed?: number;
  total_created?: number;
  total_duplicates?: number;
  total_failed?: number;
  started_at?: string | null;
  completed_at?: string | null;
  created_at?: string | null;
};

export type ScoreInfo = {
  business_id: string;
  qualification_score: number;
  qualification_reason?: Record<string, unknown> | null;
  lead_status: string;
};

export type ScoreResult = {
  business: Business;
  score: number;
  components: Record<string, number>;
  details?: Record<string, unknown>;
  qualification_reason?: Record<string, unknown> | null;
};

export type PipelineSummary = {
  by_status: Record<string, number>;
  average_score: number;
  qualified_count: number;
  registered_count: number;
  conversion_rate: number;
};

export type ConsentRecord = {
  id: string;
  business_id: string;
  contact_id?: string | null;
  purpose: string;
  channel: string;
  consent_status: string;
  consent_method?: string | null;
  consented_at?: string | null;
  withdrawn_at?: string | null;
};

export type EligibilityResult = {
  eligible: boolean;
  reasons: string[];
  consent_status?: string | null;
  channel?: string | null;
  purpose?: string | null;
};

export type BusinessContact = {
  id: string;
  contact_type: string;
  contact_value: string;
  normalized_value?: string | null;
  label?: string | null;
  is_primary: boolean;
  is_verified: boolean;
  verification_method?: string | null;
};

export type SmtpSettings = {
  id: string;
  host: string;
  port: number;
  username?: string | null;
  password_set: boolean;
  from_email: string;
  from_name?: string | null;
  reply_to?: string | null;
  use_tls: boolean;
  use_ssl: boolean;
  is_enabled: boolean;
  updated_at: string;
};
