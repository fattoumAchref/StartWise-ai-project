export interface Message {
  role: 'user' | 'assistant'
  content: string
}

export interface KPIs {
  burn_net?: number
  burn_rate_raw?: number
  runway_months?: number
  runway_weeks?: number
  cash_out_alert?: string
  ltv?: number
  cac?: number
  ltv_cac_ratio?: number
  ltv_cac_status?: string
  gross_margin_pct?: number
  gross_margin_status?: string
  mrr?: number
  arr?: number
  breakeven_months?: number
  alertes?: string[]
}

export interface MonteCarloResult {
  p10?: number
  p50?: number
  p90?: number
  proba_survie_12m?: number
  mean_runway?: number
}

export interface Scenario {
  nom?: string
  growth_rate?: number
  revenue_12m?: number
  runway_months?: number
  breakeven_months?: number
  cash_12m?: number
  survie_12m?: boolean
  alerte?: string
}

export interface Scenarios {
  pessimiste?: Scenario
  realiste?: Scenario
  optimiste?: Scenario
}

export interface SeasonalityResult {
  forecast_3m?: number
  forecast_6m?: number
  forecast_12m?: number
  forecast_12m_lower?: number
  forecast_12m_upper?: number
  trend_direction?: string
  trend_monthly_pct?: number
  has_seasonality?: boolean
  peak_months?: number[]
  low_months?: number[]
  confidence_level?: string
  reasoning?: string
  sector_index?: number[]
  n_data_points?: number
  market_context?: string
  anomaly_months?: number[]
  blend_weight_client?: number
  alerte?: string
}

export interface Analysis {
  kpis?: KPIs
  monte_carlo?: MonteCarloResult
  phase?: string
  scenarios?: Scenarios
  seasonality?: SeasonalityResult
  comparator?: Record<string, unknown>
  confidence?: { score?: number; level?: string }
}

export interface FinancialContext {
  burn_rate?: number
  cash_balance?: number
  monthly_revenue?: number
  n_clients?: number
  prix_client?: number
  churn_rate?: number
  marketing_budget?: number
  cogs?: number
  secteur?: string
  pays?: string
  intent_fundraising?: string
  [key: string]: unknown
}

export interface Validation {
  is_valid: boolean
  data_quality_score: number
  missing_critical: string[]
  incoherences: string[]
  questions_to_ask: string[]
}

export interface Benchmark {
  source?: string
  similarity_score?: number
  churn_median?: number
  gross_margin_median?: number
  valorisation_multiple?: number
}

export interface BenchmarkExtra {
  ltv_cac_ratio?: number
  cac_payback_months?: number
  nrr?: number
  growth_yoy?: number
}

export interface Conversation {
  id: string
  title: string
}

export interface A2AState {
  available: boolean
  // investment results
  investment_rating?: string
  investment_score?: string
  investment_recommendation?: string
  investment_confidence?: string
  investment_ts?: string
  valuation?: string
  valuation_method?: string
  best_scenario?: string
  best_scenario_raise?: string
  best_scenario_dilution?: string
  best_scenario_post_money?: string
  best_scenario_rationale?: string
  dilution_pct?: string
  founder_after_pct?: string
  // clarification
  clarification_status?: string
  clarification_phrased?: string
  clarification_questions?: string
  clarification_auto_answers?: string
  clarification_ts?: string
  // conflict
  conflict_type?: string
  conflict_message?: string
  conflict_severity?: string
}

export interface AppState {
  messages: Message[]
  financial_context?: FinancialContext
  validation?: Validation
  analysis?: Analysis
  bench?: Benchmark
  bench_extra?: BenchmarkExtra
  bench_text?: string
  shown_sections: string[]
  whatif_mode: boolean
  awaiting_clarification: boolean
  a2a_publish_time?: number
  agent_task_state?: string
  conversations: Conversation[]
}
