import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { DictionaryService, normalizeDictionaryWord } from './dictionary.service';

describe('DictionaryService', () => {
  let service: DictionaryService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(DictionaryService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('sends only the normalized word and maps a verified definition source', () => {
    let result: unknown;
    service.lookup('  learning ').subscribe((value) => result = value);
    const request = http.expectOne((candidate) => (
      candidate.url === 'https://api.datamuse.com/words'
      && candidate.params.get('sp') === 'learning'
      && candidate.params.get('md') === 'd'
      && candidate.params.get('max') === '1'
    ));
    expect(request.request.body).toBeNull();
    request.flush([{ word: 'learning', defs: ['n\tthe acquisition of knowledge'] }]);
    expect(result).toEqual({
      word: 'learning',
      partOfSpeech: 'noun',
      definition: 'the acquisition of knowledge',
      sourceLabel: 'Datamuse · WordNet and Wiktionary',
      sourceUrl: 'https://www.datamuse.com/api/',
    });
  });

  it('returns no result rather than inventing a definition', () => {
    let result: unknown = 'pending';
    service.lookup('unknownword').subscribe((value) => result = value);
    http.expectOne((request) => request.params.get('sp') === 'unknownword').flush([]);
    expect(result).toBeNull();
  });

  it('rejects phrases and punctuation before making a request', () => {
    expect(normalizeDictionaryWord('two words')).toBeNull();
    expect(normalizeDictionaryWord('<script>')).toBeNull();
    expect(() => service.lookup('two words')).toThrowError(TypeError);
    http.expectNone('https://api.datamuse.com/words');
  });
});
