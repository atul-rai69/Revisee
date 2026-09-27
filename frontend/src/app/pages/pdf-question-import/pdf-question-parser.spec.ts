import { describe, expect, it } from 'vitest';
import { ExtractedPdfPage } from '../../shared/components/pdf-viewer/pdf-text-extractor.service';
import { parseExistingPdfQuestions } from './pdf-question-parser';

function page(page_number: number, text: string): ExtractedPdfPage {
  return { page_number, text, has_usable_text: true };
}

describe('parseExistingPdfQuestions', () => {
  it('extracts a complete MCQ without inventing content', () => {
    const drafts = parseExistingPdfQuestions([page(2, `
1. Which organelle produces ATP?
A. Nucleus
B. Mitochondrion
C. Ribosome
D. Golgi apparatus
Answer: B
Explanation: Mitochondria produce ATP during respiration.
`)]);

    expect(drafts).toHaveLength(1);
    expect(drafts[0]).toMatchObject({
      question: 'Which organelle produces ATP?',
      correct_option: 'B',
      source_page: 2,
      explanation: 'Mitochondria produce ATP during respiration.',
    });
    expect(drafts[0].options.D).toBe('Golgi apparatus');
  });

  it('applies an answer key found on a later page', () => {
    const drafts = parseExistingPdfQuestions([
      page(3, 'Q7) Capital of France?\n(A) Paris\n(B) Rome\n(C) Lima\n(D) Oslo\nExplanation: Use the answer key.'),
      page(9, 'Answer Key\n7. A'),
    ]);

    expect(drafts).toHaveLength(1);
    expect(drafts[0].correct_option).toBe('A');
    expect(drafts[0].source_page).toBe(3);
  });

  it('keeps a missing answer as an editable warning', () => {
    const [draft] = parseExistingPdfQuestions([
      page(1, 'Question 2: Pick one?\nA) One\nB) Two\nC) Three\nD) Four'),
    ]);

    expect(draft.correct_option).toBeNull();
    expect(draft.validation_issues).toContain('Choose the correct answer before importing.');
    expect(draft.validation_issues).toContain('Add an explanation before importing.');
  });

  it('keeps a written question-and-answer pair without inventing distractors', () => {
    const [draft] = parseExistingPdfQuestions([
      page(4, 'Q3: What process produces ATP?\nAnswer: Cellular respiration\nExplanation: It releases usable energy.'),
    ]);

    expect(draft.options).toEqual({ A: 'Cellular respiration', B: '', C: '', D: '' });
    expect(draft.correct_option).toBe('A');
    expect(draft.validation_issues).toContain('Option B is missing.');
  });
});
