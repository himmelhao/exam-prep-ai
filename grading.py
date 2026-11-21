"""Grades answers on a 0/1/2 scale and saves each attempt.

- Multiple choice: graded locally (free, instant). Right = 2, wrong = 0.
- Short answer: graded by the AI against the model answer and source quote.
"""

import db
from ai_provider import generate_json

MAX_SCORE = 2

GRADE_PROMPT = """You are grading a student's short answer on an exam practice question.
Grade ONLY against the model answer and the source quote, not outside knowledge.

QUESTION: {question}
MODEL ANSWER: {answer}
SOURCE QUOTE: {quote}
STUDENT ANSWER: {user_answer}

Scoring:
- 2 = correct and complete (wording may differ; minor spelling mistakes are fine)
- 1 = partly correct or missing an important part
- 0 = wrong, irrelevant or empty

Write the feedback as ONE short sentence in the same language as the question,
saying what was right or what was missing.

Return JSON: {{"score": 0, "feedback": "..."}}
"""


def grade_mcq(question, user_answer: str) -> dict:
    correct = user_answer.strip() == question["answer"].strip()
    return {
        "score": MAX_SCORE if correct else 0,
        "feedback": "Correct!" if correct else f"The correct answer is: {question['answer']}",
    }


def grade_short(question, user_answer: str) -> dict:
    if not user_answer.strip():
        return {"score": 0, "feedback": "No answer given."}
    result = generate_json(
        GRADE_PROMPT.format(
            question=question["question"],
            answer=question["answer"],
            quote=question["source_quote"],
            user_answer=user_answer,
        )
    )
    # Clamp to 0-2 in case the AI returns something odd.
    try:
        score = max(0, min(MAX_SCORE, int(result.get("score", 0))))
    except (TypeError, ValueError):
        score = 0
    return {"score": score, "feedback": result.get("feedback", "")}


def grade_and_save(question, user_answer: str) -> dict:
    """Grade one answer, store it in the attempts table, return {score, feedback}."""
    if question["type"] == "mcq":
        result = grade_mcq(question, user_answer)
    else:
        result = grade_short(question, user_answer)
    db.add_attempt(question["id"], user_answer, result["score"])
    return result
