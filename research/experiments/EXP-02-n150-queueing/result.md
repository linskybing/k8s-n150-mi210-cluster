---
artifact_type: experiment-result
id: EXP-02-result
version: 1
status: DRAFT
created_at: 2026-11-10
updated_at: 2026-11-10
derived_from: [experiments/EXP-02-n150-queueing/plan.md@1]
source_files: [experiments/EXP-02-n150-queueing/raw, scripts/seq.sh, scripts/analyze.py]
verification_status: ANALYZED
produced_by: ai-draft
---

# EXP-02 result: Kueue serializes users of the single n150
## Provenance
- Provided by: agent-run (scripts/seq.sh stages queue-a, queue-b). Run windows: (a) 03:45:57Z-03:49:46Z, (b) 04:05:02Z-04:06:10Z.
- Raw: raw/queue-a (1 s samples, pending workloads and events), raw/sglang-rq (the queued SGLang run), raw/queue-b. Processed: processed/queueing.csv
- Note: the SGLang server in (a) is the unfixed manifest (CPU inference, EXP-01 Anomalies); the queueing, admission and claim
  behaviour measured here does not depend on where the server computes.
## Runs
| Run | Cell | Outcome | Notes |
|---|---|---|---|
| queue-a | vLLM holds the n150, SGLang submitted, vLLM deleted after 60 s | ok | |
| queue-b | two busybox Jobs with the n150 claim, back to back | ok | |
## Results
| ID | Finding | Value | Source |
|---|---|---|---|
| EXP-02#R1 | SGLang Workload not admitted while vLLM holds the card; Kueue event WaitingForQuota: "insufficient unused quota for tenstorrent.com/chip in flavor default, 1 more needed" | admitted at 61.55 s (Kueue: "wait time since queued was 62s") | raw/sglang-rq/events.json, processed/queueing.csv |
| EXP-02#R2 | vLLM delete -> quota released -> SGLang admitted -> vLLM claim unprepared -> SGLang claim prepared | t = 60.46 / 60.58 / 61.55 / 61.73 / 62.08 s (Kueue event and DRA log times, sub-second) | processed/queueing.csv, raw/sglang-rq/dra-plugin.log |
| EXP-02#R3 | at most one allocated tenstorrent claim per sample (about every 1.13 s, namespace u-testuser only); the DRA plugin prepared the new claim only after unpreparing the old one | 92 + 60 samples; 03:46:58.842 -> 03:46:59.192 | raw/queue-*/sample.txt, analyze.py asserts |
| EXP-02#R4 | two Jobs ran one after the other | a 0-34 s, b 35-68 s | processed/queueing.csv |
## Validation
Q1 and Q2 hold. One run each (ordering claim, deterministic by design). With a single device, DRA alone would also never give
tt-0 to two claims; Kueue's part is queueing the second Job before admission instead of leaving its Pod pending in the scheduler.
