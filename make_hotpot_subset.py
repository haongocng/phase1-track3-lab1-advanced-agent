from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def convert_item(item: dict, context_mode: str) -> dict:
    supporting_titles = {title for title, _ in item.get("supporting_facts", [])}
    context = item["context"]
    if context_mode == "supporting":
        context = [entry for entry in context if entry[0] in supporting_titles] or context

    return {
        "qid": item["_id"],
        "difficulty": item.get("level", "medium"),
        "question": item["question"],
        "gold_answer": item["answer"],
        "context": [
            {"title": title, "text": "".join(sentences)}
            for title, sentences in item["context"]
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a random QAExample subset from HotpotQA.")
    parser.add_argument("--source", default="data/hotpot_dev_distractor_v1.json")
    parser.add_argument("--out", default="data/hotpot_random_100.json")
    parser.add_argument("--num-samples", type=int, default=100)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--context-mode", choices=["supporting", "full"], default="supporting")
    args = parser.parse_args()

    source = Path(args.source)
    out = Path(args.out)
    raw = json.loads(source.read_text(encoding="utf-8"))

    rng = random.Random(args.seed)
    sample_size = min(args.num_samples, len(raw))
    sampled = rng.sample(raw, sample_size)
    converted = [convert_item(item, args.context_mode) for item in sampled]

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(converted, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {sample_size} examples to {out}")


if __name__ == "__main__":
    main()
