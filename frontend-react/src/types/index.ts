export interface Car {
  id: number
  year: number
  make: string
  model: string
  trim?: string
  horsepower: number
  mpg_highway: number
  msrp: number
  safety_rating: number
}

export interface CarDetail {
  id: number
  year: number
  make: string
  model: string
  trim?: string
  engine?: string
  horsepower?: number
  torque?: number
  mpg_city?: number
  mpg_highway?: number
  msrp?: number
  invoice_price?: number
  used_avg_price?: number
  safety_rating?: number
  reliability_score?: number
}

export interface PublicInventoryCar {
  id: number
  year: number
  make: string
  model: string
  trim?: string
  msrp: number
  mileage: number
  stock_count: number
  image_url: string
  social_proof?: string
}

export interface InventoryPage {
  page: number
  page_size: number
  total: number
  items: PublicInventoryCar[]
}

export interface LoanResult {
  monthly_payment: number
  total_cost: number
  down_payment: number
  annual_rate: number
  term_months: number
}

export interface FinanceEstimateResult {
  price: number
  msrp: number
  financed_amount: number
  monthly_payment: number
  total_cost: number
  savings: number
  savings_percent: number
  break_even_month: number
}

export interface TradeInEstimateResult {
  make: string
  model: string
  year?: number
  mileage: number
  condition: string
  baseline_price: number
  estimate_low: number
  estimate_high: number
  estimate_mid: number
  source: string
}

export interface SocialProofResult {
  car_id: number
  count_30_days: number
  message: string
}

export interface ResumeDealResult {
  status: string
  customer_id: number
  resume_token: string
  resume_link: string
  sms?: {
    status: string
    error?: string
  } | null
}

export interface LeaseResult {
  status: string
  monthly_payment: number
  total_lease_cost: number
  cap_cost: number
  residual_value: number
  depreciation_charge: number
  interest_charge: number
  term_months: number
  message?: string
}

export interface LeaseVsBuyResult {
  lease: LeaseResult
  buy: {
    monthly_payment: number
    total_loan_cost: number
    residual_value: number
    net_cost: number
    down_payment: number
  }
  total_comparison: {
    lease_total: number
    buy_net_total: number
    difference: number
  }
  recommendation: string
}

export interface TradeInEquity {
  market_value: number
  amount_owed: number
  equity: number
  status: "positive" | "negative" | "neutral"
  recommendation: string
}

export interface ChannelPref {
  channel: "sms" | "whatsapp" | "email" | "voice"
  is_enabled: boolean
  contact_value?: string | null
}

export interface FollowupResponse {
  status: string
  customer_id: number
  message?: string
  summary?: string
  channels?: Record<string, { status: string; error?: string }>
  sms_status?: string
  whatsapp_status?: string
  voice_status?: string
  email_status?: string
  error?: string
}

export interface LeadContact {
  id: number
  contact_type: "call" | "email" | "text" | "voicemail" | "in-person"
  notes?: string
  outcome?: string
  contacted_at?: string
}

export interface LeadSummary {
  customer_id: number
  name: string
  phone?: string
  email?: string
  contact_count: number
  score: number
  tier: "hot" | "warm" | "cold"
}

export interface LeadScoreResult {
  status: string
  customer_id: number
  score: number
  tier: "hot" | "warm" | "cold"
  components: {
    recency: number
    contact_count: number
    chat_engagement: number
    budget_match: number
  }
}

export interface DailyGoalsResult {
  status: string
  salesperson_id: string
  goal_date: string
  goals: {
    calls: number
    texts: number
    emails: number
    appointments: number
  }
}

export interface ActivityTodayResult {
  status: string
  salesperson_id: string
  date: string
  actual: {
    calls: number
    texts: number
    emails: number
    appointments: number
  }
  goals: {
    calls: number
    texts: number
    emails: number
    appointments: number
  }
  progress_percent: {
    calls: number
    texts: number
    emails: number
    appointments: number
  }
}

export interface ChatConflictOption {
  key: string
  label: string
}

export interface VehicleMetadata {
  id?: number
  year?: number | null
  make?: string | null
  model?: string | null
  trim?: string | null
  price?: number | null
  msrp?: number | null
  used_avg_price?: number | null
  mileage?: number | null
  color?: string | null
  image_url?: string | null
  stock_count?: number | null
  horsepower?: number | null
  torque?: number | null
  mpg_highway?: number | null
  towing_capacity?: number | null
  safety_rating?: number | null
  reliability_score?: number | null
}

export interface AskResponseDetailed {
  answer: string
  source?: "inventory" | "knowledge_base" | "winning_script" | "fallback" | "routed_action" | string
  question_type: string
  role?: "buyer" | "researcher" | "service" | "finance"
  tone?: string
  metadata?: {
    entities?: Record<string, any>
    total_matches?: number
    vehicles?: VehicleMetadata[]
    comparison?: {
      left?: VehicleMetadata | null
      right?: VehicleMetadata | null
    }
    rag_score?: number
    route?: string
    [key: string]: any
  }
  context?: {
    last_vehicle?: {
      year?: number | null
      make?: string | null
      model?: string | null
      trim?: string | null
    }
    last_question_type?: string
    [key: string]: any
  }
  conflict_mode?: {
    triggered: boolean
    message?: string
    options: ChatConflictOption[]
  }
}

export type AskResponse = AskResponseDetailed

export interface CustomerCountStats {
  status: string
  customer_count: number
  badge_text: string
}

export interface TriageAnswers {
  budget_max: number
  use_case: "family" | "commute" | "performance"
  priority: "value" | "reliability" | "performance"
}

export interface TriageMatch {
  id: number
  year: number
  make: string
  model: string
  msrp?: number
  used_avg_price?: number
  safety_rating?: number
  reliability_score?: number
  horsepower?: number
  mpg_highway?: number
}

export interface TriageResponse {
  status: string
  session_id: string
  answers: TriageAnswers
  matches: TriageMatch[]
}

export interface DashboardBrandStat {
  brand: string
  count: number
}

export interface DealOfDay {
  id: number
  year: number
  make: string
  model: string
  msrp?: number
  reliability_score?: number
}

export interface SalesDashboardMe {
  status: string
  salesperson_id?: number
  conversion_rate: number
  avg_profit: number
  month_sold: number
  ytd_sales: number
  ytd_target: number
  ytd_progress_percent: number
  best_selling_brands: DashboardBrandStat[]
  deal_of_the_day?: DealOfDay | null
  pending_video_approvals: number
}

export interface ServiceVideoUploadResult {
  status: string
  video_id: number
  approval_status: string
  signed_url: string
  expires_at: string
}

export interface ServiceVideoApprovalResult {
  status: string
  video_id: number
  approval_status: string
  approved_at?: string | null
}
