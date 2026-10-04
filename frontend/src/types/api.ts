// TypeScript mirror of the backend response and request models in src/ruko/models/.
// The backend's Pydantic models are the source of truth; field names here must match them.
// Only the fields the frontend reads are typed strictly; the rest are passed through.

export type InterventionLevel = "L0" | "L1" | "L2" | "L3";
export type Certainty = "possible" | "likely" | "unclear";
export type Severity = "low" | "medium" | "high";
export type DecisionStage =
  | "learn"
  | "evaluate_content"
  | "consider_action"
  | "about_to_act"
  | "already_acted"
  | "calculate"
  | "unknown";
export type ProductClass =
  | "cash_equity"
  | "derivative"
  | "ipo"
  | "mutual_fund"
  | "scheme_or_app"
  | "crypto"
  | "unknown";
export type FundingSource =
  | "savings"
  | "borrowed"
  | "emergency_fund"
  | "protected_goal"
  | "unknown";
export type SourceType =
  | "unsolicited_group"
  | "known_person"
  | "influencer"
  | "own_research"
  | "unknown";
export type ExpenseBand = "lt_10k" | "10k_25k" | "25k_50k" | "50k_1l" | "1l_2l" | "gt_2l";
export type SavingsBand = "lt_25k" | "25k_1l" | "1l_3l" | "3l_10l" | "10l_25l" | "gt_25l";
export type Locale = "en" | "hi" | "kn";

/** models/responses.py: TemplateRef */
export interface TemplateRef {
  key: string;
  slots: Record<string, string>;
}

/** models/common.py: SourceRef */
export interface SourceRef {
  source_title: string;
  source_url: string | null;
  as_of: string | null;
  verified_by_human: boolean;
}

/** models/responses.py: ResponseMeta (subset) */
export interface ResponseMeta {
  request_id: string;
  locale: string;
  stage?: DecisionStage | null;
  stage_source?: string | null;
  extraction_mode?: string;
  unverified_fact_ids?: string[];
  [key: string]: unknown;
}

/** models/responses.py: SignalView */
export interface SignalView {
  code: string;
  certainty: Certainty;
  severity: Severity | null;
  /** "Label: explanation" (kept for compatibility). */
  text: string;
  /** Rendered certainty word alone, in the locale (badge). */
  certainty_label?: string | null;
  /** Rendered explanation without the certainty label. */
  reason_text?: string | null;
}

/** models/responses.py: EventSummary (no message text) */
export interface EventSummary {
  stage: DecisionStage;
  action: string;
  product_class: ProductClass;
  source_type: SourceType;
}

/** models/responses.py: ExplanationCard */
export interface ExplanationCard {
  id: string;
  title: string;
  body: string;
  safety_critical: boolean;
  as_of: string | null;
  sources: SourceRef[];
  verified_by_human: boolean;
}

/** models/responses.py: RecoveryEntry */
export interface RecoveryEntry {
  text: string;
  endpoint: "/v1/recover";
}

/** models/decision.py: Reason */
export interface Reason {
  code: string;
  severity: Severity;
  certainty: Certainty;
  source: string;
  dimension: "content" | "behavioural";
}

/** models/decision.py: InterventionDecision (subset) */
export interface InterventionDecision {
  level: InterventionLevel;
  computed_level: InterventionLevel;
  reasons: Reason[];
  dimension_levels: { content: InterventionLevel; behavioural: InterventionLevel };
  cooling_off_minutes: number | null;
  recovery_entry: boolean;
  override_allowed: true;
  policy_version: string;
  [key: string]: unknown;
}

/** models/responses.py: PauseResponse */
export interface PauseResponse {
  kind: "pause";
  level: InterventionLevel;
  headline: string;
  numbers_text: string[];
  rules_text: string[];
  signals: SignalView[];
  question: string | null;
  cards: ExplanationCard[];
  recovery_entry: RecoveryEntry | null;
  override_label: string;
  speak: TemplateRef[];
  decision: InterventionDecision;
  event?: EventSummary | null;
  meta: ResponseMeta;
}

/** models/responses.py: RefusalResponse */
export interface RefusalResponse {
  kind: "refusal";
  refusal_class: string;
  message: string;
  alternative: string;
  speak: TemplateRef[];
  meta: ResponseMeta;
}

/** models/responses.py: ClarifyOption / ClarifyQuestion */
export interface ClarifyOption {
  value: string;
  label: string;
}
export interface ClarifyQuestion {
  field: string;
  text: string;
  options: ClarifyOption[];
}

/** models/event.py: DecisionEvent (subset the frontend reads) */
export interface DecisionEventView {
  product_class?: ProductClass;
  source_type?: SourceType;
  [key: string]: unknown;
}

/** models/responses.py: ClarifyResponse */
export interface ClarifyResponse {
  kind: "clarify";
  questions: ClarifyQuestion[];
  event: DecisionEventView;
  speak: TemplateRef[];
  meta: ResponseMeta;
}

/** models/responses.py: ContentReportResponse */
export interface ContentReportResponse {
  kind: "content_report";
  headline: string;
  signals: SignalView[];
  note: string | null;
  cards: ExplanationCard[];
  recovery_entry: RecoveryEntry | null;
  speak: TemplateRef[];
  meta: ResponseMeta;
}

/** models/responses.py: GlossaryResponse */
export interface GlossaryResponse {
  kind: "glossary";
  found: boolean;
  term: string | null;
  title: string | null;
  body: string;
  sources: SourceRef[];
  speak: TemplateRef[];
  meta: ResponseMeta;
}

/** models/recovery.py: RecoveryStep / RecoveryGuide */
export interface RecoveryStep {
  order: number;
  urgent: boolean;
  text: string;
  route_id: string | null;
  contact: string | null;
}
export interface RecoveryGuide {
  kind: "recovery";
  scenario: string;
  steps: RecoveryStep[];
  evidence_checklist: string[];
  draft_complaint: string;
  sources: SourceRef[];
  speak: TemplateRef[];
  meta: ResponseMeta;
}

/** models/common.py: CalculatorTool */
export type CalculatorTool = "sip" | "goal" | "inflation" | "consequence" | "costs" | "tax";

/** models/calculation.py: SeriesPoint / Scenario / CalculationResponse */
export interface SeriesPoint {
  month: number;
  invested_inr: number;
  value_inr: number;
}
export interface Scenario {
  label: string;
  assumption_pct: number | null;
  values: Record<string, number>;
  lines: string[];
  series: SeriesPoint[];
}
export interface CalculationResponse {
  kind: "calculation";
  tool: CalculatorTool;
  inputs: Record<string, number | number[]>;
  headline: string;
  explanation: string;
  assumptions: string[];
  scenarios: Scenario[];
  is_illustration: true;
  speak: TemplateRef[];
  meta: ResponseMeta;
}

/** models/calculation.py: CalculationInputs (answers.calculation) */
export interface CalculationInputs {
  tool?: CalculatorTool;
  amount_inr?: number;
  monthly_inr?: number;
  goal_inr?: number;
  already_saved_inr?: number;
  months?: number;
  years?: number;
  rates_pct?: number[];
  drops_pct?: number[];
  leverage?: number;
  trade_value_inr?: number;
  trades_per_month?: number;
}

/** Union returned by POST /v1/analyze, discriminated by `kind`. */
export type AnalyzeResponse =
  | PauseResponse
  | RefusalResponse
  | ClarifyResponse
  | ContentReportResponse
  | GlossaryResponse
  | RecoveryGuide
  | CalculationResponse;

/** Error envelope used by every /v1 route (docs/api_contract.md "Errors"). */
export interface ApiErrorBody {
  error: {
    code: string;
    message_key: string;
    retryable: boolean;
    fields?: string[];
  };
}

/** models/inputs.py: RawInput */
export interface RawInput {
  type: "text" | "link" | "image";
  content: string;
  claimed_locale?: Locale;
}

/** models/event.py: DecisionPlan */
export interface DecisionPlan {
  reason_given: boolean;
  horizon?: string | null;
  reconsider_condition_given?: boolean;
}

/** models/requests.py: DecisionAnswers */
export interface DecisionAnswers {
  amount_inr?: number;
  funding_source?: FundingSource;
  product_class?: ProductClass;
  source_type?: SourceType;
  stage?: DecisionStage;
  plan?: DecisionPlan;
  calculation?: CalculationInputs;
  skipped_fields?: string[];
}

/** models/profile.py: UserRules (subset the app edits) */
export interface UserRules {
  max_share_of_savings_pct?: number;
  max_amount_inr?: number;
  no_borrowed_money?: boolean;
  cooling_off_minutes?: number;
}

/** models/profile.py: UserProfile (subset the app edits; lives on the device) */
export interface UserProfile {
  monthly_expenses_band?: ExpenseBand;
  liquid_savings_band?: SavingsBand;
  rules?: UserRules;
  seen_card_ids?: string[];
}

/** models/requests.py: AnalyzeRequest */
export interface AnalyzeRequest {
  input: RawInput;
  locale: Locale;
  profile: UserProfile;
  answers: DecisionAnswers;
}

/** models/journal.py: JournalAction */
export type JournalAction =
  | "went_ahead"
  | "changed_amount"
  | "delayed"
  | "set_plan"
  | "dropped";
