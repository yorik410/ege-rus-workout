import csv
import random
import re
import json
from pathlib import Path

from flask import Blueprint, render_template, request, session

bp = Blueprint("letters", __name__)

STATS_FILE = Path("letters/stats.json")
EXCLUDED_FILE = Path("letters/excluded.json")
CSV_FILE = "dicts/9-12_static.csv"


# ---------- LOAD / SAVE ----------

if STATS_FILE.exists():
    with open(STATS_FILE, encoding="utf-8") as f:
        STATS = json.load(f)
else:
    STATS = {}

if EXCLUDED_FILE.exists():
    with open(EXCLUDED_FILE, encoding="utf-8") as f:
        EXCLUDED = json.load(f)
else:
    EXCLUDED = {}


def save_stats():
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(STATS, f, ensure_ascii=False, indent=4)


def save_excluded():
    with open(EXCLUDED_FILE, "w", encoding="utf-8") as f:
        json.dump(EXCLUDED, f, ensure_ascii=False, indent=4)


# ---------- DATA ----------

def load_dictionary():
    items = []

    with open(CSV_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            masked = row["masked"].strip()
            correct = row["correct"].strip()

            if masked in EXCLUDED:
                continue

            # ищем место пропуска: ".."
            # и строим шаблон ответа
            match = re.search(r"\.\.", masked)

            if not match:
                continue

            items.append({
                "masked": masked,
                "correct": correct
            })

    return items


WORDS = load_dictionary()


# ---------- WEIGHTS ----------

def get_weights():
    weights = []

    for w in WORDS:
        stat = STATS.get(w["masked"])

        if not stat:
            weights.append(1)
        else:
            weights.append(max(1, 1 + stat["wrong"] * 4 - stat["correct"]))

    return weights


# ---------- ROUTE ----------

@bp.route("/letters", methods=["GET", "POST"])
def letters():
    result = None

    if request.method == "POST":
        user_answer = request.form.get("answer", "").strip().lower()

        word_data = session["current"]
        if len(user_answer) <= 1:
            user_answer = word_data["masked"].replace("..", user_answer).lower()

        correct = word_data["correct"].lower() in user_answer or word_data["correct"].lower() == user_answer

        key = word_data["masked"]

        if key not in STATS:
            STATS[key] = {"correct": 0, "wrong": 0}

        if correct:
            STATS[key]["correct"] += 1
        else:
            STATS[key]["wrong"] += 1

        save_stats()

        result = {
            "correct": correct,
            "answer": word_data["correct"]
        }

    weights = get_weights()

    word_data = random.choices(WORDS, weights=weights, k=1)[0]
    session["current"] = word_data

    total_correct = sum(v["correct"] for v in STATS.values())
    total_wrong = sum(v["wrong"] for v in STATS.values())

    total = total_correct + total_wrong

    accuracy = round(total_correct / total * 100, 1) if total else 0

    return render_template(
        "index_letters.html",
        word=word_data["masked"],
        result=result,
        accuracy=accuracy,
        seen=len(STATS),
        total_correct=total_correct,
        total_wrong=total_wrong,
        words_count=len(WORDS)
    )


# ---------- EXCLUDE ----------

@bp.route("/letters/exclude/<word>")
def exclude(word):
    EXCLUDED[word] = True
    save_excluded()
    return "ok"


# ---------- STATS ----------

@bp.route("/letters/stats")
def stats():
    data = []

    for w in WORDS:
        key = w["masked"]
        stat = STATS.get(key, {"correct": 0, "wrong": 0})

        weight = max(1, 1 + stat["wrong"] * 4 - stat["correct"])

        data.append({
            "masked": key,
            "correct": stat["correct"],
            "wrong": stat["wrong"],
            "weight": weight
        })

    top_wrong = sorted(data, key=lambda x: x["wrong"], reverse=True)[:20]
    top_weight = sorted(data, key=lambda x: x["weight"], reverse=True)[:20]

    return render_template(
        "stats_letters.html",
        top_wrong=top_wrong,
        top_weight=top_weight
    )


@bp.route("/letters/edit/<word>", methods=["GET", "POST"])
def edit(word):
    item = next((w for w in WORDS if w["masked"] == word), None)

    if not item:
        return "not found", 404

    if request.method == "POST":
        new_masked = request.form["masked"].strip()
        new_correct = request.form["correct"].strip()

        # обновляем словарь
        item["masked"] = new_masked
        item["correct"] = new_correct

        # обновляем статистику под новый ключ
        if word in STATS:
            STATS[new_masked] = STATS.pop(word)

        save_stats()

        return "ok"

    return render_template("letters_edit.html", word=item)