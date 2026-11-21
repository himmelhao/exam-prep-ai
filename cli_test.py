"""Phase 1 test script: run the pipeline from the terminal and print what was saved.

Usage:
    python cli_test.py sample.txt
    python cli_test.py my_notes.pdf --lang swedish --per-topic 4
    python cli_test.py sample.txt --show-only     (print saved data, no AI calls)
"""

import argparse
import json
from pathlib import Path

import db
from ai_provider import AIError, RateLimitError
from generator import process_document
from text_input import load_text_file


def print_document(document_id: int):
    doc = db.get_document(document_id)
    print(f"\n=== Document #{doc['id']}: {doc['title']} ({len(doc['text'])} chars) ===")
    for topic in db.get_topics(document_id):
        print(f"\n## {topic['name']}")
        print(f"   {topic['description']}")
        for goal in json.loads(topic["goals"] or "[]"):
            print(f"   - goal: {goal}")
        for q in db.get_questions(topic["id"]):
            print(f"\n   [{q['difficulty']}/{q['type']}] {q['question']}")
            if q["options_json"]:
                for opt in json.loads(q["options_json"]):
                    marker = "*" if opt == q["answer"] else " "
                    print(f"      {marker} {opt}")
            else:
                print(f"      answer: {q['answer']}")
            print(f"      quote: \"{q['source_quote']}\"")


def main():
    parser = argparse.ArgumentParser(description="Phase 1 pipeline test")
    parser.add_argument("file", help="A .pdf or .txt file")
    parser.add_argument("--lang", choices=["english", "swedish", "both"], default="english")
    parser.add_argument("--per-topic", type=int, default=6, help="Questions per topic")
    parser.add_argument("--show-only", action="store_true", help="Only print cached data")
    args = parser.parse_args()

    text = load_text_file(args.file)
    if len(text) < 200:
        print("The text is very short (or the PDF has no extractable text, e.g. a scan).")
        return

    db.init_db()
    if args.show_only:
        doc = db.find_document_by_text(text)
        if doc:
            print_document(doc["id"])
        else:
            print("This document isn't in the database yet.")
        return

    try:
        document_id, cached = process_document(
            Path(args.file).stem, text, args.per_topic, args.lang
        )
    except RateLimitError as e:
        print(f"\nRate limit: {e}")
        return
    except AIError as e:
        print(f"\nAI error: {e}")
        return

    if cached:
        print("Loaded from cache - no API calls were made.")
    print_document(document_id)


if __name__ == "__main__":
    main()
