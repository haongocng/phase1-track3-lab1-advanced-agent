from __future__ import annotations
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from .schemas import ReportPayload, RunRecord

def summarize(records: list[RunRecord]) -> dict:
    grouped: dict[str, list[RunRecord]] = defaultdict(list)
    for record in records:
        grouped[record.agent_type].append(record)
    summary: dict[str, dict] = {}
    for agent_type, rows in grouped.items():
        summary[agent_type] = {"count": len(rows), "em": round(mean(1.0 if r.is_correct else 0.0 for r in rows), 4), "avg_attempts": round(mean(r.attempts for r in rows), 4), "avg_token_estimate": round(mean(r.token_estimate for r in rows), 2), "avg_latency_ms": round(mean(r.latency_ms for r in rows), 2)}
    if "react" in summary and "reflexion" in summary:
        summary["delta_reflexion_minus_react"] = {"em_abs": round(summary["reflexion"]["em"] - summary["react"]["em"], 4), "attempts_abs": round(summary["reflexion"]["avg_attempts"] - summary["react"]["avg_attempts"], 4), "tokens_abs": round(summary["reflexion"]["avg_token_estimate"] - summary["react"]["avg_token_estimate"], 2), "latency_abs": round(summary["reflexion"]["avg_latency_ms"] - summary["react"]["avg_latency_ms"], 2)}
    return summary

def failure_breakdown(records: list[RunRecord]) -> dict:
    grouped: dict[str, Counter] = defaultdict(Counter)
    for record in records:
        grouped[record.agent_type][record.failure_mode] += 1
    return {agent: dict(counter) for agent, counter in grouped.items()}

def build_report(records: list[RunRecord], dataset_name: str, mode: str = "mock") -> ReportPayload:
    examples = [{"qid": r.qid, "agent_type": r.agent_type, "gold_answer": r.gold_answer, "predicted_answer": r.predicted_answer, "is_correct": r.is_correct, "attempts": r.attempts, "failure_mode": r.failure_mode, "reflection_count": len(r.reflections)} for r in records]
    return ReportPayload(meta={"dataset": dataset_name, "mode": mode, "num_records": len(records), "agents": sorted({r.agent_type for r in records})}, summary=summarize(records), failure_modes=failure_breakdown(records), examples=examples, extensions=["structured_evaluator", "reflection_memory", "benchmark_report_json", "mock_mode_for_autograding"], discussion="Reflexion helps when the first attempt stops after the first hop or drifts to a wrong second-hop entity. The tradeoff is higher attempts, token cost, and latency. In a real report, students should explain when the reflection memory was useful, which failure modes remained, and whether evaluator quality limited gains.")

def comparison_rows(report: ReportPayload) -> list[dict]:
    grouped: dict[str, dict[str, dict]] = defaultdict(dict)
    for example in report.examples:
        grouped[example["qid"]][example["agent_type"]] = example

    rows = []
    for qid, pair in sorted(grouped.items()):
        react = pair.get("react", {})
        reflexion = pair.get("reflexion", {})
        rows.append(
            {
                "qid": qid,
                "gold": react.get("gold_answer") or reflexion.get("gold_answer", ""),
                "react_answer": react.get("predicted_answer", ""),
                "react_correct": react.get("is_correct", False),
                "react_attempts": react.get("attempts", 0),
                "reflexion_answer": reflexion.get("predicted_answer", ""),
                "reflexion_correct": reflexion.get("is_correct", False),
                "reflexion_attempts": reflexion.get("attempts", 0),
                "reflections": reflexion.get("reflection_count", 0),
            }
        )
    return rows

def short_cell(value: object, limit: int = 80) -> str:
    text = str(value).replace("\n", " ").replace("|", "\\|")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."

def yes_no(value: object) -> str:
    return "yes" if bool(value) else "no"

def interpret_summary(react: dict, reflexion: dict, delta: dict) -> str:
    em_delta = delta.get("em_abs", 0)
    token_delta = delta.get("tokens_abs", 0)
    latency_delta = delta.get("latency_abs", 0)
    attempt_delta = delta.get("attempts_abs", 0)
    lines = [
        f"- Accuracy delta is {em_delta}: Reflexion {'improved' if em_delta > 0 else 'matched' if em_delta == 0 else 'underperformed'} ReAct on EM.",
        f"- Attempt delta is {attempt_delta}: Reflexion used {'more' if attempt_delta > 0 else 'the same number of' if attempt_delta == 0 else 'fewer'} attempts on average.",
        f"- Token estimate delta is {token_delta}: positive values mean Reflexion is more expensive per example.",
        f"- Latency delta is {latency_delta} ms: positive values mean Reflexion is slower per example.",
    ]
    if react.get("em") == reflexion.get("em") and token_delta > 0:
        lines.append("- In this run, Reflexion did not improve accuracy but still added estimated cost/latency overhead.")
    return "\n".join(lines)

def save_report(report: ReportPayload, out_dir: str | Path) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "report.json"
    md_path = out_dir / "report.md"
    json_path.write_text(json.dumps(report.model_dump(), indent=2), encoding="utf-8")
    s = report.summary
    react = s.get("react", {})
    reflexion = s.get("reflexion", {})
    delta = s.get("delta_reflexion_minus_react", {})
    detail_lines = [
        "| QID | Gold | ReAct | ReAct ok | ReAct attempts | Reflexion | Reflexion ok | Reflexion attempts | Reflections |",
        "|---|---|---|---:|---:|---|---:|---:|---:|",
    ]
    for row in comparison_rows(report):
        detail_lines.append(
            "| {qid} | {gold} | {react_answer} | {react_correct} | {react_attempts} | {reflexion_answer} | {reflexion_correct} | {reflexion_attempts} | {reflections} |".format(
                qid=short_cell(row["qid"], 24),
                gold=short_cell(row["gold"], 50),
                react_answer=short_cell(row["react_answer"], 50),
                react_correct=yes_no(row["react_correct"]),
                react_attempts=row["react_attempts"],
                reflexion_answer=short_cell(row["reflexion_answer"], 50),
                reflexion_correct=yes_no(row["reflexion_correct"]),
                reflexion_attempts=row["reflexion_attempts"],
                reflections=row["reflections"],
            )
        )
    detail_table = "\n".join(detail_lines)
    ext_lines = "\n".join(f"- {item}" for item in report.extensions)
    md = f"""# Lab 16 Benchmark Report

## Metadata
- Dataset: {report.meta['dataset']}
- Mode: {report.meta['mode']}
- Records: {report.meta['num_records']}
- Agents: {', '.join(report.meta['agents'])}

## Summary
| Metric | ReAct | Reflexion | Delta |
|---|---:|---:|---:|
| EM | {react.get('em', 0)} | {reflexion.get('em', 0)} | {delta.get('em_abs', 0)} |
| Avg attempts | {react.get('avg_attempts', 0)} | {reflexion.get('avg_attempts', 0)} | {delta.get('attempts_abs', 0)} |
| Avg token estimate | {react.get('avg_token_estimate', 0)} | {reflexion.get('avg_token_estimate', 0)} | {delta.get('tokens_abs', 0)} |
| Avg latency (ms) | {react.get('avg_latency_ms', 0)} | {reflexion.get('avg_latency_ms', 0)} | {delta.get('latency_abs', 0)} |

## Interpretation
{interpret_summary(react, reflexion, delta)}

## Per-question comparison
{detail_table}

## Failure modes
```json
{json.dumps(report.failure_modes, indent=2)}
```

## Extensions implemented
{ext_lines}

## Discussion
{report.discussion}
"""
    md_path.write_text(md, encoding="utf-8")
    return json_path, md_path
