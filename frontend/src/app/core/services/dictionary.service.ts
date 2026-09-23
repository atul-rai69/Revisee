import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';

export interface DictionaryDefinition {
  word: string;
  partOfSpeech: string | null;
  definition: string;
  sourceLabel: string;
  sourceUrl: string;
}

type JsonObject = Record<string, unknown>;

const PARTS_OF_SPEECH: Readonly<Record<string, string>> = {
  n: 'noun',
  v: 'verb',
  adj: 'adjective',
  adv: 'adverb',
  u: 'word',
};

export function normalizeDictionaryWord(value: string): string | null {
  const word = value.normalize('NFKC').trim();
  if (!word || word.length > 80 || /\s/u.test(word)) return null;
  return /^[\p{L}\p{M}]+(?:['’\-][\p{L}\p{M}]+)*$/u.test(word) ? word : null;
}

@Injectable({ providedIn: 'root' })
export class DictionaryService {
  private readonly endpoint = 'https://api.datamuse.com/words';

  constructor(private readonly http: HttpClient) {}

  lookup(value: string): Observable<DictionaryDefinition | null> {
    const word = normalizeDictionaryWord(value);
    if (!word) throw new TypeError('Enter one word using letters, apostrophes or hyphens.');

    const params = new HttpParams()
      .set('sp', word)
      .set('md', 'd')
      .set('max', 1);

    return this.http.get<unknown>(this.endpoint, { params }).pipe(
      map((response) => this.normalizeResponse(word, response)),
    );
  }

  private normalizeResponse(requestedWord: string, value: unknown): DictionaryDefinition | null {
    if (!Array.isArray(value)) return null;
    const match = value.find((entry): entry is JsonObject => (
      typeof entry === 'object'
      && entry !== null
      && !Array.isArray(entry)
      && typeof (entry as JsonObject)['word'] === 'string'
      && ((entry as JsonObject)['word'] as string).localeCompare(
        requestedWord,
        undefined,
        { sensitivity: 'base' },
      ) === 0
    ));
    if (!match || !Array.isArray(match['defs'])) return null;
    const rawDefinition = match['defs'].find((entry): entry is string => (
      typeof entry === 'string' && entry.trim().length > 0
    ));
    if (!rawDefinition) return null;

    const separator = rawDefinition.indexOf('\t');
    const code = separator >= 0 ? rawDefinition.slice(0, separator) : '';
    const definition = (separator >= 0
      ? rawDefinition.slice(separator + 1)
      : rawDefinition).trim();
    if (!definition) return null;

    return {
      word: match['word'] as string,
      partOfSpeech: PARTS_OF_SPEECH[code] ?? null,
      definition,
      sourceLabel: 'Datamuse · WordNet and Wiktionary',
      sourceUrl: 'https://www.datamuse.com/api/',
    };
  }
}
