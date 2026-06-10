import axios from "axios"

import type {
  ActivityTodayResult,
  AskResponse,
  AskResponseDetailed,
  Car,
  CarDetail,
  ChannelPref,
  CustomerCountStats,
  DailyGoalsResult,
  SalesDashboardMe,
  FinanceEstimateResult,
  FollowupResponse,
  InventoryPage,
  LeadContact,
  LeadScoreResult,
  LeadSummary,
  LeaseResult,
  LeaseVsBuyResult,
  LoanResult,
  ResumeDealResult,
  SocialProofResult,
  TriageAnswers,
  TriageResponse,
  ServiceVideoApprovalResult,
  ServiceVideoUploadResult,
  TradeInEstimateResult,
  TradeInEquity,
} from "../types"

const approvalSecret = String(import.meta.env.VITE_SERVICE_VIDEO_APPROVAL_SECRET || "").trim()

const client = axios.create({
  baseURL: "/api",
  timeout: 180000,
  headers: { "Content-Type": "application/json" },
})

function getClientApiKey(): string {
  if (typeof window === "undefined") {
    return String(import.meta.env.VITE_IMPERIAL_API_KEY || "").trim()
  }

  const fromStorage = window.localStorage.getItem("IMPERIAL_API_KEY") || ""
  const fromEnv = String(import.meta.env.VITE_IMPERIAL_API_KEY || "")
  return (fromStorage || fromEnv).trim()
}

function requiresApiKey(url: string, method: string): boolean {
  const normalizedUrl = (url || "").toLowerCase()
  const normalizedMethod = (method || "get").toLowerCase()

  const protectedPrefixes = [
    "/ask",
    "/followup",
    "/knowledge/",
    "/dealership/",
    "/leads",
    "/feedback",
    "/deal/",
    "/unanswered",
    "/visualizations",
    "/paperwork/",
  ]

  if (protectedPrefixes.some((prefix) => normalizedUrl.startsWith(prefix))) {
    return true
  }

  return ["post", "put", "patch", "delete"].includes(normalizedMethod)
}

client.interceptors.request.use((config) => {
  const apiKey = getClientApiKey()
  const requestUrl = String(config.url || "")
  const requestMethod = String(config.method || "get")

  if (apiKey && requiresApiKey(requestUrl, requestMethod)) {
    config.headers = config.headers || {}
    if (!("x-api-key" in config.headers) && !("X-API-Key" in config.headers)) {
      ;(config.headers as Record<string, string>)["X-API-Key"] = apiKey
    }
  }

  return config
})

export const api = {
  /**
  * Safe fallback for streamed UX: call /ask once and emit a single chunk.
   * @param question The user question
   * @param customerContext Optional context
   * @param onDelta Callback for each streamed chunk ({ content, delta })
   * @returns Promise that resolves when stream ends
   */
  async askStream(
    question: string,
    customerContext: Record<string, any> = {},
    onDelta: (chunk: { content: string; delta: string }) => void,
  ): Promise<void> {
    const payload = { question, customer_context: customerContext, prefer_template: true }
    const { data } = await client.post("/ask", payload)
    const content = String(data?.answer || data?.response || "No response")
    onDelta({ content, delta: content })
  },
  async ask(question: string, quickReply?: string): Promise<string> {
    const payload = quickReply
      ? { question, quick_reply: quickReply, prefer_template: true }
      : { question, prefer_template: true }
    const { data } = await client.post("/ask", payload)
    if (typeof data === "string") {
      return data
    }
    return String(data?.answer || data?.response || "No response")
  },

  async askDetailed(
    question: string,
    quickReply?: string,
    customerContext?: Record<string, any>
  ): Promise<AskResponseDetailed> {
    const payload = quickReply
      ? { question, quick_reply: quickReply, prefer_template: true, customer_context: customerContext }
      : { question, prefer_template: true, customer_context: customerContext }
    const { data } = await client.post("/ask", payload)
    if (typeof data === "string") {
      return {
        answer: data,
        question_type: "general",
      }
    }
    return {
      answer: String(data?.answer || data?.response || "No response"),
      source: data?.source,
      question_type: String(data?.question_type || "general"),
      role: data?.role,
      tone: data?.tone,
      metadata: data?.metadata,
      context: data?.context,
      conflict_mode: data?.conflict_mode,
    }
  },

  async submitLead(input: {
    name?: string
    phone?: string
    email?: string
    context?: Record<string, any>
  }): Promise<{ status: string; saved_to?: string; message?: string }> {
    const { data } = await client.post("/lead", input)
    return {
      status: String(data?.status || "error"),
      saved_to: data?.saved_to,
      message: data?.message,
    }
  },

  async verifySalespersonPin(pin: string): Promise<boolean> {
    const { data } = await client.post("/auth/salesperson-mode", { pin })
    return Boolean(data?.ok)
  },

  async listPublicInventory(params?: { page?: number; page_size?: number; make?: string; model?: string }): Promise<InventoryPage> {
    const { data } = await client.get("/inventory/public", { params })
    return {
      page: Number(data?.page || 1),
      page_size: Number(data?.page_size || 12),
      total: Number(data?.total || 0),
      items: Array.isArray(data?.items) ? data.items : [],
    }
  },

  async listCars(params?: { make?: string; model?: string; year?: number }): Promise<Car[]> {
    const { data } = await client.get("/cars", { params })
    return Array.isArray(data) ? data : []
  },

  async getCar(carId: number): Promise<CarDetail> {
    const { data } = await client.get(`/cars/${carId}`)
    return data
  },

  async loan(input: { price: number; down_payment: number; annual_rate: number; term_months: number }): Promise<LoanResult> {
    const { data } = await client.post("/financial/loan", input)
    return data
  },

  async lease(input: {
    msrp: number
    residual_percent: number
    money_factor: number
    term_months: number
    down_payment: number
  }): Promise<LeaseResult> {
    const { data } = await client.post("/financial/lease", input)
    return data
  },

  async leaseVsBuy(input: {
    price: number
    residual_percent: number
    money_factor: number
    loan_rate: number
    term_months: number
    lease_down: number
    buy_down?: number
  }): Promise<LeaseVsBuyResult> {
    const { data } = await client.post("/financial/lease-vs-buy", input)
    return data
  },

  async tradeIn(input: { amount_owed: number; market_value: number }): Promise<TradeInEquity> {
    const { data } = await client.post("/financial/trade-in", input)
    return data
  },

  async financeEstimate(input: {
    price: number
    down_payment: number
    annual_rate: number
    term_months: number
    msrp?: number
  }): Promise<FinanceEstimateResult> {
    const { data } = await client.post("/finance/estimate", input)
    return data
  },

  async tradeInEstimate(input: {
    year?: number
    make: string
    model: string
    mileage?: number
    condition?: string
  }): Promise<TradeInEstimateResult> {
    const { data } = await client.post("/trade-in/estimate", input)
    return data
  },

  async socialProof(carId: number): Promise<SocialProofResult> {
    const { data } = await client.get(`/social-proof/${carId}`)
    return data
  },

  async resumeDeal(input: {
    name?: string
    email?: string
    phone?: string
    car_id?: number
    payment_estimate?: number
    trade_in_estimate?: number
    snapshot?: Record<string, any>
    walkaway?: boolean
    source?: string
  }): Promise<ResumeDealResult> {
    const { data } = await client.post("/resume-deal", input)
    return data
  },

  async getCustomerCountStats(): Promise<CustomerCountStats> {
    const { data } = await client.get("/stats/customer-count")
    return data
  },

  async submitTriage(input: { session_id?: string; customer_id?: number; answers: TriageAnswers }): Promise<TriageResponse> {
    const { data } = await client.post("/triage", input)
    return data
  },

  async ingestDocument(file: File, docType: string): Promise<any> {
    const formData = new FormData()
    formData.append("file", file)
    formData.append("doc_type", docType)
    const { data } = await client.post("/ingest-document", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    return data
  },

  async getCustomerPreferences(customerId: number): Promise<ChannelPref[]> {
    const { data } = await client.get(`/customer-preferences/${customerId}`)
    return data?.preferences || []
  },

  async saveCustomerPreferences(customerId: number, preferences: ChannelPref[]): Promise<ChannelPref[]> {
    const { data } = await client.post(`/customer-preferences/${customerId}`, { preferences })
    return data?.preferences || []
  },

  async sendFollowup(customerId: number, overrideMessage?: string): Promise<FollowupResponse> {
    const payload = overrideMessage ? { override_message: overrideMessage } : {}
    const { data } = await client.post(`/followup/${customerId}`, payload)
    return data
  },

  async logLeadContact(customerId: number, input: { contact_type: LeadContact["contact_type"]; notes?: string; outcome?: string }) {
    const { data } = await client.post(`/leads/${customerId}/contact`, input)
    return data
  },

  async getLeadContacts(customerId: number): Promise<LeadContact[]> {
    const { data } = await client.get(`/leads/${customerId}/contacts`)
    return Array.isArray(data?.contacts) ? data.contacts : []
  },

  async scoreLead(customerId: number, input?: { chat_engagement?: number; budget_match?: number; salesperson_phone?: string; auto_schedule?: boolean }): Promise<LeadScoreResult> {
    const { data } = await client.post(`/leads/${customerId}/score`, input || {})
    return data
  },

  async getLeadsSummary(limit = 25): Promise<LeadSummary[]> {
    const { data } = await client.get("/leads/summary", { params: { limit } })
    return Array.isArray(data?.leads) ? data.leads : []
  },

  async setDailyGoals(input: {
    salesperson_id?: string
    call_goal: number
    text_goal: number
    email_goal: number
    appointment_goal: number
  }): Promise<DailyGoalsResult> {
    const { data } = await client.put("/goals/today", input)
    return data
  },

  async getDailyGoals(salespersonId = "default-sales"): Promise<DailyGoalsResult> {
    const { data } = await client.get("/goals/today", { params: { salesperson_id: salespersonId } })
    return data
  },

  async getActivityToday(salespersonId = 1): Promise<ActivityTodayResult> {
    const { data } = await client.get("/activity/today", { params: { salesperson_id: salespersonId } })
    return data
  },

  async getDashboardMe(input?: { salesperson_id?: number; target_ytd?: number }): Promise<SalesDashboardMe> {
    const { data } = await client.get("/dashboard/me", { params: input })
    return data
  },

  async getMaintenanceSchedulePdf(params: { vin?: string; make?: string; model?: string; year?: number }): Promise<Blob> {
    const { data } = await client.get("/maintenance-schedule/pdf", {
      params,
      responseType: "blob",
    })
    return data
  },

  async uploadServiceVideo(file: File, input?: { customer_id?: number; salesperson_id?: number }): Promise<ServiceVideoUploadResult> {
    const formData = new FormData()
    formData.append("file", file)
    if (input?.customer_id !== undefined) formData.append("customer_id", String(input.customer_id))
    if (input?.salesperson_id !== undefined) formData.append("salesperson_id", String(input.salesperson_id))
    const { data } = await client.post("/service-video/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    return data
  },

  async approveServiceVideo(videoId: number, approved: boolean, payload?: Record<string, any>): Promise<ServiceVideoApprovalResult> {
    const headers = approvalSecret ? { "x-approval-secret": approvalSecret } : undefined
    const { data } = await client.post(`/service-video/${videoId}/approval-webhook`, { approved, ...(payload || {}) }, { headers })
    return data
  },
}
