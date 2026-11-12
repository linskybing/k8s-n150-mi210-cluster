---
artifact_type: experiment-result
id: EXP-01-result
version: 1
status: DRAFT
created_at: 2026-11-10
updated_at: 2026-11-10
derived_from: [experiments/EXP-01-n150-lifecycle/plan.md@1]
source_files: [experiments/EXP-01-n150-lifecycle/raw/runs, experiments/EXP-01-n150-lifecycle/raw/env, scripts/lc.sh, scripts/seq.sh, scripts/analyze.py]
verification_status: ANALYZED
produced_by: ai-draft
---

# EXP-01 result: n150 model lifecycle on Kubernetes, vLLM and SGLang (3 reps each)
## Provenance
- Provided by: agent-run (scripts/lc.sh, scripts/seq.sh on the node, admin kubeconfig, namespace u-testuser)
- Exact configuration: scripts/llm.yaml + scripts/llama-3.2-1b-n150.json (vLLM, = k8s-llm-example@0bb1d0f n150/); scripts/sglang-tt.yaml
  + scripts/sitecustomize.py (SGLang: n150/sglang-custom.yaml plus the plugin loaded in every process and --max-total-tokens 131072)
- Commit(s): n150@8387795; tenstorrent/vllm 222ee06; tt-metal 84b4c53 (image); SGLang v0.5.8.post1 (c1f2241a32); tt-inference-server v0.11.1 (0a19f30f0)
- Environment / hardware: raw/env/ (host.txt, n150-device.txt, software.txt, dra-tenstorrent.yaml, kueue.yaml, admission.txt)
- Run window: 2026-11-10 03:26:22Z - 04:32:27Z. Raw: raw/runs/, raw/excluded/, raw/seq/. Processed: processed/lifecycle*.csv
## Runs
| Run | Cell | Outcome | Notes |
|---|---|---|---|
| vllm-r1 | vLLM | ok | |
| vllm-r2 | vLLM | ok | first launch killed at its query (ssh teardown); query rerun on the same loaded server (query-interrupted.txt kept) |
| vllm-r3 | vLLM | ok | also served EXP-03 vLLM batch 32 and EXP-02 (a) |
| sglang-rq | SGLang as in k8s-llm-example | ok but excluded here | ran on CPU, see Anomalies; kept in EXP-02/raw |
| sglang-r1 | SGLang as in k8s-llm-example | aborted by agent | stopped after submit because SGLang ran on CPU (raw/excluded/sglang-r1-aborted-cpu) |
| sglang-tt-r0 | SGLang + fix, no token cap | trial, excluded | first load with the fix: 174.5 s; host KV pool 22 GB (raw/excluded/sglang-tt-r0-trial) |
| sglang-tt-r1..r3 | SGLang + fix | ok | r3 also served EXP-03 SGLang |
## Failed and excluded runs
| Run | What happened | Excluded? | Reason | Decision (researcher, date) |
|---|---|---|---|---|
| sglang-rq, sglang-r1 | `device='cpu'`, SGLang's own LlamaForCausalLM, no process holds /dev/tenstorrent | yes | not n150 inference | "try to fix; if not, write it as it is" (2026-11-10, translated) |
| sglang-tt-r0 | first load after the fix; config differs (no --max-total-tokens) | yes | trial of the fix | same decision |
## Anomalies
- SGLang (manifest as in k8s-llm-example) runs on CPU while holding the n150 claim. Cause (code-confirmed): SGLang v0.5.8.post1
  `engine.py:836` forces multiprocessing "spawn"; tt-sglang-plugin registers TTLlamaForCausalLM in the launcher process only
  (it relies on fork), so the spawned scheduler loads SGLang's CPU model. Fixed by scripts/sitecustomize.py; checked by
  device-fds.txt (vLLM EngineCore 2 fds = positive control; SGLang before fix 0; after fix sglang::scheduler 2).
- SGLang sizes its host KV pool from free host memory (mem_fraction_static 0.791): 719,232 tokens, 22 GB, pod 26 GiB vs an
  8 GiB request; node available memory fell to 7 GB (kubectl top / free -g, not captured by lc.sh: transcribed in
  raw/excluded/sglang-tt-r0-trial/observed-memory.txt). The plugin's n150 KV cache holds 131,072 + 64 x 32 tokens, so measured runs
  use --max-total-tokens 131072.
- tenstorrent ResourceSlice capacity.memory = 140725536995392 (about 128 TiB) for a 12 GB card (driver-reported; unused here).
- unload marks are polled sequentially (pod, then claim): up to about 0.7 s late (EXP-02 sample.txt shows the vLLM claim gone
  at 03:46:59.247 while its claim-gone mark is 03:46:59.929). Lifecycle times are reported to the second.
- Load paths differ: vLLM downloads the weights into the container on every load (66-69 s); SGLang shows no download in its log and
  uses the tt-metal caches in the user's home (~/.cache: 3,983 files from 2026-10-23 plus 5,520 written during the runs,
  raw/env/sglang-tt-cache-dirs.txt). The load-time difference reflects cache state, not the framework: sglang-tt-r0 (partial cache)
  took 174.5 s, slower than vLLM minus its download (about 137 s).
- device='cpu' in SGLang server_args is the plugin's design (also in the fixed runs); the CPU-fallback evidence is
  type=LlamaForCausalLM plus no /dev/tenstorrent fd (EXP-02/raw/sglang-rq/observed-device-fds.txt, transcribed: lc.sh got the
  fd check only after vllm-r1..r3 and the unfixed SGLang runs). Root cause SUPPORTED, not isolated: the fix applies both the plugin
  import and the decode alias in every process. Upstream sources archived in literature/sources/.
- Shared node: other users' workloads (another accelerator's KServe claim, 31 GiB host memory in use at start) ran throughout.
## Results
| ID | Finding | Metric | Value (mean, min-max, n=3) | Source |
|---|---|---|---|---|
| EXP-01#R1 | every run got exactly one device (tt-0, driver tenstorrent.com) and Kueue charged tenstorrent.com/chip 1 | claim / workload | 6/6 runs | analyze.py asserts |
| EXP-01#R2 | /health 200, /v1/models lists the model, chat.py and curl answer | query | 6/6 runs | raw/runs/*/query.txt |
| EXP-01#R3 | submit -> Ready, vLLM | s | 204.6 (204.2-204.8) | processed/lifecycle-summary.csv |
| EXP-01#R4 | of which weight download / engine init (compile, trace, KV), vLLM | s | 67.0 (66-69) / 67.4 (67.1-67.6) | processed/lifecycle.csv |
| EXP-01#R5 | submit -> Ready, SGLang (warm home caches) | s | 53.6 (53.5-53.7) | processed/lifecycle-summary.csv |
| EXP-01#R6 | submit -> admitted -> claim allocated -> container running | s | 0 / 0 / 1-2 (both) | processed/lifecycle.csv |
| EXP-01#R7 | delete -> Kueue quota released | s | vLLM 0.13 (0.12-0.14); SGLang 0.12 (0.12-0.13) | processed/lifecycle-summary.csv |
| EXP-01#R8 | delete -> ResourceClaim deleted | s | vLLM 2.3 (2.1-2.4); SGLang 6.7 (5.5-8.4) | processed/lifecycle-summary.csv |
| EXP-01#R9 | DRA NodePrepareResources / NodeUnprepareResources duration | ms | 1.24-1.94 / 1.42-2.06 (6 runs) | raw/runs/*/dra-plugin.log, processed/lifecycle.csv |
| EXP-01#R10 | submit -> server's own ready log line (Ready adds the readinessProbe period, default 10 s) | s | vLLM 199.7 (198.7-201.6); SGLang 45.2 (44.4-45.8) | processed/lifecycle-summary.csv |
| EXP-01#R11 | vLLM load breakdown, vllm-r1 log: download 66 s, process start + device open about 25 s (03:27:36-03:28:01), weight conversion and load about 30 s (03:28:02-03:28:32, 16 layers), warmup/trace/KV 67.6 s | s | one run | raw/runs/vllm-r1/server-full.log |
## Statistics
n = 3 per framework; mean and min-max; no CI from n = 3. API timestamps have 1 s resolution; marks are node `date` (ms) with the polling lag above.
## Validation
Checklist: one clock (single node); determinism class environment-sensitive (shared node, network download); claims L1-L3 hold
(L3 bound 120 s, max observed 8.4 s). Not VALIDATED: no independent re-run; SGLang load time depends on cache state in the user's home.
