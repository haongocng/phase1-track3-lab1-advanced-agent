from __future__ import annotations
import json
import os
from pathlib import Path
import typer
from rich import print
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from dotenv import load_dotenv
from src.reflexion_lab.agents import ReActAgent, ReflexionAgent
from src.reflexion_lab.reporting import build_report, save_report
from src.reflexion_lab.utils import load_dataset, save_jsonl
app = typer.Typer(add_completion=False)


def run_agent(agent, examples, label: str):
    records = []
    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task(label, total=len(examples))
        for example in examples:
            progress.update(task, description=f"{label}: {example.qid}")
            records.append(agent.run(example))
            progress.advance(task)
    return records


@app.command()
def main(dataset: str = "data/hotpot_mini.json", out_dir: str = "outputs/sample_run", reflexion_attempts: int = 3, limit: int | None = None) -> None:
    load_dotenv()
    examples = load_dataset(dataset)
    if limit is not None:
        examples = examples[:limit]
    react = ReActAgent()
    reflexion = ReflexionAgent(max_attempts=reflexion_attempts)
    print(f"[cyan]Dataset[/cyan]: {dataset} ({len(examples)} examples)")
    print(f"[cyan]Runtime[/cyan]: {os.getenv('REFLEXION_RUNTIME', 'llm').strip().lower()}")
    react_records = run_agent(react, examples, "ReAct")
    reflexion_records = run_agent(reflexion, examples, "Reflexion")
    all_records = react_records + reflexion_records
    out_path = Path(out_dir)
    save_jsonl(out_path / "react_runs.jsonl", react_records)
    save_jsonl(out_path / "reflexion_runs.jsonl", reflexion_records)
    mode = os.getenv("REFLEXION_RUNTIME", "llm").strip().lower()
    report = build_report(all_records, dataset_name=Path(dataset).name, mode=mode)
    json_path, md_path = save_report(report, out_path)
    print(f"[green]Saved[/green] {json_path}")
    print(f"[green]Saved[/green] {md_path}")
    print(json.dumps(report.summary, indent=2))

if __name__ == "__main__":
    app()
