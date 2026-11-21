"""The study pipeline: text -> topic map -> questions, all saved to the database.

Caching: if the exact same text was processed before, we reuse the saved
document/topics/questions and make zero AI calls.
"""

import re

import db
from ai_provider import generate_json

LANGUAGE_INSTRUCTIONS = {
    "english": "Write all questions, options, answers and explanations in English.",
    "swedish": "Write all questions, options, answers and explanations in Swedish.",
    "both": (
        "Write each question, option, answer and explanation in Swedish followed by an "
        "English translation in parentheses."
    ),
}

TOPIC_PROMPT = """You are helping a student prepare for an exam.
Read the SOURCE TEXT and split it into 5 to 15 study topics.
Each topic needs a short description and 2 or 3 concrete learning goals.
Use only what is in the source text.

Return JSON in exactly this shape:
{{"topics": [{{"name": "...", "description": "...", "goals": ["...", "..."]}}]}}

SOURCE TEXT:
\"\"\"
{text}
\"\"\"
"""

QUESTION_PROMPT = """You are writing exam practice questions.
Write {count} questions about the topic below, using ONLY facts stated in the SOURCE TEXT.
Do not use outside knowledge.

TOPIC: {name}
DESCRIPTION: {description}
LEARNING GOALS: {goals}

Rules:
- Mix difficulties: "easy" = recall a fact, "medium" = show understanding,
  "hard" = apply the knowledge to a new situation.
- Mix types: "mcq" (multiple choice, exactly 4 options) and "short" (short written answer).
- For "mcq", "answer" must be copied exactly from one of the "options".
- For "short", "options" must be an empty list and "answer" is a model answer (1-2 sentences).
- "source_quote" must be an EXACT, word-for-word quote from the source text (1-2 sentences)
  that supports the answer. Keep the quote in the source's original language.
- {language}

Return JSON in exactly this shape:
{{"questions": [{{"type": "mcq", "difficulty": "easy", "question": "...",
  "options": ["...", "...", "...", "..."], "answer": "...", "explanation": "...",
  "source_quote": "..."}}]}}

SOURCE TEXT:
\"\"\"
{text}
\"\"\"
"""

VALID_TYPES = {"mcq", "short"}
VALID_DIFFICULTIES = {"easy", "medium", "hard"}


def _normalize(s: str) -> str:
    """Lowercase and collapse whitespace, so quote checks ignore line breaks."""
    return re.sub(r"\s+", " ", s).strip().lower()


def quote_is_in_source(quote: str, text: str) -> bool:
    return bool(quote) and _normalize(quote) in _normalize(text)


def build_topic_map(text: str) -> list[dict]:
    result = generate_json(TOPIC_PROMPT.format(text=text))
    topics = result.get("topics", [])
    if not topics:
        raise ValueError("The AI returned no topics. Is the text long enough?")
    return topics[:15]


def _is_valid_question(q: dict) -> bool:
    """Drop malformed questions instead of saving broken data."""
    if q.get("type") not in VALID_TYPES or q.get("difficulty") not in VALID_DIFFICULTIES:
        return False
    if not q.get("question") or not q.get("answer"):
        return False
    if q["type"] == "mcq":
        options = q.get("options") or []
        return len(options) >= 2 and q["answer"] in options
    return True


def generate_questions(topic: dict, text: str, count: int, language: str) -> list[dict]:
    prompt = QUESTION_PROMPT.format(
        count=count,
        name=topic["name"],
        description=topic.get("description", ""),
        goals="; ".join(topic.get("goals", [])),
        language=LANGUAGE_INSTRUCTIONS[language],
        text=text,
    )
    result = generate_json(prompt)
    return [q for q in result.get("questions", []) if _is_valid_question(q)]


def process_document(title: str, text: str, questions_per_topic: int = 6,
                     language: str = "english", log=print) -> tuple[int, bool]:
    """Run the whole pipeline. Returns (document_id, was_cached).
    `log` receives progress messages (print in the CLI, a status box in the UI)."""
    db.init_db()

    existing = db.find_document_by_text(text)
    if existing:
        topics = db.get_topics(existing["id"])
        # Only a complete earlier run counts as cached: every topic must have questions.
        if topics and all(db.get_questions(t["id"]) for t in topics):
            return existing["id"], True
        # An earlier run stopped halfway: clear the partial data and start over.
        db.delete_topics(existing["id"])

    document_id = existing["id"] if existing else db.add_document(title, text)

    log("Building topic map...")
    topics = build_topic_map(text)
    log(f"  Found {len(topics)} topics.")

    for i, topic in enumerate(topics, start=1):
        topic_id = db.add_topic(
            document_id, topic["name"], topic.get("description", ""), topic.get("goals", [])
        )
        log(f"Generating questions {i}/{len(topics)}: {topic['name']}")
        questions = generate_questions(topic, text, questions_per_topic, language)
        unverified = 0
        for q in questions:
            if not quote_is_in_source(q.get("source_quote", ""), text):
                unverified += 1
            db.add_question(topic_id, q)
        note = f" ({unverified} quotes not found word-for-word)" if unverified else ""
        log(f"  Saved {len(questions)} questions{note}.")

    return document_id, False
