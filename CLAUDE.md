# Exam Prep AI — Project Brief

## Goal
A personal study app. I upload a PDF or paste text (course material, exam requirements).
The app generates questions, tests me, shows what level I'm at per topic, and tells me what to improve.
First use case: a Swedish exam. Later: the Swedish driving theory test.

## Hard constraints
- Must cost $0 to run. Use the Google Gemini API free tier (model: a current free Flash / Flash-Lite model).
- API key is read from a `.env` file (`GEMINI_API_KEY`). Never hard-code keys. `.env` must be in `.gitignore`.
- Put all AI calls behind one small provider module (`ai_provider.py`) so I can later switch to Groq or Claude by changing one setting.
- Cache generated topics/questions in the database so the same document never costs API calls twice.
- Handle rate-limit errors (HTTP 429) with a friendly message and retry/backoff.

## Tech stack
- Python 3.11+
- Streamlit for the UI
- `google-genai` for Gemini, using JSON output mode for structured results
- `pypdf` for PDF text extraction
- SQLite (single file `data.db`) for storage
- `python-dotenv`

## How the app works
1. Input: upload PDF or paste text.
2. AI builds a topic map: 5–15 topics, each with a description and 2–3 learning goals (JSON).
3. AI generates questions per topic using ONLY the source text:
   - difficulty: easy (recall), medium (understanding), hard (application)
   - types: multiple choice and short answer
   - each question stores: type, difficulty, question, options, correct answer, explanation, exact source quote
4. Diagnostic quiz: 2–3 questions per topic, one question at a time.
5. Grading: MCQ graded locally; short answers graded by AI with a 0/1/2 score and one-line feedback.
6. Mastery score (0–100) per topic; hard questions weigh more; recent attempts weigh more.
7. Results page: chart of topics, 3 weakest topics, what to review (show the source passages).
8. "Practice weak topics" mode that generates new questions for weak topics.
9. Spaced repetition: wrong answers come back after 1, 3, 7 days (`next_review_date`).
10. Setting: question language = Swedish / English / both.

## Database tables
- documents (id, title, text, created_at)
- topics (id, document_id, name, description, goals)
- questions (id, topic_id, type, difficulty, question, options_json, answer, explanation, source_quote)
- attempts (id, question_id, user_answer, score, created_at)
- mastery (topic_id, score, updated_at)
- reviews (question_id, next_review_date, interval_days)

## Build order (do one phase at a time, I test between phases)
- Phase 1: project setup, ai_provider.py, PDF/text → topic map → questions, saved to SQLite. Test with a CLI script.
- Phase 2: Streamlit UI: input page + quiz page + grading.
- Phase 3: mastery scores + results page + practice weak topics.
- Phase 4: spaced repetition, caching, polish, README with setup steps.

## Working style
- I'm learning: explain briefly what each new file does.
- Keep code simple and readable; small files; comments where logic is non-obvious.
- After each phase, tell me exactly how to run and test it.
- Ask me before adding new dependencies or paid services.
