# Exam Prep AI

A personal study app. Upload a PDF or paste text (course material, exam requirements), and the app:

1. builds a **topic map** (5–15 topics, each with a description and learning goals),
2. generates **practice questions** per topic using *only* your source text,
3. runs a **diagnostic quiz**, one question at a time, and grades your answers,
4. shows your score per topic so you know where to focus.

It runs for **$0** on the Google Gemini API free tier. The first use case is a Swedish exam. Later it will cover the Swedish driving theory test.

## Status

| Phase | What | Status |
|---|---|---|
| 1 | Setup, AI provider, text → topics → questions, SQLite, CLI test | ✅ Done |
| 2 | Streamlit UI: add material, quiz, grading | ✅ Done |
| 3 | Mastery scores, results page with chart, practice weak topics | Planned |
| 4 | Spaced repetition (1/3/7 days), polish | Planned |

## Setup

You need **Python 3.11+** and a free Gemini API key.

```bash
# 1. Get the code
git clone https://github.com/himmelhao/exam-prep-ai.git
cd exam-prep-ai

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your API key
copy .env.example .env          # Windows
# cp .env.example .env          # macOS / Linux
```

Then open `.env` and replace `your-key-here` with a key from <https://aistudio.google.com/apikey>.

`.env` is listed in `.gitignore`, so your key never gets committed.

### Settings (`.env`)

| Variable | Meaning | Default |
|---|---|---|
| `GEMINI_API_KEY` | Your Gemini API key | *(required)* |
| `AI_PROVIDER` | Which AI service to use (only `gemini` for now) | `gemini` |
| `GEMINI_MODEL` | Any current free-tier Flash / Flash-Lite model | `gemini-3.8-flash` |

## Usage

### Web app

```bash
streamlit run app.py
```

Your browser opens at <http://localhost:8501>. The sidebar has two pages:

- **Add material**: upload a PDF or paste text, choose the question language (Swedish / English / both) and the number of questions per topic, then click **Generate questions**. On the free tier this can take a few minutes.
- **Quiz**: choose the material and 2 or 3 questions per topic, then start. After each answer you see your score (0–2), feedback, the model answer and the quote from your material that supports it. At the end you get a per-topic score table, weakest topic first.

### Command line (pipeline test)

```bash
python cli_test.py sample.txt                         # generate and print everything
python cli_test.py notes.pdf --lang swedish --per-topic 4
python cli_test.py sample.txt --show-only             # print saved data, no AI calls
```

`sample.txt` is a short Swedish text about the Swedish system of government that you can use for testing.

## How it works

```
PDF / text ──► text_input.py ──► generator.py ──► ai_provider.py ──► Gemini (JSON mode)
                                      │
                                      ▼
                                   db.py (data.db)
                                      ▲
            app.py (Streamlit) ── quiz.py / grading.py
```

- **Questions** have three difficulties (easy = recall, medium = understanding, hard = application) and two types (multiple choice and short answer). Each question stores an explanation and a word-for-word **source quote**. The app checks that the quote really appears in your text and logs any that don't.
- **Grading**: multiple choice is graded locally, which is free and instant (right = 2, wrong = 0). Short answers are graded by the AI against the model answer: 0, 1 or 2 points with a one-line feedback.
- **Caching**: if you submit the exact same text again, everything is loaded from the database and no API calls are made. If a run stops halfway (for example, because the quota ran out), the next run cleans up and starts over.
- **Rate limits**: on HTTP 429 (quota) or 503 (overloaded), the app waits 5s, 10s, 20s, 40s and retries. If it still fails, it shows a friendly message instead of crashing.

## Project files

| File | What it does |
|---|---|
| `app.py` | Streamlit UI: the "Add material" and "Quiz" pages |
| `ai_provider.py` | The **only** file that talks to an AI service. Handles JSON mode, retries and backoff |
| `generator.py` | Pipeline: text → topic map → questions, with prompts, validation and caching |
| `grading.py` | Grades answers on a 0/1/2 scale and saves each attempt |
| `quiz.py` | Picks diagnostic questions per topic, mixing difficulties |
| `db.py` | SQLite schema and small read/write helpers |
| `text_input.py` | PDF and text extraction and cleanup |
| `cli_test.py` | Terminal script to test the pipeline without the UI |
| `sample.txt` | Example study text (Swedish) |

### Database (`data.db`, created automatically)

`documents`, `topics`, `questions`, `attempts`, `mastery`, `reviews`. The last two are created now and will be used in Phases 3–4. `data.db` is not committed to git.

## Switching AI provider

Every AI call goes through `generate_json(prompt)` in `ai_provider.py`. To add Groq or Claude:

1. Write a `_call_<name>(prompt) -> str` function that returns JSON text and raises `RateLimitError` on 429.
2. Add it to the `_PROVIDERS` dict.
3. Set `AI_PROVIDER=<name>` in `.env`.

Nothing else in the app needs to change.

## Troubleshooting

- **"GEMINI_API_KEY is missing"**: copy `.env.example` to `.env` and add your key.
- **"The AI service is busy or the free quota is used up"**: wait a minute for the per-minute limit, or until tomorrow for the daily limit. Your progress is kept.
- **"Not enough text"** after uploading a PDF: the PDF is probably a scan (images only), which has no extractable text.
- **Questions are in the wrong language**: cached material keeps the language it was first generated in.
