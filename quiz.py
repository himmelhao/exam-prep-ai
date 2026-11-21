"""Picks which questions go into a diagnostic quiz (no UI code here)."""

import json
import random

import db

DIFFICULTY_ORDER = ["easy", "medium", "hard"]


def pick_for_topic(questions, per_topic: int) -> list:
    """Pick up to `per_topic` questions, trying to cover different difficulties."""
    by_difficulty = {d: [q for q in questions if q["difficulty"] == d] for d in DIFFICULTY_ORDER}
    for group in by_difficulty.values():
        random.shuffle(group)

    picked = []
    # Round-robin over easy -> medium -> hard until we have enough.
    while len(picked) < per_topic and any(by_difficulty.values()):
        for d in DIFFICULTY_ORDER:
            if by_difficulty[d] and len(picked) < per_topic:
                picked.append(by_difficulty[d].pop())
    return picked


def build_diagnostic_quiz(document_id: int, per_topic: int = 3) -> list[dict]:
    """Return a list of quiz items: {"question_id", "options"}.
    MCQ options are shuffled once here so the right answer isn't always in the same spot."""
    items = []
    for topic in db.get_topics(document_id):
        for q in pick_for_topic(db.get_questions(topic["id"]), per_topic):
            options = json.loads(q["options_json"]) if q["options_json"] else []
            random.shuffle(options)
            items.append({"question_id": q["id"], "options": options})
    return items
