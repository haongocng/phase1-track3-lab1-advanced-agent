from __future__ import annotations

import json
import os
import re
import time
from functools import lru_cache

from dotenv import load_dotenv

from .prompts import ACTOR_SYSTEM, EVALUATOR_SYSTEM, REFLECTOR_SYSTEM
from .schemas import QAExample, JudgeResult, ReflectionEntry
from .utils import normalize_answer

FIRST_ATTEMPT_WRONG = {"hp2": "London", "hp4": "Atlantic Ocean", "hp6": "Red Sea", "hp8": "Andes"}
FAILURE_MODE_BY_QID = {"hp2": "incomplete_multi_hop", "hp4": "wrong_final_answer", "hp6": "entity_drift", "hp8": "entity_drift"}


def actor_answer(example: QAExample, attempt_id: int, agent_type: str, reflection_memory: list[str]) -> str:
    if _use_mock_runtime():
        return _mock_actor_answer(example, attempt_id, agent_type, reflection_memory)

    user_prompt = "\n\n".join(
        [
            f"Question: {example.question}",
            f"Difficulty: {example.difficulty}",
            "Context:\n" + _format_context(example),
            "Reflection memory:\n" + _format_reflection_memory(reflection_memory),
            f"Attempt: {attempt_id}",
            f"Agent type: {agent_type}",
            "Return only the final answer.",
        ]
    )
    return _chat(ACTOR_SYSTEM, user_prompt).strip()


def evaluator(example: QAExample, answer: str) -> JudgeResult:
    if _use_mock_runtime():
        return _mock_evaluator(example, answer)

    user_prompt = "\n\n".join(
        [
            f"Question: {example.question}",
            f"Gold answer: {example.gold_answer}",
            f"Predicted answer: {answer}",
            "Return the evaluation JSON only.",
        ]
    )
    payload = _parse_json_object(_chat(EVALUATOR_SYSTEM, user_prompt))
    return JudgeResult.model_validate(payload)


def reflector(example: QAExample, attempt_id: int, judge: JudgeResult) -> ReflectionEntry:
    if _use_mock_runtime():
        return _mock_reflector(example, attempt_id, judge)

    user_prompt = "\n\n".join(
        [
            f"Attempt ID: {attempt_id}",
            f"Question: {example.question}",
            f"Gold answer: {example.gold_answer}",
            f"Failure reason: {judge.reason}",
            "Missing evidence:\n" + "\n".join(f"- {item}" for item in judge.missing_evidence),
            "Spurious claims:\n" + "\n".join(f"- {item}" for item in judge.spurious_claims),
            "Return the reflection JSON only.",
        ]
    )
    payload = _parse_json_object(_chat(REFLECTOR_SYSTEM, user_prompt))
    payload["attempt_id"] = int(payload.get("attempt_id", attempt_id))
    return ReflectionEntry.model_validate(payload)


def _mock_actor_answer(example: QAExample, attempt_id: int, agent_type: str, reflection_memory: list[str]) -> str:
    if example.qid not in FIRST_ATTEMPT_WRONG:
        return example.gold_answer
    if agent_type == "react":
        return FIRST_ATTEMPT_WRONG[example.qid]
    if attempt_id == 1 and not reflection_memory:
        return FIRST_ATTEMPT_WRONG[example.qid]
    return example.gold_answer


def _mock_evaluator(example: QAExample, answer: str) -> JudgeResult:
    if normalize_answer(example.gold_answer) == normalize_answer(answer):
        return JudgeResult(score=1, reason="Final answer matches the gold answer after normalization.")
    if normalize_answer(answer) == "london":
        return JudgeResult(
            score=0,
            reason="The answer stopped at the birthplace city and never completed the second hop to the river.",
            missing_evidence=["Need to identify the river that flows through London."],
            spurious_claims=[],
        )
    return JudgeResult(
        score=0,
        reason="The final answer selected the wrong second-hop entity.",
        missing_evidence=["Need to ground the answer in the second paragraph."],
        spurious_claims=[answer],
    )


def _mock_reflector(example: QAExample, attempt_id: int, judge: JudgeResult) -> ReflectionEntry:
    strategy = (
        "Do the second hop explicitly: birthplace city -> river through that city."
        if example.qid == "hp2"
        else "Verify the final entity against the second paragraph before answering."
    )
    return ReflectionEntry(
        attempt_id=attempt_id,
        failure_reason=judge.reason,
        lesson="A partial first-hop answer is not enough; the final answer must complete all hops.",
        next_strategy=strategy,
    )


def _use_mock_runtime() -> bool:
    load_dotenv()
    return os.getenv("REFLEXION_RUNTIME", "llm").strip().lower() == "mock"


def _format_context(example: QAExample) -> str:
    return "\n".join(f"[{chunk.title}] {chunk.text}" for chunk in example.context)


def _format_reflection_memory(reflection_memory: list[str]) -> str:
    if not reflection_memory:
        return "(none)"
    return "\n".join(f"- {item}" for item in reflection_memory)


def _parse_json_object(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    if not cleaned.startswith("{"):
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise ValueError(f"LLM response did not contain a JSON object: {text}")
        cleaned = match.group(0)
    return json.loads(cleaned)


def _chat(system_prompt: str, user_prompt: str) -> str:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = _client().chat.completions.create(
                model=_model(),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                timeout=90,
            )
            break
        except Exception as exc:
            last_error = exc
            if attempt == 3:
                raise
            time.sleep(2 * attempt)
    else:
        raise RuntimeError("LLM call failed without an exception.") from last_error

    content = response.choices[0].message.content
    if not content:
        raise ValueError("LLM returned an empty response.")
    return content


@lru_cache(maxsize=1)
def _client():
    load_dotenv()
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Missing dependency: install openai or run pip install -r requirements.txt") from exc

    api_key = os.getenv("MINIMAX_API_KEY")
    base_url = os.getenv("MINIMAX_BASE_URL", "https://api.tokenrouter.com/v1")
    if not api_key:
        raise RuntimeError("Missing MINIMAX_API_KEY. Configure it in the environment or .env file.")
    return OpenAI(api_key=api_key, base_url=base_url)


def _model() -> str:
    load_dotenv()
    return os.getenv("MINIMAX_MODEL", "MiniMax-M3")
