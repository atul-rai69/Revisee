import { CommonModule } from '@angular/common';
import { Component, Input, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import {
  AudienceLevel,
  CodingQuestionFormat,
  ContentSection,
  DetailLevel,
  GenerationDifficulty,
  GenerationGoal,
  GenerationPreferences,
  GenerationQuestionType,
  GenerationTone,
  ProgrammingLanguage,
} from '../../../core/models/generation-preferences.models';

@Component({
  selector: 'app-generation-preferences',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './generation-preferences.html',
  styleUrl: './generation-preferences.css',
})
export class GenerationPreferencesPanel {
  @Input() fullContent = false;

  readonly customized = signal(false);
  readonly form;

  constructor(formBuilder: FormBuilder) {
    this.form = formBuilder.nonNullable.group({
      questionCount: [5, [Validators.min(1), Validators.max(10)]],
      typeTheory: true,
      typeNumerical: false,
      typeCoding: false,
      typeApplication: false,
      typeFactRecall: false,
      typePyqStyle: false,
      difficultyMode: 'DEFAULT',
      easyPercent: [20, [Validators.min(0), Validators.max(100)]],
      mediumPercent: [50, [Validators.min(0), Validators.max(100)]],
      hardPercent: [30, [Validators.min(0), Validators.max(100)]],
      explanationsRequired: true,
      expectedTime: [30, [Validators.min(1), Validators.max(3600)]],
      generationGoal: 'DEFAULT',
      audienceLevel: 'DEFAULT',
      detailLevel: 'DEFAULT',
      tone: 'DEFAULT',
      contentTheory: true,
      contentKeyPoints: true,
      contentRevisionNotes: false,
      contentQuestions: true,
      contentExamples: false,
      contentFormulaSummary: false,
      contentCodeExamples: false,
      numericalComplexity: 'INTERMEDIATE',
      numericalFormulas: true,
      numericalUnitConversions: false,
      numericalStepByStep: true,
      numericalAllowCalculator: false,
      codingLanguage: 'INFER_FROM_SOURCE',
      codingOutputPrediction: false,
      codingDebugging: false,
      codingConceptual: true,
      codingComplexity: false,
      codingImplementation: false,
      codingExperience: 'INTERMEDIATE',
      codingExplanations: true,
      focusAreas: ['', Validators.maxLength(1200)],
      avoidAreas: ['', Validators.maxLength(1200)],
      additionalInstructions: ['', Validators.maxLength(2000)],
    });
  }

  toggleCustomization(): void {
    this.customized.update((value) => !value);
  }

  reset(): void {
    this.customized.set(false);
    this.form.reset({
      questionCount: 5,
      typeTheory: true, typeNumerical: false, typeCoding: false,
      typeApplication: false, typeFactRecall: false, typePyqStyle: false,
      difficultyMode: 'DEFAULT', easyPercent: 20, mediumPercent: 50, hardPercent: 30,
      explanationsRequired: true, expectedTime: 30, generationGoal: 'DEFAULT',
      audienceLevel: 'DEFAULT', detailLevel: 'DEFAULT', tone: 'DEFAULT',
      contentTheory: true, contentKeyPoints: true, contentRevisionNotes: false,
      contentQuestions: true, contentExamples: false, contentFormulaSummary: false,
      contentCodeExamples: false, numericalComplexity: 'INTERMEDIATE',
      numericalFormulas: true, numericalUnitConversions: false,
      numericalStepByStep: true, numericalAllowCalculator: false,
      codingLanguage: 'INFER_FROM_SOURCE', codingOutputPrediction: false,
      codingDebugging: false, codingConceptual: true, codingComplexity: false,
      codingImplementation: false, codingExperience: 'INTERMEDIATE',
      codingExplanations: true, focusAreas: '', avoidAreas: '', additionalInstructions: '',
    });
  }

  summary(): string[] { return this.buildSummary(); }

  questionsEnabled(): boolean {
    return !this.fullContent || this.form.controls.contentQuestions.value;
  }

  numericalSelected(): boolean { return this.form.controls.typeNumerical.value; }
  codingSelected(): boolean { return this.form.controls.typeCoding.value; }
  mixedDifficulty(): boolean { return this.form.controls.difficultyMode.value === 'MIXED'; }

  validationMessage(): string | null {
    if (!this.customized()) return null;
    if (this.form.invalid) return 'Check the highlighted generation limits.';
    if (this.fullContent && this.selectedContentSections().length === 0) {
      return 'Select at least one content section.';
    }
    if (this.questionsEnabled() && this.selectedQuestionTypes().length === 0) {
      return 'Select at least one question type.';
    }
    if (this.mixedDifficulty()) {
      const value = this.form.getRawValue();
      if (value.easyPercent + value.mediumPercent + value.hardPercent !== 100) {
        return 'Mixed difficulty percentages must total 100.';
      }
    }
    if (
      !this.form.controls.explanationsRequired.value
      && this.numericalSelected()
      && this.form.controls.numericalStepByStep.value
    ) return 'Step-by-step numerical working requires explanations.';
    if (
      !this.form.controls.explanationsRequired.value
      && this.codingSelected()
      && this.form.controls.codingExplanations.value
    ) return 'Code explanations require explanations to be enabled.';
    if (this.codingSelected() && this.selectedCodingFormats().length === 0) {
      return 'Select at least one coding-question format.';
    }
    const focusAreas = this.parseAreas(this.form.controls.focusAreas.value);
    const avoidAreas = this.parseAreas(this.form.controls.avoidAreas.value);
    const areas = [...focusAreas, ...avoidAreas];
    if (focusAreas.length > 10 || avoidAreas.length > 10 || areas.some((area) => area.length > 120)) {
      return 'Use at most 10 focus and 10 avoidance areas, with 120 characters per area.';
    }
    return null;
  }

  markAllAsTouched(): void { this.form.markAllAsTouched(); }

  buildPreferences(): GenerationPreferences | null {
    if (!this.customized() || this.validationMessage()) return null;
    const value = this.form.getRawValue();
    const preferences: GenerationPreferences = {
      generation_goal: value.generationGoal === 'DEFAULT' ? undefined : value.generationGoal as GenerationGoal,
      audience_level: value.audienceLevel === 'DEFAULT' ? undefined : value.audienceLevel as AudienceLevel,
      detail_level: value.detailLevel === 'DEFAULT' ? undefined : value.detailLevel as DetailLevel,
      tone: value.tone === 'DEFAULT' ? undefined : value.tone as GenerationTone,
      focus_areas: this.parseAreas(value.focusAreas),
      avoid_areas: this.parseAreas(value.avoidAreas),
      additional_instructions: value.additionalInstructions.trim() || undefined,
      output_language: 'ENGLISH',
    };
    if (this.fullContent) preferences.content_sections = this.selectedContentSections();
    if (this.questionsEnabled()) {
      preferences.question_count = value.questionCount;
      preferences.question_types = this.selectedQuestionTypes();
      preferences.difficulty_mode = value.difficultyMode === 'DEFAULT' ? undefined : value.difficultyMode as GenerationDifficulty;
      preferences.difficulty_distribution = value.difficultyMode === 'MIXED' ? {
        unit: 'PERCENTAGE', easy: value.easyPercent, medium: value.mediumPercent, hard: value.hardPercent,
      } : undefined;
      preferences.explanations_required = value.explanationsRequired;
      preferences.preferred_expected_time_seconds = value.expectedTime;
      if (value.typeNumerical) preferences.numerical_preferences = {
        complexity: value.numericalComplexity as 'BASIC' | 'INTERMEDIATE' | 'ADVANCED',
        include_formulas: value.numericalFormulas,
        include_unit_conversions: value.numericalUnitConversions,
        step_by_step_explanations: value.numericalStepByStep,
        allow_calculator: value.numericalAllowCalculator,
      };
      if (value.typeCoding) preferences.coding_preferences = {
        language: value.codingLanguage as ProgrammingLanguage,
        question_formats: this.selectedCodingFormats(),
        experience_level: value.codingExperience as AudienceLevel,
        code_explanations_required: value.codingExplanations,
      };
    }
    return this.withoutUndefined(preferences);
  }

  private selectedQuestionTypes(): GenerationQuestionType[] {
    const value = this.form.getRawValue();
    const entries: Array<[boolean, GenerationQuestionType]> = [
      [value.typeTheory, 'THEORY'], [value.typeNumerical, 'NUMERICAL'],
      [value.typeCoding, 'CODING'], [value.typeApplication, 'APPLICATION'],
      [value.typeFactRecall, 'FACT_RECALL'], [value.typePyqStyle, 'PYQ_STYLE'],
    ];
    return entries.filter(([selected]) => selected).map(([, type]) => type);
  }

  private selectedContentSections(): ContentSection[] {
    const value = this.form.getRawValue();
    const entries: Array<[boolean, ContentSection]> = [
      [value.contentTheory, 'THEORY'], [value.contentKeyPoints, 'KEY_POINTS'],
      [value.contentRevisionNotes, 'REVISION_NOTES'], [value.contentQuestions, 'QUESTIONS'],
      [value.contentExamples, 'EXAMPLES'], [value.contentFormulaSummary, 'FORMULA_SUMMARY'],
      [value.contentCodeExamples, 'CODE_EXAMPLES'],
    ];
    return entries.filter(([selected]) => selected).map(([, section]) => section);
  }

  private selectedCodingFormats(): CodingQuestionFormat[] {
    const value = this.form.getRawValue();
    const entries: Array<[boolean, CodingQuestionFormat]> = [
      [value.codingOutputPrediction, 'OUTPUT_PREDICTION'], [value.codingDebugging, 'DEBUGGING'],
      [value.codingConceptual, 'CONCEPTUAL_CODE'], [value.codingComplexity, 'COMPLEXITY_ANALYSIS'],
      [value.codingImplementation, 'IMPLEMENTATION'],
    ];
    return entries.filter(([selected]) => selected).map(([, format]) => format);
  }

  private parseAreas(value: string): string[] {
    return value.split(/[,\n]/u).map((entry) => entry.trim()).filter(Boolean);
  }

  private buildSummary(): string[] {
    if (!this.customized()) return ['Generate automatically'];
    const value = this.form.getRawValue();
    const summary: string[] = [];
    if (this.questionsEnabled()) {
      summary.push(`${value.questionCount} questions`);
      summary.push(value.difficultyMode === 'DEFAULT' ? 'Default difficulty' : this.label(value.difficultyMode));
      summary.push(this.selectedQuestionTypes().map((entry) => this.label(entry)).join(' + '));
      if (value.explanationsRequired) summary.push('Explanations');
    }
    if (value.generationGoal !== 'DEFAULT') summary.push(this.label(value.generationGoal));
    if (this.fullContent) summary.push(`${this.selectedContentSections().length} content sections`);
    return summary.filter(Boolean);
  }

  private label(value: string): string {
    return value.toLocaleLowerCase().replaceAll('_', ' ').replace(/^./u, (letter) => letter.toLocaleUpperCase());
  }

  private withoutUndefined(preferences: GenerationPreferences): GenerationPreferences {
    return Object.fromEntries(Object.entries(preferences).filter(([, value]) => value !== undefined)) as GenerationPreferences;
  }
}
