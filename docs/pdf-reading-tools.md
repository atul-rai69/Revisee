# PDF reading tools

## Dictionary source

Revisee's PDF word lookup uses the Datamuse API:

- API documentation: https://www.datamuse.com/api/
- Endpoint used: `GET https://api.datamuse.com/words`
- Request fields: `sp=<one word>`, `md=d`, and `max=1`
- Data sent: only the selected or manually entered word. PDF files, page text,
  learning-item content, source excerpts, and personal notes are not sent.
- Definition sources reported by Datamuse: WordNet and Wiktionary.

Terms were reviewed on 2026-09-20. Datamuse states that until 2027-01-01 the
service can be used without an API key up to 100,000 requests per day, after
which requests may be rate-limited. It asks publicly available applications to
acknowledge the Datamuse API. Revisee provides that attribution in every
successful definition panel.

The terms also state that an API key will be required from 2027-01-01. The
integration must be reviewed before that date. A provider failure must remain a
visible, retryable lookup failure; Revisee must not replace it with an AI guess.

## Personal PDF notes

Personal PDF notes are separate from source learning-item text, generated theory,
and generated key points. Notes are scoped to the authenticated user, learning
item, stable PDF media row, and page number. Note text is rendered as text, not
HTML. Creating or changing a selection never saves automatically.

Migration `20260920_0009` creates the `pdf_notes` table. Apply it only after a
database backup and normal migration review. The migration must not be applied
automatically on application startup.
