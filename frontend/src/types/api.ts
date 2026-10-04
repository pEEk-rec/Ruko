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
  /** What the signal is doing: pressure, claims, source, or you. */
  role?: string | null;
  role_label?: string | null;
  certainty: Certainty;
  severity: Severity | null;
  /** "Label: explanation" (kept for compatibility). */
  text: string;
  /** Rendered certainty word alone, in the locale (badge). */
  certainty_label?: string | null;
  /** Rendered explanation without the certainty label. */
  reason_text?: string | null;
  /** An excerpt of the user's own (redacted) message this signal rests on. Not Ruko's wording. */
  quote?: string | null;
}

/** models/responses.py: EventSummary (no message text) */
export interface EventSummary {
  stage: DecisionStage;
  action: string;
  product_class: ProductClass;
  source_type: SourceType;
}

/** models/responses.py: TermHit (a glossary word inside a Ruko text, tappable for a pop-up) */
export interface TermHit {
  id: string;
  /** The exact words in the text that name the term. */
  match: string;
  title: string;
  brief: string;
}

/** models/responses.py: LessonTopic (a lesson as listed or suggested) */
export interface LessonTopic {
  id: string;
  title: string;
  summary: string;
  read_seconds: number;
  topic: string;
  seen: boolean;
  safety_critical: boolean;
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

/** models/responses.py: Lesson (a short curated micro-lesson; never LLM-written) */
export interface Lesson {
  id: string;
  title: string;
  body: string;
  read_seconds: number;
  safety_critical: boolean;
  related_tool: CalculatorTool | null;
  as_of: string | null;
  sources: SourceRef[];
  verified_by_human: boolean;
  speak: TemplateRef[];
  summary?: string | null;
  /** General habit advice from Ruko, not from an official source (labelled in the app). */
  own_guidance?: boolean;
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

/** models/decision.py: NumberRange / MoneyRange / AdverseMove / ExposureNumbers */
export interface NumberRange {
  low: number;
  high: number;
  typical: number;
}
export interface AdverseMove {
  move_pct: number;
  loss_inr: number;
  exposure_inr: number;
  label: "illustration";
}
export interface ExposureNumbers {
  amount_inr: number | null;
  basis: "exact" | "band" | "none";
  months_of_expenses: NumberRange | null;
  share_of_savings_pct: NumberRange | null;
  remaining_savings_inr: NumberRange | null;
  remaining_buffer_months: NumberRange | null;
  adverse_moves: AdverseMove[];
}

/** models/decision.py: InterventionDecision (subset) */
export interface InterventionDecision {
  level: InterventionLevel;
  computed_level: InterventionLevel;
  reasons: Reason[];
  dimension_levels: { content: InterventionLevel; behavioural: InterventionLevel };
  cooling_off_minutes: number | null;
  recovery_entry: boolean;
  exposure?: ExposureNumbers;
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
  lessons?: Lesson[];
  /** One lesson worth reading, offered on a quiet result. */
  learn_next?: LessonTopic | null;
  /** Glossary words used anywhere in this response (the shared word layer). */
  terms?: TermHit[];
  recovery_entry: RecoveryEntry | null;
  /** Questions that would personalise this pause (a warning was shown before asking). */
  refine?: ClarifyQuestion[];
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
  terms?: TermHit[];
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
  /** Values the message itself mentions (e.g. an amount), offered as one-tap confirmations. */
  hints?: ClarifyOption[];
  /** The option that matches what the message describes, and its rendered tag. */
  suggested?: string | null;
  suggested_tag?: string | null;
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
  lessons?: Lesson[];
  learn_next?: LessonTopic | null;
  /** Glossary words used anywhere in this response (the shared word layer). */
  terms?: TermHit[];
  recovery_entry: RecoveryEntry | null;
  speak: TemplateRef[];
  meta: ResponseMeta;
}

/** models/responses.py: GlossaryChip (another term Ruko can explain) */
export interface GlossaryChip {
  id: string;
  title: string;
}

/** models/responses.py: GlossaryResponse */
export interface GlossaryResponse {
  kind: "glossary";
  found: boolean;
  term: string | null;
  title: string | null;
  body: string;
  sources: SourceRef[];
  related?: GlossaryChip[];
  terms?: TermHit[];
  /** A lesson that goes deeper on this term. */
  learn_next?: LessonTopic | null;
  speak: TemplateRef[];
  meta: ResponseMeta;
}

/** models/responses.py: TopicGroup / GlossaryEntry / LearnHubResponse / LessonResponse */
export interface TopicGroup {
  id: string;
  title: string;
  lessons: LessonTopic[];
}
export interface GlossaryEntry {
  id: string;
  title: string;
  brief: string;
}
export interface LearnHubResponse {
  kind: "learn_hub";
  featured: LessonTopic | null;
  read_count: number;
  total: number;
  topics: TopicGroup[];
  words: GlossaryEntry[];
  meta: ResponseMeta;
}
export interface LessonResponse {
  kind: "lesson";
  lesson: Lesson;
  next: LessonTopic | null;
  terms?: TermHit[];
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
  lessons?: Lesson[];
  learn_next?: LessonTopic | null;
  /** Glossary words used anywhere in this response (the shared word layer). */
  terms?: TermHit[];
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

export type PlanHorizon = "days" | "weeks" | "months" | "years" | "unsure";

/** models/event.py: DecisionPlan (flags only: the user's words stay on the device) */
export interface DecisionPlan {
  reason_given: boolean;
  horizon?: PlanHorizon | null;
  reconsider_condition_given?: boolean;
}

/** models/profile.py: PlannedDecision (a plan logged in advance; words stay on the device) */
export interface PlannedDecision {
  id: string;
  product_class: ProductClass;
  amount_min_inr: number;
  amount_max_inr: number;
  horizon?: PlanHorizon | null;
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

export type AgeBand = "lt_30" | "30_40" | "40_50" | "50_60" | "gt_60";
export type TradesPerWeekBand = "0" | "1_5" | "6_20" | "gt_20";
export type Experience = "none" | "some" | "regular";

/** models/profile.py: ProtectedGoal */
export interface ProtectedGoal {
  id: string;
  amount_inr?: number;
}

/** models/profile.py: UserRules */
export interface UserRules {
  max_share_of_savings_pct?: number;
  max_amount_inr?: number;
  no_borrowed_money?: boolean;
  protected_goals?: ProtectedGoal[];
  cooling_off_minutes?: number;
}

/** models/profile.py: RecentContext */
export interface RecentContext {
  post_loss?: boolean;
  /** The device clock says it is late at night (only this yes/no is sent, never the time). */
  late_night?: boolean;
  trades_this_week?: TradesPerWeekBand;
}

/** models/profile.py: AttentionCounts (counted on the device) */
export interface AttentionCounts {
  l1_this_week?: number;
  l2_this_week?: number;
  l3_this_week?: number;
  rule_following_streak?: number;
}

/** models/profile.py: UserProfile (lives on the device; the backend forbids unknown fields) */
export interface UserProfile {
  monthly_expenses_band?: ExpenseBand;
  monthly_expenses_inr?: number;
  liquid_savings_band?: SavingsBand;
  liquid_savings_inr?: number;
  emergency_buffer_months?: number;
  rules?: UserRules;
  experience?: Partial<Record<ProductClass, Experience>>;
  age_band?: AgeBand;
  recent?: RecentContext;
  seen_card_ids?: string[];
  plans?: PlannedDecision[];
  seen_lesson_ids?: string[];
  attention?: AttentionCounts;
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

/** models/requests.py: PaymentMethod / RecoveryAnswers / RecoverRequest */
export type PaymentMethod = "upi" | "bank_transfer" | "card" | "cash_or_other" | "none";
export interface RecoveryAnswers {
  paid_money: boolean;
  payment_method: PaymentMethod;
  installed_app: boolean;
  registered_broker_involved: boolean;
  unauthorized_trade: boolean;
  cannot_withdraw: boolean;
}
export interface RecoverRequest {
  locale: Locale;
  answers: RecoveryAnswers;
}

/** models/journal.py: JournalReviewResponse (numbers and rendered text only) */
export type RuleArticulation = "growing" | "steady" | "shrinking" | "not_enough_data";
export interface WeekPoint {
  week_start: string;
  decisions: number;
  interventions: number;
  per_decision: number;
}
export interface JournalReviewResponse {
  kind: "journal_review";
  as_of: string;
  total_decisions: number;
  unsolicited_share_pct: number | null;
  plans_set_pct: number | null;
  plans_followed_pct: number | null;
  plans_pending: number;
  pauses: number;
  pause_completion_pct: number | null;
  comprehension_pct: number | null;
  reconsideration_pct: number | null;
  overrides_with_reason: number;
  overrides_without_reason: number;
  rule_articulation: RuleArticulation;
  weekly: WeekPoint[];
  highlights: string[];
  speak: TemplateRef[];
  meta: ResponseMeta;
}

/** models/requests.py: SpeakRequest / SpeakResponse */
export interface SpeakResponse {
  kind: "speech";
  audio_base64: string;
  audio_format: string;
  provider: string;
  meta: ResponseMeta;
}

/** models/inputs.py: AudioFormat (the formats a browser recorder can produce) */
export type AudioFormat = "wav" | "mp3" | "ogg" | "opus" | "webm" | "m4a" | "aac" | "flac" | "amr";

/** models/requests.py: VoiceAnalyzeRequest */
export interface VoiceAnalyzeRequest {
  audio_base64: string;
  audio_format: AudioFormat;
  speech_locale?: Locale;
  locale: Locale;
  profile: UserProfile;
  answers: DecisionAnswers;
}

/** models/requests.py: OrderIntentRequest (no instrument identity, no user ID) */
export interface OrderIntentRequest {
  product_class: ProductClass;
  amount_band: { min_inr: number; max_inr: number };
  borrowed_funds: boolean;
  leveraged: boolean;
  plan_matched?: boolean | null;
  profile: UserProfile;
}
export interface OrderIntentResponse {
  kind: "order_intent";
  level: InterventionLevel;
  reason_codes: string[];
  override_allowed: true;
  policy_version: string;
}

/** models/requests.py: CalculateRequest (the live calculator) */
export interface CalculateRequest {
  locale: Locale;
  inputs: CalculationInputs;
  profile: UserProfile;
}
