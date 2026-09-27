import { ExtractedPdfPage } from '../../shared/components/pdf-viewer/pdf-text-extractor.service';

export type PdfQuestionOption = 'A' | 'B' | 'C' | 'D';

export interface PdfQuestionDraft {
  clientId: string;
  selected: boolean;
  question: string;
  options: Record<PdfQuestionOption, string>;
  correct_option: PdfQuestionOption | null;
  explanation: string | null;
  difficulty: number;
  expected_time_seconds: number;
  source_page: number;
  source_excerpt: string;
  confidence: number;
  validation_issues: string[];
}

const QUESTION = /^\s*(?:(?:q(?:uestion)?)\s*)?(\d+)(?:\s*[.):\-]\s*|\s+)(.+)$/iu;
const OPTION = /^\s*[([]?([A-D])[\]).:\-]\s*(.+)$/iu;
const ANSWER = /^\s*(?:ans(?:wer)?|correct\s+(?:answer|option))\s*[:.\-]?\s*[([]?([A-D])[\])]?(?:\s|$)/iu;
const FREE_ANSWER = /^\s*(?:ans(?:wer)?|solution)\s*[:.\-]\s*(.+)$/iu;
const ANSWER_KEY = /^\s*(?:q(?:uestion)?\s*)?(\d+)\s*[).:\-]\s*[([]?([A-D])[\])]?(?:\s|$)/iu;
const ANSWER_KEY_HEADING = /^\s*(?:answers?|answer\s+key|solutions?)\s*:?[\s]*$/iu;
const EXPLANATION = /^\s*(?:explanation|reason)\s*[:.\-]?\s*(.*)$/iu;

interface WorkingDraft {
  number: number;
  page: number;
  question: string;
  options: Record<PdfQuestionOption, string>;
  correct: PdfQuestionOption | null;
  explanation: string[];
  raw: string[];
  activeOption: PdfQuestionOption | null;
  inExplanation: boolean;
}

export function parseExistingPdfQuestions(pages: ExtractedPdfPage[]): PdfQuestionDraft[] {
  const answerKey = collectAnswerKey(pages);
  const drafts: PdfQuestionDraft[] = [];
  for (const page of pages) {
    const lines = page.text.split(/\n/gu).map((line) => line.trim()).filter(Boolean);
    let working: WorkingDraft | null = null;
    let answerKeySection = false;
    const finish = (): void => {
      if (!working) return;
      const optionCount = Object.values(working.options).filter(Boolean).length;
      if (optionCount >= 1) drafts.push(toDraft(working, answerKey.get(working.number) ?? null));
      working = null;
    };

    for (let index = 0; index < lines.length; index += 1) {
      const line = lines[index];
      if (ANSWER_KEY_HEADING.test(line)) {
        finish();
        answerKeySection = true;
        continue;
      }
      if (answerKeySection) continue;
      const question = QUESTION.exec(line);
      if (question && hasNearbyAnswer(lines, index + 1)) {
        finish();
        working = {
          number: Number(question[1]),
          page: page.page_number,
          question: question[2].trim(),
          options: { A: '', B: '', C: '', D: '' },
          correct: null,
          explanation: [],
          raw: [line],
          activeOption: null,
          inExplanation: false,
        };
        continue;
      }
      if (!working) continue;
      working.raw.push(line);
      const option = OPTION.exec(line);
      if (option) {
        const label = option[1].toUpperCase() as PdfQuestionOption;
        working.options[label] = option[2].trim();
        working.activeOption = label;
        working.inExplanation = false;
        continue;
      }
      const answer = ANSWER.exec(line);
      if (answer) {
        working.correct = answer[1].toUpperCase() as PdfQuestionOption;
        working.activeOption = null;
        continue;
      }
      const freeAnswer = FREE_ANSWER.exec(line);
      if (freeAnswer && !Object.values(working.options).some(Boolean)) {
        working.options.A = freeAnswer[1].trim();
        working.correct = 'A';
        working.activeOption = null;
        continue;
      }
      const explanation = EXPLANATION.exec(line);
      if (explanation) {
        working.inExplanation = true;
        working.activeOption = null;
        if (explanation[1]) working.explanation.push(explanation[1].trim());
        continue;
      }
      if (working.inExplanation) working.explanation.push(line);
      else if (working.activeOption) {
        working.options[working.activeOption] = `${working.options[working.activeOption]} ${line}`.trim();
      } else {
        working.question = `${working.question} ${line}`.trim();
      }
    }
    finish();
  }
  return drafts;
}

function collectAnswerKey(pages: ExtractedPdfPage[]): Map<number, PdfQuestionOption> {
  const answers = new Map<number, PdfQuestionOption>();
  let inAnswerKey = false;
  for (const page of pages) {
    for (const line of page.text.split(/\n/gu)) {
      if (ANSWER_KEY_HEADING.test(line)) {
        inAnswerKey = true;
        continue;
      }
      if (!inAnswerKey) continue;
      const entries = line.split(/[,;|]/gu);
      for (const entry of entries) {
        const match = ANSWER_KEY.exec(entry.trim());
        if (match) answers.set(Number(match[1]), match[2].toUpperCase() as PdfQuestionOption);
      }
    }
  }
  return answers;
}

function hasNearbyAnswer(lines: string[], start: number): boolean {
  return lines.slice(start, start + 8).some((line) => OPTION.test(line) || FREE_ANSWER.test(line));
}

function toDraft(working: WorkingDraft, keyedAnswer: PdfQuestionOption | null): PdfQuestionDraft {
  const correct = working.correct ?? keyedAnswer;
  const explanation = working.explanation.join(' ').trim() || null;
  const issues: string[] = [];
  for (const label of ['A', 'B', 'C', 'D'] as const) {
    if (!working.options[label]) issues.push(`Option ${label} is missing.`);
  }
  if (!correct) issues.push('Choose the correct answer before importing.');
  if (!explanation) issues.push('Add an explanation before importing.');
  return {
    clientId: crypto.randomUUID(),
    selected: true,
    question: working.question,
    options: working.options,
    correct_option: correct,
    explanation,
    difficulty: 2,
    expected_time_seconds: 30,
    source_page: working.page,
    source_excerpt: working.raw.join(' ').replace(/\s+/gu, ' ').slice(0, 500),
    confidence: correct ? 0.88 : 0.68,
    validation_issues: issues,
  };
}
