# HH Goa 2026 — Voice-Enabled RAG Pipeline

[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg)](LICENSE)
[![Task](https://img.shields.io/badge/HH_Goa-Task_%232-blue.svg)](https://hhgoa.com)
[![STT](https://img.shields.io/badge/STT-ElevenLabs_Scribe_v2-purple.svg)](https://elevenlabs.io)
[![Dataset](https://img.shields.io/badge/Dataset-ai4bharat%2FMSMARCO--XI_(344_passages)-orange.svg)](https://huggingface.co/datasets/ai4bharat/MSMARCO-XI)
[![Fast path](https://img.shields.io/badge/Fast_path-P50_1.51ms_·_P100_11.18ms_%3C_50ms-brightgreen.svg)](#latency-task-req-3--4)
[![Python](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org)

Voice in → transcript → **cited extractive answer in under 50ms** → optional Groq polish.
Built for **Hacker House Goa 2026, Task #2**.

The extractive answer is computed **before** generation and never depends on it.
That is the number the 50ms budget is measured against.

---

## Requirements → where they live

| # | Requirement | What we ship |
|---|---|---|
| 1 | STT (Sarvam **or** ElevenLabs) | ElevenLabs `scribe_v2` (`stt/engine.py`). Sarvam is optional, off by default. |
| 2 | Chunking must be vast | Three strategies, swappable (`chunking/strategies.py`). Indexed subset: **344 MSMARCO-XI passages**, not the full 100M-passage corpus. |
| 3 | Chunking + retrieval + **final output &lt; 50ms** | Two-tier: extractive span is the final local output. **P50 1.51ms / P100 11.18ms.** |
| 4 | P50 / P70 / P100 on many queries | `python -m app.benchmark` and `GET /api/benchmark?n=80` |
| 5 | Harness | Typed `BaseStep` / `StepResult`, retries, structured I/O (`harness/`) |
| 6 | Know when not to answer | Layers 1–3 refuse before generation. Layers 4–5 reject a bad polish and **keep the extractive span**. |

---

## Architecture

```
Voice ──► ElevenLabs STT          ← outside the 50ms window (~0.9–1.9s)
              │
              ▼
     ┌─ 50ms BUDGET ─────────────────────────────────────┐
     │  intent guard (L1)                                 │
     │  TF-IDF retrieve                                   │
     │  grounding gate (L2–L3)                            │
     │  extractive span + support                         │
     │           ▼                                        │
     │     FAST ANSWER     P50 1.51ms                     │
     └────────────────────────────────────────────────────┘
              │
              ▼
     Groq polish (optional)       ← outside the budget (~0.7–2s)
     L4 numeric/lexical check
     L5 hedge check
           │
           ├── polish passes  → show generated
           └── polish fails   → keep extractive
```

`POST /ask` `{ "question", "generate": false }` is the measured path.
`generate: true` may replace the span. It cannot delete it.

---

## Latency (Task req #3 / #4)

**Window:** transcript → extractive answer  
(`retrieve + guardrail + extract`, `generate=false`).  
STT and Groq are reported separately and are **not** inside the 50ms target.

Two measurements, same code path:

| Source | n | P50 | P70 | P100 | Under 50ms |
|---|---:|---:|---:|---:|---:|
| CLI `python benchmarks/fastpath.py --n 80` | 80 | 1.53 ms | 2.05 ms | 7.26 ms | 80/80 |
| **Live process `GET /api/benchmark?n=80`** ← publish this | 80 | **1.51 ms** | **1.83 ms** | **11.18 ms** | **80/80** |

Stage breakdown (CLI run, n=80, 8 warmup discarded, machine `shikhar-ubuntu`):

| Stage | P50 | P70 | P100 |
|---|---:|---:|---:|
| Retrieval | 0.37 ms | 0.43 ms | 2.95 ms |
| Guardrail | 0.02 ms | 0.02 ms | 7.11 ms |
| Extract | 1.02 ms | 1.15 ms | 3.70 ms |
| **Fast path** | **1.53 ms** | **2.05 ms** | **7.26 ms** |
| LLM | 0 (not called) | — | — |

Answer sources on that run: **74 extractive, 6 Layer-3 OOD refusals** (cake / Shor / Apple / World Cup / fusion).

Reproduce:

```bash
python -m app.benchmark
python benchmarks/fastpath.py --n 80
curl -s "http://127.0.0.1:8000/api/benchmark?n=80"
```

Do **not** use `python -m benchmarks.run_benchmarks` for the 50ms claim. That script calls Groq and is outside the official window.

STT + Groq, for honesty, sit in a different table (audio n=7, real ElevenLabs):

| Stage | P50 | P100 |
|---|---:|---:|
| ElevenLabs STT | ~1.13 s | ~1.94 s |
| Groq polish | ~1.05 s | ~5.7 s |
| Fast path (same process) | 2.97 ms | 4.24 ms |

---

## Chunking (Task req #2)

MSMARCO-XI rows are **queries**, each carrying ~10 passages. We indexed a **30-query validation slice → 344 passages** (Hindi + Bengali shards interleaved). Calling this “the complete dataset” would be false; the full train set is hundreds of thousands of queries per language.

Three strategies, same 344-passage text, query-time index uses `recursive_sentence`:

| Strategy | Chunks | Avg length | Boundary |
|---|---:|---:|---|
| `fixed_window` | 406 | 299 chars | 300-char window, 60-char overlap |
| `recursive_sentence` ← served | 306 | 316 chars | sentence terminators, 60-word pack |
| `semantic_paragraph` | 344 | 281 chars | `\n\n` then sentence fallback |

This table is **chunk statistics**, not retrieval quality. MSMARCO passages are already retrieval-sized, so at these budgets most strategies emit ~1 chunk/passage — a known null. A gold-label MRR ablation belongs in a later increment; we are not pretending the count table is that ablation.

```bash
python -m chunking.benchmark
```

---

## Guardrails (Task req #6)

Intent is not a similarity score. Layers 1–3 run **before** any extract/generate. Layers 4–5 run on the **generated** text only; a failed polish leaves the extractive span standing.

| Layer | When | What |
|---|---|---|
| 1 Safety | before retrieve | injection / weapons / exploit patterns |
| 2 Empty context | after retrieve | zero hits |
| 3 Off-topic | after retrieve | cosine &lt; `SIMILARITY_THRESHOLD` (default **0.15**) |
| 4 Faithfulness | after generate | invented numbers, stemmed overlap |
| 5 Hedge | after generate | “I do not have information…” |

Layer 3 is the OOD backstop that produced the 6 refusals in the fast-path bench (similarity 0.00–0.12 vs 0.15).

An older 35-query precision/recall run (`benchmarks/guardrail_eval.py`) reported 85.7–88.6% accuracy when Layer 4/5 still flipped `refused=True`. After the two-tier change those layers no longer refuse the *request* — they reject the polish. **Do not re-run that script and republish 87% against the current orchestrator.**

---

## Harness (Task req #5)

`harness/orchestrator.py` is one typed call:

1. STT (or `text_override`)
2. Retrieve
3. Layers 1–3
4. Extractive span ← `fast_path_ms` stops here
5. Optional generate
6. Layers 4–5 on generated text only

Retries with jitter live in `harness/retry.py` (429 `Retry-After` respected). Every stage returns `StepResult`. Nothing raises out of `process()`.

---

## Quickstart

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# ELEVENLABS_API_KEY=...     # voice
# GROQ_API_KEY=...           # polish only; fast path works without it

python -m dataset.loader --samples 30 --strategy recursive_sentence
python -m app.benchmark          # official 50ms numbers, no API keys
python app.py                    # http://127.0.0.1:8000
```

```bash
curl -s http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"what is a corporation?","generate":false}'
```

Expect `answer_source: "extractive"`, `timings.generation: 0`, `fast_path_ms` well under 50.

---

## API

| Endpoint | Purpose |
|---|---|
| `POST /ask` `{question, generate}` | text → answer. `generate=false` is the budget path |
| `POST /api/query` | audio and/or `text_override`, same `generate` flag |
| `GET /api/benchmark?n=80` | live P50/P70/P100 over the fast path |
| `GET /health` | passage count, 50ms budget |
| `GET /api/metrics` | SQLite percentiles |

---

## Configuration

| Variable | Purpose |
|---|---|
| `ELEVENLABS_API_KEY` | Primary STT |
| `SARVAM_API_KEY` | Optional STT fallback (disabled in the graded path) |
| `GROQ_API_KEY` | Polish only. Fast path and `/api/benchmark` do not need it |
| `HF_TOKEN` | Optional, dataset download |
| `SIMILARITY_THRESHOLD` | Layer 3 gate (default `0.15`) |

---

## Repository

```text
app.py                      FastAPI + demo UI
app/benchmark.py            dashboard wrapper around the fast path
benchmarks/fastpath.py      official <50ms bench (no Groq)
benchmarks/run_benchmarks.py  old Groq+STT suite — not the 50ms number
retrieval/extractive.py     sentence picker over the retrieved window
retrieval/vector_store.py   in-memory TF-IDF cosine index
harness/orchestrator.py     two-tier pipeline
chunking/strategies.py      three chunkers
dataset/loader.py           MSMARCO-XI subset ingest
```

---

## License

MIT. See [LICENSE](LICENSE).
