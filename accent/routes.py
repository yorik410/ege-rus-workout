import csv
import random
import re

from flask import Flask, render_template, request, session, Blueprint

import json
from pathlib import Path


STATS_FILE = Path("accent/stats.json")

if STATS_FILE.exists():
    with open(STATS_FILE, encoding="utf-8") as f:
        STATS = json.load(f)
else:
    STATS = {}

EXCLUDED_FILE = Path("accent/excluded.json")

if EXCLUDED_FILE.exists():
    with open(EXCLUDED_FILE, encoding="utf-8") as f:
        EXCLUDED = json.load(f)
else:
    EXCLUDED = {}

bp = Blueprint("accent", __name__)


def save_stats():
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(
            STATS,
            f,
            ensure_ascii=False,
            indent=4
        )


def save_excluded():
    with open(EXCLUDED_FILE, "w", encoding="utf-8") as f:
        json.dump(EXCLUDED, f, ensure_ascii=False, indent=4)


def load_dictionary():
    words = []

    with open("dicts/4.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            word_raw = row["слово"].strip()
            stressed_raw = row["ударение"].strip()

            note = ""

            m = re.match(r"^(.*?)\s*\((.*)\)$", word_raw)
            if m:
                word = m.group(1).strip().replace("ё", "е")
                note = m.group(2).strip()

                stressed = re.sub(r"\s*\(.*\)$", "", stressed_raw).strip()
            else:
                word = word_raw.replace("ё", "е")
                stressed = stressed_raw

            stress_index = None

            # for i, (a, b) in enumerate(zip(word, stressed)):
            #     if a != b:
            #         stress_index = i
            #         break
            for idx, i in enumerate(stressed):
                if i.isupper():
                    stress_index = idx
                    break

            if stress_index is None:
                continue

            if len([c for c in word if c.lower() in "аеёиоуыэюя"]) <= 1:
                if word in STATS:
                    STATS.pop(word)
                    save_stats()
                continue

            words.append({
                "word": word,
                "note": note,
                "stress_index": stress_index,
                "stressed": stressed
            })

    return words


WORDS = [w for w in load_dictionary() if w["word"] not in EXCLUDED]


def get_weights():
    weights = []

    for word in WORDS:
        stat = STATS.get(word["word"])

        if not stat:
            weights.append(1)
            continue

        weights.append(max(1, 1 + stat["wrong"] * 4 - stat["correct"]))
    return weights


def needed_correct(target, correct, wrong):
    total = correct + wrong
    if total == 0:
        return 0

    x = (target * total - correct) / (1 - target)
    return max(0, int(x))


targets = [0.8, 0.9, 0.95, 0.98, 0.99]


@bp.route("/accent", methods=["GET", "POST"])
def accent():
    result = None

    if request.method == "POST":
        chosen = int(request.form["letter"])

        word_data = session["current"]

        correct = chosen == word_data["stress_index"]

        key = word_data["word"]

        if key not in STATS:
            STATS[key] = {
                "correct": 0,
                "wrong": 0
            }

        if correct:
            STATS[key]["correct"] += 1
        else:
            STATS[key]["wrong"] += 1

        save_stats()

        result = {
            "correct": correct,
            "answer": word_data["stressed"]
        }

    weights = get_weights()

    word_data = random.choices(
        WORDS,
        weights=weights,
        k=1
    )[0]

    session["current"] = word_data

    total_correct = sum(v["correct"] for v in STATS.values())
    total_wrong = sum(v["wrong"] for v in STATS.values())

    progress = []

    for t in targets:
        progress.append({
            "target": int(t * 100),
            "need": needed_correct(t, total_correct, total_wrong)
        })

    total = total_correct + total_wrong

    accuracy = (
        round(total_correct / total * 100, 1)
        if total else 0
    )

    return render_template(
        "index_accent.html",
        word=word_data["word"],
        note=word_data["note"],
        result=result,
        accuracy=accuracy,
        seen=len(STATS),
        words_count=len(WORDS),
        total_correct=total_correct,
        total_wrong=total_wrong,
        progress=progress
    )


@bp.route("/accent/exclude/<word>")
def accent_exclude(word):
    EXCLUDED[word] = True
    save_excluded()
    return "ok"


@bp.route("/accent/stats")
def accent_stats_page():
    data = []

    for word in WORDS:
        key = word["word"]
        stat = STATS.get(key, {"correct": 0, "wrong": 0})

        weight = max(1, 1 + stat["wrong"] * 4 - stat["correct"])

        data.append({
            "word": key,
            "note": word["note"],
            "correct": stat["correct"],
            "wrong": stat["wrong"],
            "weight": weight
        })

    top_wrong = filter(lambda y: y["wrong"] != 0, sorted(data, key=lambda x: x["wrong"], reverse=True)[:20])
    top_weight = filter(lambda y: y["weight"] != 1, sorted(data, key=lambda x: x["weight"], reverse=True)[:20])

    return render_template(
        "stats_accent.html",
        top_wrong=top_wrong,
        top_weight=top_weight
    )

