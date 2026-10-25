"""
Retrieval evaluation. Checks that the right handbook SECTION appears in the top-k results, and
prints relevance scores for off-topic questions so you can tune DENSE_MIN_SCORE / thresholds.

    python scripts/eval_retrieval.py            # run from backend/
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.store import get_kb  # noqa: E402

# (question, [accepted section-title prefixes])
IN_SCOPE = {
    "student": [
        ("What is the minimum attendance requirement?", ["3.7."]),
        ("How much attendance do I need to write the end semester exam?", ["3.7."]),
        ("What does the R grade mean?", ["3.8."]),
        ("What are the grade points for each letter grade?", ["3.8."]),
        ("How do I convert CGPA to percentage?", ["3.8."]),
        ("Who is eligible to appear for examinations?", ["3.9."]),
        ("What is the punishment for ragging?", ["4.4."]),
        ("Can I change my branch after first year?", ["3.11."]),
        ("How does credit transfer work?", ["3.12."]),
        ("What are the rules for promotion to the next year?", ["3.10."]),
        ("What is the dress code on campus?", ["2.2."]),
        ("How many books can a UG student borrow from the library?", ["2.13"]),
        ("How do I file a complaint to the grievance committee?", ["4.6."]),
        ("What are the PhD thesis submission requirements?", ["8.10."]),
        ("What are the hostel rules?", ["2.15.", "ANNEXURE-III"]),
        ("What happens if a student is caught plagiarising?", ["4.2.", "ANNEXURE-I"]),
        ("What is the Academic Bank of Credits?", ["3.13."]),
    ],
    "faculty": [
        ("How many casual leaves can a faculty member take in a year?", ["ANNEXURE - I >"]),
        ("What is the maternity leave policy?", ["ANNEXURE - I >"]),
        ("What is the teaching workload of a professor?", ["3.10"]),
        ("What is the probation period for new staff?", ["3.6"]),
        ("What are the examination duties of faculty?", ["11.0"]),
        ("What is the dress code for staff?", ["6.0"]),
        ("Can faculty accept gifts?", ["7.0"]),
        ("What is covered under group medical insurance?", ["4.1"]),
        ("How do I get a No Objection Certificate to apply for other jobs?", ["16."]),
        ("What is the whistleblower policy?", ["17."]),
        ("What is the sexual harassment complaint procedure?", ["ANNEXURE - V"]),
        ("What is the travel policy for official trips?", ["ANNEXURE - II"]),
        ("Is biometric attendance mandatory?", ["8.0"]),
        ("What is the Leave Travel Concession?", ["4.5", "ANNEXURE - III"]),
        ("What is the mentoring process for students?", ["15.0"]),
        ("What are the duties of the Dean of Faculty Affairs?", ["18.29"]),
        ("What research incentive is given per publication?", ["1.2"]),
    ],
}
OFF_TOPIC = [
    "What is the capital of France?",
    "Write a python function to sort a list",
    "Who won the cricket world cup?",
    "What is the best pizza topping?",
    "Tell me a joke",
    "How do I invest in stocks?",
]


def main():
    total = hits = 0
    for role, qs in IN_SCOPE.items():
        kb = get_kb(role)
        print(f"\n===== {kb.label}  ({len(kb.chunks)} chunks, retrieval={kb.mode}) =====")
        for q, prefixes in qs:
            r = kb.search(q)
            rank = next((i + 1 for i, h in enumerate(r.hits) if any(h.chunk["section"].startswith(p) for p in prefixes)), None)
            total += 1
            hits += rank is not None
            d = f"{r.best_dense:.2f}" if r.best_dense is not None else " n/a"
            top = r.hits[0].chunk
            print(f"{'OK  ' if rank else 'MISS'} rank={rank or '-'} dense={d} cov={r.coverage:.2f} relevant={r.relevant!s:5} | {q}")
            if not rank:
                print(f"       top was: p{top['printed_start']} {top['section'][:70]}")
    print(f"\nHit@{len(r.hits)}: {hits}/{total} = {hits/total:.0%}")

    print("\n===== Off-topic questions (these should score LOW; tune thresholds if not) =====")
    for role in IN_SCOPE:
        kb = get_kb(role)
        for q in OFF_TOPIC:
            r = kb.search(q)
            d = f"{r.best_dense:.2f}" if r.best_dense is not None else " n/a"
            print(f"[{role:7}] dense={d} cov={r.coverage:.2f} relevant={r.relevant!s:5} | {q}")


if __name__ == "__main__":
    main()
