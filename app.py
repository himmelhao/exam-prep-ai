"""Streamlit UI. Run with:  streamlit run app.py

Two pages (picked in the sidebar):
- Add material: upload a PDF or paste text -> topics + questions are generated and saved.
- Quiz: a diagnostic quiz, one question at a time, graded immediately.

Streamlit re-runs this whole script on every click, so anything that must survive
between clicks (the current quiz, which question we're on) lives in st.session_state.
"""

import streamlit as st

import db
from ai_provider import AIError, RateLimitError
from generator import process_document
from grading import MAX_SCORE, grade_and_save
from quiz import build_diagnostic_quiz
from text_input import clean_text, extract_pdf_text

st.set_page_config(page_title="Exam Prep AI", page_icon="📚")
db.init_db()

LANGUAGES = {"English": "english", "Swedish": "swedish", "Both (SV + EN)": "both"}


# ---------------------------------------------------------------- Add material

def page_add_material():
    st.header("Add study material")

    tab_pdf, tab_text = st.tabs(["Upload PDF", "Paste text"])
    with tab_pdf:
        pdf = st.file_uploader("PDF file", type=["pdf"])
    with tab_text:
        pasted = st.text_area("Paste course text or exam requirements", height=250)

    default_title = pdf.name.rsplit(".", 1)[0] if pdf else ""
    title = st.text_input("Title", value=default_title, placeholder="e.g. Samhällskunskap kap. 3")
    col1, col2 = st.columns(2)
    language = col1.selectbox("Question language", list(LANGUAGES))
    per_topic = col2.slider("Questions per topic", 3, 9, 6)
    st.caption("The same text is only processed once. Later runs load it from the "
               "database (in the language it was first generated in).")

    if st.button("Generate questions", type="primary"):
        text = extract_pdf_text(pdf) if pdf else clean_text(pasted)
        if len(text) < 200:
            st.error("Not enough text. If this is a scanned PDF, it has no extractable text.")
            return

        with st.status("Working... this can take a few minutes on the free tier.",
                       expanded=True) as status:
            try:
                doc_id, cached = process_document(
                    title or "Untitled", text, per_topic, LANGUAGES[language], log=status.write
                )
            except RateLimitError as e:
                status.update(label="Paused: AI limit reached", state="error")
                st.warning(str(e) + " Progress is kept; press Generate again later.")
                return
            except AIError as e:
                status.update(label="AI error", state="error")
                st.error(str(e))
                return
            status.update(label="Loaded from cache (no API calls)" if cached else "Done!",
                          state="complete")
        st.success("Ready! Open the **Quiz** page in the sidebar.")

    show_saved_documents()


def show_saved_documents():
    docs = db.list_documents()
    if not docs:
        return
    st.subheader("Saved material")
    for doc in docs:
        topics = db.get_topics(doc["id"])
        n_questions = sum(len(db.get_questions(t["id"])) for t in topics)
        with st.expander(f"{doc['title']} · {len(topics)} topics · {n_questions} questions"):
            for t in topics:
                st.markdown(f"**{t['name']}**: {t['description']}")


# ---------------------------------------------------------------- Quiz

def page_quiz():
    st.header("Diagnostic quiz")
    docs = db.list_documents()
    if not docs:
        st.info("No material yet. Add some on the **Add material** page.")
        return

    quiz = st.session_state.get("quiz")
    if quiz is None:
        start_screen(docs)
    elif quiz["index"] < len(quiz["items"]):
        question_screen(quiz)
    else:
        summary_screen(quiz)


def start_screen(docs):
    # Streamlit widgets need simple values, so we pass document ids and show the titles.
    titles = {d["id"]: d["title"] for d in docs}
    doc_id = st.selectbox("Material", list(titles), format_func=titles.get)
    per_topic = st.radio("Questions per topic", [2, 3], index=1, horizontal=True)
    if st.button("Start quiz", type="primary"):
        items = build_diagnostic_quiz(doc_id, per_topic)
        if not items:
            st.error("This material has no questions yet.")
            return
        st.session_state.quiz = {"items": items, "index": 0, "result": None, "log": []}
        st.rerun()


def question_screen(quiz):
    item = quiz["items"][quiz["index"]]
    q = db.get_question(item["question_id"])

    st.progress(quiz["index"] / len(quiz["items"]),
                text=f"Question {quiz['index'] + 1} of {len(quiz['items'])}")
    st.caption(f"Topic: {q['topic_name']} · {q['difficulty']} · "
               f"{'multiple choice' if q['type'] == 'mcq' else 'short answer'}")
    st.subheader(q["question"])

    if quiz["result"] is None:
        # A form means typing doesn't trigger a rerun; only "Submit" does.
        with st.form(f"q{quiz['index']}"):
            if q["type"] == "mcq":
                answer = st.radio("Choose one", item["options"], index=None)
            else:
                answer = st.text_area("Your answer")
            submitted = st.form_submit_button("Submit", type="primary")
        if submitted:
            if q["type"] == "mcq" and answer is None:
                st.warning("Pick an option first.")
                return
            try:
                with st.spinner("Grading..."):
                    result = grade_and_save(q, answer or "")
            except (RateLimitError, AIError) as e:
                st.error(f"Couldn't grade this answer: {e}")
                return
            quiz["result"] = {**result, "answer": answer or ""}
            quiz["log"].append({"topic": q["topic_name"], "score": result["score"]})
            st.rerun()
    else:
        show_feedback(q, quiz["result"])
        last = quiz["index"] + 1 == len(quiz["items"])
        if st.button("See results" if last else "Next question", type="primary"):
            quiz["index"] += 1
            quiz["result"] = None
            st.rerun()


def show_feedback(q, result):
    st.markdown(f"**Your answer:** {result['answer'] or '_(empty)_'}")
    score, feedback = result["score"], result["feedback"]
    if score == MAX_SCORE:
        st.success(f"✅ {score}/{MAX_SCORE}: {feedback}")
    elif score == 1:
        st.warning(f"🟡 {score}/{MAX_SCORE}: {feedback}")
    else:
        st.error(f"❌ {score}/{MAX_SCORE}: {feedback}")
    if q["type"] == "short":
        st.markdown(f"**Model answer:** {q['answer']}")
    if q["explanation"]:
        st.markdown(f"**Why:** {q['explanation']}")
    if q["source_quote"]:
        st.markdown(f"**From your material:**\n> {q['source_quote']}")


def summary_screen(quiz):
    log = quiz["log"]
    total = sum(r["score"] for r in log)
    st.subheader(f"Score: {total} / {MAX_SCORE * len(log)}")

    # Simple per-topic table. Proper mastery scores and charts come in Phase 3.
    per_topic = {}
    for r in log:
        got, possible = per_topic.get(r["topic"], (0, 0))
        per_topic[r["topic"]] = (got + r["score"], possible + MAX_SCORE)
    st.table([
        {"Topic": topic, "Score": f"{got}/{possible}", "%": round(100 * got / possible)}
        for topic, (got, possible) in sorted(per_topic.items(), key=lambda kv: kv[1][0] / kv[1][1])
    ])

    if st.button("New quiz", type="primary"):
        del st.session_state.quiz
        st.rerun()


# ---------------------------------------------------------------- Navigation

page = st.sidebar.radio("Page", ["Add material", "Quiz"])
if page == "Add material":
    page_add_material()
else:
    page_quiz()
