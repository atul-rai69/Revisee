export type RevisionStrategy = 'RANDOM' | 'LABEL' | 'SMART';
export type RevisionStatus = 'IN_PROGRESS' | 'COMPLETED';
export type AnswerOption = 'A' | 'B' | 'C' | 'D';
export type MasteryDelta = number;

export interface RandomRevisionRequest {
  quiz_type: 'RANDOM';
  question_count: number;
  allow_ai_generation: boolean;
}

export interface LabelRevisionRequest {
  quiz_type: 'LABEL';
  label_ids: number[];
  questions_per_label: number;
  allow_ai_generation: boolean;
}

export interface SmartRevisionRequest {
  quiz_type: 'SMART';
  question_count: number;
  allow_ai_generation: boolean;
}

export type RevisionSessionCreateRequest =
  | RandomRevisionRequest
  | LabelRevisionRequest
  | SmartRevisionRequest;

export interface RevisionQuestionOption {
  label: AnswerOption;
  text: string;
}

export interface AnswerSafeRevisionQuestion {
  session_question_id: number;
  position: number;
  question: string;
  options: RevisionQuestionOption[];
  difficulty: number;
  expected_time_seconds: number;
}

export interface RevisionSessionLabel {
  label_id: number | null;
  label_name: string;
  question_quota: number;
}

export interface RevisionSessionResponse {
  session_id: number;
  requested_strategy: RevisionStrategy;
  strategy_used: RevisionStrategy;
  question_count: number;
  questions_per_label: number | null;
  generated_question_count: number;
  status: RevisionStatus;
  labels: RevisionSessionLabel[] | null;
  questions: AnswerSafeRevisionQuestion[];
}

export interface RevisionSubmissionAnswer {
  session_question_id: number;
  selected_option: AnswerOption;
  time_taken_seconds: number;
}

export interface RevisionSubmissionRequest {
  answers: RevisionSubmissionAnswer[];
}

export interface CompletedRevisionQuestion {
  session_question_id: number;
  position: number;
  learning_item_title: string;
  question: string;
  options: RevisionQuestionOption[];
  selected_option: AnswerOption;
  correct_option: AnswerOption;
  is_correct: boolean;
  explanation: string | null;
  difficulty: number;
  expected_time_seconds: number;
  time_taken_seconds: number;
  mastery_delta: MasteryDelta;
}

export interface CompletedRevisionLabel {
  label_id: number | null;
  label_name: string;
  question_quota: number;
}

export interface RevisionSessionResult {
  session_id: number;
  status: 'COMPLETED';
  requested_strategy: RevisionStrategy;
  strategy_used: RevisionStrategy;
  started_at: string | null;
  completed_at: string;
  question_count: number;
  correct_count: number;
  incorrect_count: number;
  score_percentage: number;
  total_time_taken_seconds: number;
  labels: CompletedRevisionLabel[] | null;
  questions: CompletedRevisionQuestion[];
}

export interface LabelQuestionShortage {
  label_id: number;
  requested: number;
  eligible_unique: number;
  assigned: number;
  shortage: number;
}

export interface InsufficientQuestionBankDetail {
  code: 'INSUFFICIENT_QUESTION_BANK';
  requested_question_count: number;
  assignable_question_count: number;
  total_shortage: number;
  label_shortages: LabelQuestionShortage[] | null;
  ai_generation_available: false;
}

export type RevisionSessionErrorCode =
  | 'ANSWER_SET_MISMATCH'
  | 'REVISION_SESSION_ALREADY_COMPLETED'
  | 'REVISION_SESSION_NOT_COMPLETED'
  | 'REVISION_SESSION_RESULT_UNAVAILABLE';

export interface RevisionSessionErrorDetail {
  code: RevisionSessionErrorCode;
  message: string;
}

export interface BackendErrorResponse<TDetail = unknown> {
  detail: TDetail;
}
