---
artifact_type: experiment-result
id: EXP-05-result
version: 1
status: DRAFT
created_at: 2026-11-11
updated_at: 2026-11-11
derived_from: [experiments/EXP-05-n150-vllm-tuning/plan.md@1]
source_files: [experiments/EXP-05-n150-vllm-tuning/raw, scripts/lc.sh, scripts/seq.sh, scripts/analyze.py, experiments/EXP-05-n150-vllm-tuning/plots/tuning.py]
verification_status: ANALYZED
produced_by: ai-draft
---

# EXP-05 result: vLLM tuning on the n150, one setting per server
## Provenance
- Provided by: agent-run, 2026-11-11, `~/exp-n150-20261111/` on the node (copy of research/scripts), one `seq.sh` call per stage:
  tune-base 08:33:57Z, tune-sod 08:46:20Z, tune-notrace 09:01:43Z, tune-b16 09:14:34Z, tune-len2k 09:28:36Z, tune-nowarm
  09:40:07Z, cache 09:46:02Z-09:53:06Z (raw/seq/chain.log). All stages exit 0.
- hf-token (.env TOKEN) existed in u-testuser 08:33:56Z until the cleanup after 09:53Z; deleted with configmaps llm-spec*. The
  hostPath dir /home/testuser/.cache/tt-vllm-cache was removed by a root helper pod (raw/state/cache-cleanup.txt, transcribed).
  State before/after (raw/state/) identical apart from timestamps and ages; kernel 7.0.0-38, firmware 19.13.1.0, tt-kmd 2.11.0
  (raw/env/host.txt). Other users' MI210 workloads kept running.
- Raw: raw/runs/<setting>-r<rep>/ (lc.sh output: load objects, server-full.log, DRA log, device-fds, query, telemetry, bench/).
  Processed: processed/throughput*.csv, processed/tuning-lifecycle.csv. Plot: plots/tuning.{pdf,png}.
## Runs
8 loads (base, sod, notrace, b16, len2k, nowarm, cache r1, cache r2); every one: Workload tenstorrent.com/chip 1, claim tt-0,
`VLLM::EngineCore` holds 2 /dev/tenstorrent fds, /health 200, /v1/models lists the model, chat.py and curl answered. analyze.py
asserts each setting in the server log (TTModelRunner line, non-default args) and that only cache r2 skipped the download.
60 bench runs (5 settings x 3 concurrencies x 3), every request 128 output tokens.
## Anomalies
- The same-day base is slower than EXP-04 vllm-a (same image, same spec): output tok/s -12.4 % (c1), -12.6 % (c8), -18.1 % (c32);
  TPOT at c1 59.4 vs 52.0 ms. Cause not tested (shared node, other users' MI210 jobs running; day-to-day variance). Claim B0
  rejected; per plan, EXP-05 is compared with its own base only. Settings ran one after another over 80 min with no repeated base
  at the end, so differences of about 10 % or less may include drift.
- Weight download time varied from 62 to 170 s across loads (Hugging Face network), so submit -> Ready mixes download with the
  setting; load comparisons below use phases from the server log.
- The `~/.cache` mount of llm-cache.yaml stayed empty (4.0K, raw/state/cache-cleanup.txt, hand transcription): the kernel compile
  cache was not persisted. Why is not tested: it may live elsewhere, or $HOME may differ under runAsUser 0. Only cache_root (6.2 GB: weights + converted tensor cache) was persisted.
- With on-device sampling the prefill warmup ran 30 times (5 lengths x 6 sampling-parameter sets; base 5) and captured a second
  decode trace; engine init 100.5 s.
## Results
Throughput (mean of 3, output tok/s; change vs same-day base) and TPOT / TTFT means (processed/throughput-summary.csv):

| ID | Setting | c1 | c8 | c32 | TPOT c1 (ms) | TTFT c1 / c32 (ms) |
|---|---|---|---|---|---|---|
| EXP-05#R1 | base | 16.8 | 98.4 | 329.1 | 59.4 | 88 / 1257 |
| EXP-05#R2 | sod (`sample_on_device_mode: all`) | 11.7 (-30.0 %) | 88.7 (-9.9 %) | 294.9 (-10.4 %) | 84.9 (x1.43) | 115 / 2930 |
| EXP-05#R3 | notrace (`trace_mode: none`) | 14.9 (-11.5 %) | 90.0 (-8.5 %) | 311.5 (-5.3 %) | 67.1 (x1.13) | 93 / 1291 |
| EXP-05#R4 | b16 (`max_num_seqs 16`) | 17.0 (+1.6 %) | 101.2 (+2.8 %) | 195.6 (-40.6 %) | 58.4 (x0.98) | 89 / 8514 |
| EXP-05#R5 | len2k (`max_model_len 2048`) | 16.8 (-0.1 %) | 99.1 (+0.7 %) | 361.2 (+9.8 %) | 59.4 (x1.00) | 90 / 1277 |

Load phases (s; processed/tuning-lifecycle.csv and server-full.log timestamps):

| ID | Setting | submit->Ready | download | TTModelRunner->KV cache (weights to device) | engine init | first request (chat.py) |
|---|---|---|---|---|---|---|
| EXP-05#R6 | base | 222.9 | 81 | 30 | 68.2 | 6.6 |
| EXP-05#R7 | sod | 268.2 | 92 | 29 | 100.5 | 4.7 |
| EXP-05#R8 | notrace | 202.8 | 71 | 29 | 66.8 | 7.9 |
| EXP-05#R9 | b16 | 281.7 | 139 | 30 | 67.0 | 6.6 |
| EXP-05#R10 | len2k | 179.1 | 62 | 28 | 49.0 | 6.5 |
| EXP-05#R11 | nowarm | 246.6 | 170 | 30 | 2.2 | 99.3 |
| EXP-05#R12 | cache r1 (empty dir) | 290.0 | 153 | 28 | 65.0 | 6.5 |
| EXP-05#R13 | cache r2 (reuse) | 103.9 | none (`Weights already exist`) | 2 | 64.2 | 6.6 |

Claims (plan.md):
- B0 rejected (-12 to -18 % vs EXP-04, see Anomalies).
- S1 rejected: on-device sampling raised TPOT at c1 to 1.43 x base (threshold <= 0.8 x). The report v3 HYPOTHESIS that host
  sampling explains vLLM's c1 TPOT is not supported (on-device sampling is slower); whether host sampling contributes at all, and
  what makes SGLang's c1 TPOT lower, stay untested.
- T1 rejected: trace off raised TPOT at c1 to 1.13 x (threshold >= 1.5 x); throughput -5 to -12 %. Engine init barely changed
  (66.8 vs 68.2 s): warmup still runs every prefill length, trace capture is a small part of it.
- M1 holds: b16 at c32 = 0.594 x base (threshold <= 0.6 x; margin small), TTFT at c32 8.5 s vs 1.3 s.
- L1 rejected as written (init part holds): engine init -19.2 s (holds, >= 10 s); throughput within 5 % at c1 and c8 but +9.8 % at c32 (the "within 5 %" part is
  rejected in the favourable direction). Why a shorter max_model_len speeds up c32 decode (TPOT 79.2 vs 88.1 ms) is not tested
  (HYPOTHESIS: smaller decode page table, [32, 32] instead of [32, 128]; or drift).
- W1 as written rejected for Ready (246.6 vs 222.9 s, because its download took 170 vs 81 s); excluding the download, Ready came
  65 s sooner (76.6 vs 141.9 s) and engine init dropped from 68.2 to 2.2 s. First request 99.3 s vs 6.6 s (15 x, holds): the
  traces are captured on the first request instead (log 09:44:33 prefill, 09:45:50 decode).
- C1 holds: r2 Ready 186.0 s sooner than r1 (103.9 vs 290.0 s), no download; weights-to-device 2 s vs 28 s (converted tensor
  cache reused). Engine init unchanged (64.2 vs 65.0 s): the kernel compile cache was not persisted (Anomalies). Download excluded: 137.0 -> 103.9 s;
  vs same-day base 222.9 s: 119.0 s sooner.
## Statistics
3 runs per cell on one server per setting; mean and min-max; one load per setting (two for cache). No CI from n = 3.
## Validation
Settings verified in logs by analyze.py. Not REPRODUCED (one day, one load per setting, no repeated base).
