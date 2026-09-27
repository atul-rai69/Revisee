export type GenerationQuestionType = 'THEORY' | 'NUMERICAL' | 'CODING' | 'APPLICATION' | 'FACT_RECALL' | 'PYQ_STYLE';
export type GenerationDifficulty = 'EASY' | 'MEDIUM' | 'HARD' | 'MIXED';
export type GenerationGoal = 'UNDERSTANDING' | 'EXAM_PREPARATION' | 'REVISION' | 'INTERVIEWS' | 'PRACTICAL_APPLICATION';
export type AudienceLevel = 'BEGINNER' | 'INTERMEDIATE' | 'ADVANCED';
export type DetailLevel = 'CONCISE' | 'STANDARD' | 'DETAILED';
export type GenerationTone = 'ACADEMIC' | 'EXAM_FOCUSED' | 'INTERVIEW_FOCUSED' | 'PRACTICAL';
export type ContentSection = 'THEORY' | 'KEY_POINTS' | 'REVISION_NOTES' | 'QUESTIONS' | 'EXAMPLES' | 'FORMULA_SUMMARY' | 'CODE_EXAMPLES';
export type ProgrammingLanguage = 'INFER_FROM_SOURCE' | 'PYTHON' | 'JAVASCRIPT' | 'TYPESCRIPT' | 'JAVA' | 'C_SHARP' | 'C_PLUS_PLUS' | 'GO' | 'RUST' | 'SQL';
export type CodingQuestionFormat = 'OUTPUT_PREDICTION' | 'DEBUGGING' | 'CONCEPTUAL_CODE' | 'COMPLEXITY_ANALYSIS' | 'IMPLEMENTATION';

export interface GenerationPreferences {
  question_count?: number;
  question_types?: GenerationQuestionType[];
  difficulty_mode?: GenerationDifficulty;
  difficulty_distribution?: {
    unit: 'PERCENTAGE' | 'COUNT';
    easy: number;
    medium: number;
    hard: number;
  };
  explanations_required?: boolean;
  preferred_expected_time_seconds?: number;
  generation_goal?: GenerationGoal;
  audience_level?: AudienceLevel;
  detail_level?: DetailLevel;
  tone?: GenerationTone;
  content_sections?: ContentSection[];
  numerical_preferences?: {
    complexity: 'BASIC' | 'INTERMEDIATE' | 'ADVANCED';
    include_formulas: boolean;
    include_unit_conversions: boolean;
    step_by_step_explanations: boolean;
    allow_calculator: boolean;
  };
  coding_preferences?: {
    language: ProgrammingLanguage;
    question_formats: CodingQuestionFormat[];
    experience_level: AudienceLevel;
    code_explanations_required: boolean;
  };
  focus_areas?: string[];
  avoid_areas?: string[];
  additional_instructions?: string;
  output_language?: 'ENGLISH';
}
