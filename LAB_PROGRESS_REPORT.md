# Lab Progress Report

## 1. Mock Baseline

Muc tieu cua buoc nay la chay thu benchmark voi mock runtime tren `data/hotpot_mini.json` de kiem tra scaffold ReAct/Reflexion truoc khi thay bang LLM that.

Lan chay dau gap loi:

```text
AttributeError: 'JudgeResult' object has no attribute 'score'
```

Nguyen nhan: `JudgeResult` va `ReflectionEntry` trong `src/reflexion_lab/schemas.py` van dang de trong (`pass`), trong khi `agents.py` can doc `judge.score`, `judge.reason` va luu reflection.

Da sua toi thieu 2 file:

- `src/reflexion_lab/schemas.py`: them field cho `JudgeResult` va `ReflectionEntry`.
- `src/reflexion_lab/agents.py`: noi Reflexion loop de khi sai thi goi `reflector()`, luu reflection vao trace va them `next_strategy` vao memory cho attempt sau.

Da chay thanh cong:

```bash
python run_benchmark.py --dataset data/hotpot_mini.json --out-dir outputs/sample_run
```

Output:

```json
{
  "react": {
    "count": 8,
    "em": 0.5,
    "avg_attempts": 1,
    "avg_token_estimate": 385,
    "avg_latency_ms": 200
  },
  "reflexion": {
    "count": 8,
    "em": 1.0,
    "avg_attempts": 1.5,
    "avg_token_estimate": 790,
    "avg_latency_ms": 455
  },
  "delta_reflexion_minus_react": {
    "em_abs": 0.5,
    "attempts_abs": 0.5,
    "tokens_abs": 405,
    "latency_abs": 255
  }
}
```

Autograde:

```text
Auto-grade total: 72/100
- Flow Score (Core): 52/80
  * Schema: 30/30
  * Experiment: 10/30
  * Analysis: 12/20
- Bonus Score: 20/20
```

Nhan xet: buoc mock baseline da hoan thanh. Reflexion dat EM cao hon ReAct vi mock runtime duoc thiet ke de mot so cau sai o attempt dau va dung sau khi co reflection memory. Diem autograde chua day du la hop ly vi `hotpot_mini.json` chi co 8 cau, nen report moi co 16 records sau khi chay ca ReAct va Reflexion. Token va latency hien van la gia tri hardcoded trong `agents.py`, chua phai so lieu thuc tu LLM.

## 2. Step 1: Understand Code Flow

Da doc va nam flow trong cac file chinh:

- `src/reflexion_lab/agents.py`: `run()` la vong lap chinh. ReAct chi chay 1 attempt; Reflexion co nhieu attempts. Moi attempt goi actor de tao answer, evaluator de cham diem, neu sai thi Reflexion goi reflector de tao reflection memory cho attempt tiep theo.
- `src/reflexion_lab/mock_runtime.py`: dang gia lap 3 thanh phan LLM. `actor_answer()` co tinh tra loi sai o mot so qid trong attempt dau, `evaluator()` cham dung/sai bang normalized exact match, `reflector()` tao strategy de attempt sau sua loi.
- `src/reflexion_lab/schemas.py`: dinh nghia data model cho dataset, attempt trace, run record, report payload, judge result va reflection entry. Phan `JudgeResult`/`ReflectionEntry` da duoc hoan thien de mock baseline chay duoc.
- `src/reflexion_lab/prompts.py`: hien van la TODO. Day se la noi viet system prompt cho Actor, Evaluator va Reflector khi thay mock runtime bang LLM that.

Ket luan: flow hien tai da ro. Scaffold dang tach 3 vai tro agent thanh actor, evaluator va reflector; viec tiep theo khi dung LLM that la thay logic trong `mock_runtime.py` bang call MiniMax-M3 va dung prompt tu `prompts.py`.

## 3. Step 2: Complete Scaffold TODOs

Da hoan thien cac TODO cot loi trong scaffold:

- `src/reflexion_lab/schemas.py`: dinh nghia `JudgeResult` voi `score`, `reason`, `missing_evidence`, `spurious_claims`; dinh nghia `ReflectionEntry` voi `attempt_id`, `failure_reason`, `lesson`, `next_strategy`.
- `src/reflexion_lab/agents.py`: trien khai Reflexion loop. Khi answer sai va van con attempt tiep theo, agent goi `reflector()`, gan reflection vao trace, luu vao `reflections`, va cap nhat `reflection_memory` bang `next_strategy`.
- `src/reflexion_lab/prompts.py`: viet system prompt cho Actor, Evaluator va Reflector. Evaluator va Reflector duoc yeu cau tra ve JSON dung schema de phuc vu buoc tich hop LLM that.

Da verify lai:

```bash
python run_benchmark.py --dataset data/hotpot_mini.json --out-dir outputs/sample_run
python autograde.py --report-path outputs/sample_run/report.json
```

Ket qua benchmark mock van on dinh: ReAct EM = 0.5, Reflexion EM = 1.0. Autograde van la 72/100, khong doi so voi buoc mock baseline vi dataset mini chi co 8 cau va token/latency van la gia tri mock hardcoded.

## 4. Step 3: Replace Mock Runtime With Real LLM

Da tich hop MiniMax-M3 theo OpenAI-compatible API trong `src/reflexion_lab/mock_runtime.py`.

Thay doi chinh:

- `actor_answer()`: gui `ACTOR_SYSTEM` + question + context + reflection memory toi LLM, tra ve final answer.
- `evaluator()`: gui `EVALUATOR_SYSTEM` + question + gold answer + predicted answer toi LLM, parse JSON thanh `JudgeResult`.
- `reflector()`: gui `REFLECTOR_SYSTEM` + question + failure reason toi LLM, parse JSON thanh `ReflectionEntry`.
- Giu lai fallback mock bang bien `REFLEXION_RUNTIME=mock` de debug/offline nhanh.
- Them `openai>=1.0` vao `requirements.txt`.
- Sua `run_benchmark.py` de report ghi dung `meta.mode`: mac dinh la `llm`, hoac `mock` khi set `REFLEXION_RUNTIME=mock`.

Da verify:

```bash
python run_benchmark.py --dataset data/hotpot_mini.json --out-dir outputs/minimax_smoke
python autograde.py --report-path outputs/minimax_smoke/report.json
```

Ket qua smoke benchmark voi MiniMax-M3:

```json
{
  "react": {
    "count": 8,
    "em": 1.0,
    "avg_attempts": 1,
    "avg_token_estimate": 385,
    "avg_latency_ms": 200
  },
  "reflexion": {
    "count": 8,
    "em": 1.0,
    "avg_attempts": 1,
    "avg_token_estimate": 505,
    "avg_latency_ms": 290
  },
  "delta_reflexion_minus_react": {
    "em_abs": 0.0,
    "attempts_abs": 0,
    "tokens_abs": 120,
    "latency_abs": 90
  }
}
```

Autograde van la 72/100 vi van chi chay tren `hotpot_mini.json` 8 cau. Report MiniMax da ghi `meta.mode = "llm"`.

Giai thich metric:

- `count`: so cau hoi duoc chay cho moi agent. O day ReAct va Reflexion moi agent chay 8 cau.
- `em`: exact match accuracy, tinh theo ty le cau dung. `1.0` nghia la dung 100%, `0.5` nghia la dung 50%.
- `avg_attempts`: so attempt trung binh moi cau. Reflexion co the lon hon 1 neu can reflection va thu lai.
- `avg_token_estimate`: token trung binh moi cau. Hien tai van la estimate hardcoded trong `agents.py`, chua phai token thuc tu MiniMax.
- `avg_latency_ms`: latency trung binh moi cau. Hien tai van la gia tri hardcoded trong `agents.py`, chua phai latency do thuc.
- `delta_reflexion_minus_react`: chenh lech theo cong thuc `Reflexion - ReAct`. `em_abs = 0.0` nghia la Reflexion khong cai thien EM so voi ReAct trong smoke test nay; `attempts_abs = 0` nghia la ca hai deu can trung binh 1 attempt; `tokens_abs = 120` va `latency_abs = 90` nghia la Reflexion dang ton them 120 token estimate va 90 ms estimate moi cau so voi ReAct.

Luu y: Bước 3 da thay mock bang LLM that, nhung `token_estimate` va `latency_ms` van la gia tri hardcoded trong `agents.py`. Phan nay thuoc task rieng ve token/latency thuc te.

## 5. Step 4: Dataset Sampling And Observable Benchmark

Da them script `make_hotpot_subset.py` de random 100 mau tu `data/hotpot_dev_distractor_v1.json` va chuyen sang format `QAExample`.

Lenh tao dataset:

```bash
python make_hotpot_subset.py --source data/hotpot_dev_distractor_v1.json --out data/hotpot_random_100.json --num-samples 100 --context-mode supporting
```

Da tao thanh cong `data/hotpot_random_100.json` voi 100 examples. `--context-mode supporting` chi lay cac paragraph supporting facts de request LLM gon hon va it timeout hon; co the dung `--context-mode full` neu muon benchmark kho hon voi distractor context day du.

Da cap nhat `run_benchmark.py`:

- Hien thi progress bar rieng cho ReAct va Reflexion.
- Hien qid dang xu ly.
- Them `--limit` de chay thu vai mau truoc khi chay du 100.

Da cap nhat `src/reflexion_lab/reporting.py`:

- `report.md` co bang Summary so sanh ReAct vs Reflexion.
- Them phan Interpretation giai thich delta.
- Them bang Per-question comparison gom gold answer, predicted answer, dung/sai, attempts va reflection count cho tung qid.

Da verify nhanh bang mock:

```bash
$env:REFLEXION_RUNTIME='mock'
python run_benchmark.py --dataset data/hotpot_mini.json --out-dir outputs/progress_smoke --limit 2
```

Ket qua: terminal hien progress va `outputs/progress_smoke/report.md` co bang so sanh chi tiet theo tung cau.
