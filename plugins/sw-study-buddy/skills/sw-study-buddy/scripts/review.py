#!/usr/bin/env python3
"""
Retenção do Study Buddy: repetição espaçada, pontos fracos, provas, streak e XP.

Lê/escreve <dir>/meta.json nos campos `reviews`, `fracos`, `exams`, `streak` e `xp`.
NÃO edite esses campos à mão — use sempre este script (ele cuida de datas, intervalos
e streak). O agente só interpreta a saída (JSON curto no stdout).

Uso:
  review.py --dir D --action due
  review.py --dir D --action add --topic 3 --concept "ownership"
  review.py --dir D --action ok --concept "ownership"
  review.py --dir D --action fail --concept "ownership"
  review.py --dir D --action done --concept "ownership"
  review.py --dir D --action exam --module 1 --score 4 --total 5 --missed "lifetimes" "drop order"
  review.py --dir D --action activity --xp 10
"""
import argparse
import json
import os
import sys
from datetime import date, timedelta

CAP = 30


def load(d):
    p = os.path.join(d, "meta.json")
    if not os.path.isfile(p):
        sys.exit(f"meta.json nao encontrado em {d}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(d, meta):
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")


def streak_bump(meta, today):
    """`today` e' um datetime.date; streak.last e' ISO string."""
    s = meta.setdefault("streak", {"count": 0, "best": 0, "last": None})
    if s.get("last") == today.isoformat():
        return
    yest = (today - timedelta(days=1)).isoformat()
    s["count"] = s.get("count", 0) + 1 if s.get("last") == yest else 1
    s["best"] = max(s.get("best", 0), s["count"])
    s["last"] = today.isoformat()


def add_fracos(meta, concept, topic, today):
    for fr in meta.setdefault("fracos", []):
        if fr.get("concept") == concept:
            fr["fails"] = fr.get("fails", 1) + 1
            fr["last"] = today
            return
    meta["fracos"].append({"concept": concept, "topic": topic, "fails": 1, "last": today})


def remove_fracos(meta, concept):
    meta["fracos"] = [f for f in meta.get("fracos", []) if f.get("concept") != concept]


def find_review(meta, concept):
    for r in meta.get("reviews", []):
        if r.get("concept") == concept:
            return r
    return None


def out(action, meta, **extra):
    s = meta.get("streak", {})
    payload = {
        "action": action,
        "xp": meta.get("xp", 0),
        "streak": s.get("count", 0),
        "streak_best": s.get("best", 0),
        "reviews_total": len(meta.get("reviews", [])),
        "fracos": [f["concept"] for f in meta.get("fracos", [])],
    }
    payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--action", required=True,
                    choices=["due", "add", "ok", "fail", "done", "exam", "activity"])
    ap.add_argument("--concept", default="")
    ap.add_argument("--topic", type=int, default=0)
    ap.add_argument("--module", type=int, default=0)
    ap.add_argument("--score", type=int, default=0)
    ap.add_argument("--total", type=int, default=0)
    ap.add_argument("--missed", nargs="*", default=[])
    ap.add_argument("--xp", type=int, default=0)
    args = ap.parse_args()

    d = os.path.expanduser(args.dir)
    meta = load(d)
    today = date.today()
    today_s = today.isoformat()
    tomorrow = (today + timedelta(days=1)).isoformat()

    if args.action == "due":
        due = [r for r in meta.get("reviews", []) if r.get("due", "9999") <= today_s]
        print(json.dumps(due, ensure_ascii=False))
        return

    if args.action in ("add", "ok", "fail", "done") and not args.concept:
        sys.exit(f"--concept e' obrigatorio para {args.action}")

    if args.action == "add":
        r = find_review(meta, args.concept)
        if r:
            r.update({"interval": 1, "strength": 0, "due": tomorrow, "topic": args.topic})
        else:
            meta.setdefault("reviews", []).append(
                {"concept": args.concept, "topic": args.topic, "due": tomorrow,
                 "interval": 1, "strength": 0})
        streak_bump(meta, today)
        save(d, meta)
        out("add", meta, concept=args.concept)

    elif args.action == "ok":
        r = find_review(meta, args.concept)
        if not r:
            sys.exit(f"conceito nao tem revisao agendada: {args.concept}")
        r["interval"] = min(max(r.get("interval", 1), 1) * 2, CAP)
        r["strength"] = r.get("strength", 0) + 1
        r["due"] = (today + timedelta(days=r["interval"])).isoformat()
        remove_fracos(meta, args.concept)
        meta["xp"] = meta.get("xp", 0) + 5
        streak_bump(meta, today)
        save(d, meta)
        out("ok", meta, concept=args.concept, next_due=r["due"])

    elif args.action == "fail":
        r = find_review(meta, args.concept)
        if r:
            r.update({"interval": 1, "strength": 0, "due": tomorrow})
        else:
            meta.setdefault("reviews", []).append(
                {"concept": args.concept, "topic": args.topic, "due": tomorrow,
                 "interval": 1, "strength": 0})
        add_fracos(meta, args.concept, r.get("topic", 0) if r else args.topic, today_s)
        streak_bump(meta, today)
        save(d, meta)
        out("fail", meta, concept=args.concept)

    elif args.action == "done":
        remove_fracos(meta, args.concept)
        streak_bump(meta, today)
        save(d, meta)
        out("done", meta, concept=args.concept)

    elif args.action == "exam":
        meta.setdefault("exams", []).append(
            {"module": args.module, "date": today_s, "score": args.score,
             "total": args.total, "missed": args.missed})
        for c in args.missed:
            add_fracos(meta, c, 0, today_s)
        meta["xp"] = meta.get("xp", 0) + 10
        streak_bump(meta, today)
        save(d, meta)
        out("exam", meta, module=args.module, score=f"{args.score}/{args.total}")

    elif args.action == "activity":
        meta["xp"] = meta.get("xp", 0) + args.xp
        streak_bump(meta, today)
        save(d, meta)
        out("activity", meta, xp_ganho=args.xp)


if __name__ == "__main__":
    main()
