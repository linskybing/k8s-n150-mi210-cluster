---
artifact_type: experiment-result
id: EXP-06-result
version: 1
status: DRAFT
created_at: 2026-11-12
updated_at: 2026-11-12
derived_from: [question: has Llama 3.1 8B Instruct run on this n150?]
source_files: [experiments/EXP-06-n150-llama31-8b/raw, scripts/llm-8b.yaml, scripts/llama-3.1-8b-n150.json, scripts/llama-3.1-8b-n150-kv32k.json, scripts/lc.sh, scripts/seq.sh, scripts/analyze.py]
verification_status: ANALYZED
produced_by: ai-draft
---

# EXP-06 result: Llama-3.1-8B-Instruct on the n150 with Tenstorrent's 0.9.0 image
## Provenance
- Provided by: agent-run, 2026-11-11 UTC, `~/exp-n150-20261112/` on the node (copy of research/scripts):
  `seq.sh 8b` 16:50:57Z (failed, stopped by the agent), `seq.sh 8b-kv32k` 17:05:46Z-17:16:26Z (exit 0). Logs: raw/seq/.
- Image `ghcr.io/tenstorrent/tt-inference-server/vllm-tt-metal-src-release-ubuntu-22.04-amd64:0.9.0-25305db-6e67d2d`
  (digest sha256:a2e2470c3e4f…c5d4, raw/runs/vllm-8b-kv32k-r1/pod.json), the image tt-inference-server v0.11.1
  `release_model_spec.json` pairs with Llama-3.1-8B-Instruct on N150 (status COMPLETE). The server log gives vLLM
  0.1.dev8069+g6e67d2d8d; tt-metal 25305db is known from the tag only (the launcher logs "commit SHA: None").
- hf-token (.env TOKEN) existed in u-testuser from 16:50Z until after 17:16Z; deleted with configmaps llm-spec,
  llm-spec-seq1, llm-spec-8b, llm-spec-8b-kv32k. No token strings in raw/ (grep `hf_…`).
- The hostPath cache /home/testuser/.cache/tt-vllm-8b (weights + converted tensors) was kept on the node; root-owned.
- Other users' MI210 workloads kept running; no other n150 claim existed before either run.
## Runs
| ID | Stage | Spec | Outcome |
|---|---|---|---|
| EXP-06#R1 | 8b | llama-3.1-8b-n150.json: TT's entry as released + `cli_args.no_auth` | engine died 17:01:49Z, device DRAM out of memory |
| EXP-06#R2 | 8b-kv32k | same, `max_model_len` / `max_context` 32768, `num_gpu_blocks_override` 549 | loaded, queried, 9 bench runs |

R1 (raw/runs/vllm-8b-r1/server-crash.log): weights converted, KV cache 1066 blocks x 64 (`Maximum concurrency for 65536
tokens per request: 1.04x`), API healthy at 17:01:06. The image's background trace capture then sent its first request;
tt-metal warmed up prefill traces at 128, 256, 512 and failed at 1024:
`TT_FATAL: Out of Memory: Not enough space to allocate 29360128 B DRAM buffer across 12 banks … bank size is only
1021821792 B` (in `mlp.py` `ttnn.linear`, `_capture_trace_prefill`). The container exited 0, so the load step kept
waiting for Ready; seq.sh/lc.sh were stopped by PID and `lc.sh unload vllm-8b 1` was run by hand (marks: claim gone
17:05:03Z).

Why (source at the image's commits):
- vLLM 6e67d2d `vllm/worker/tt_worker.py` `get_num_available_blocks_tt`: for "Llama-3.1-8B" on one Wormhole device the KV
  cache is fixed at 65536 tokens + block_size x max_num_seqs, +1 % (= 1066 blocks), whatever `max_model_len` is.
- tt-metal 25305db `models/tt_transformers/tt/model_config.py` `get_trace_prefill_supported_seq_lens`: Llama-3.1-8B on
  N150 traces prefill at [128, 256, 512, 1024]; the N150 default for other models stops at 512.
- Weights + that KV cache leave too little of the 12 GB DRAM for the 1024 trace on this card. Why TT's own runs passed
  is not known (not tested: firmware, harvesting, a different trace region).

The one targeted fix (R2): `num_gpu_blocks_override` (applied by V0 `llm_engine.py`: log `Overriding num_gpu_blocks=1066
with num_gpu_blocks_override=549`), sized with the same formula for 32768 tokens, and `max_model_len` 32768 to match;
`max_context` 32768 so the image's trace capture stops there. Nothing else differs from TT's spec. The bench needs at most
32 x 256 tokens of KV, so its numbers do not depend on this change; the maximum context does (32k instead of 64k).

R2 checks: Workload admitted, claim on the n150; `device-fds.txt`: the vLLM engine process holds a /dev/tenstorrent fd;
/health 200; /v1/models lists meta-llama/Llama-3.1-8B-Instruct with max_model_len 32768; chat.py and curl answered
correctly; "✅ Background trace capture completed successfully" (9 context lengths up to 32k); 9 bench JSONs, every
request completed with 128 output tokens (analyze.py asserts); claim gone 17:16:25.995Z.
## Results
Bench: `vllm bench serve`, random dataset, input 128 / output 128 tokens, `--ignore-eos`, temperature 0, seed 10 x
concurrency + rep, prompts max(8, 2 x concurrency); mean of 3 (min-max) from processed/throughput-summary.csv.

| ID | Concurrency | Output tok/s | TTFT mean (ms) | TPOT mean (ms) | E2E mean (s) |
|---|---|---|---|---|---|
| EXP-06#R3 | 1 | 19.3 (19.2-19.3) | 182 (181-182) | 50.9 (50.8-51.2) | 6.65 |
| EXP-06#R4 | 8 | 122.1 (121.3-122.5) | 1046 (1033-1062) | 57.8 (57.5-58.3) | 8.39 |
| EXP-06#R5 | 32 | 348.9 (347.5-351.5) | 3952 (3923-3967) | 61.3 (60.8-61.5) | 11.73 |

Against TT's perf reference for this model/device (ISL/OSL 128, concurrency 1, 8 prompts; release_model_spec.json):
TTFT 182 ms vs functional <= 890, complete <= 178, target 89; per-user decode 1000/TPOT = 19.6 tok/s vs functional 2.1,
complete 10.5, target 21. So it is above "complete" on throughput, 2 % over the "complete" TTFT.
TTFT grows with concurrency at about 120 ms per queued request (3.95 s at 32): prefill runs one user at a time.

Load phases (s; events.json, server logs, marks.txt):

| ID | Phase | R1 (empty cache) | R2 (R1's cache) |
|---|---|---|---|
| EXP-06#R6 | image pull (3.94 GB) | 269.9 | 0 (present) |
| EXP-06#R7 | weight download (init container) | 127 | ~0 (files present) |
| EXP-06#R8 | launcher start -> API healthy (includes weight conversion, 32 layers in 156 s on R1) | 200.2 | 40.0 |
| EXP-06#R9 | background trace capture (to /tmp/ready) | crashed after 43 | 124 |
| EXP-06#R10 | submit -> Ready | - | 176.8 |

A first load on an empty node would be about 270 + 127 + 200 + 124 s ≈ 12 min (sum of phases from two runs, not one
measured load).
## Anomalies
- tt-metal 25305db warns "Firmware bundle version 19.13.0 on the system is newer than the maximum supported version 19.1.0"
  (the card has 19.13.0). R2 ran correctly with it; the OOM in R1 is explained by the allocation sizes above.
- lc.sh `load` waits for Ready only, so a server that exits during load costs the full 90 min timeout; R1 was caught by an
  agent watcher instead. Not changed.
- `tt_device_dram_used_megabytes` reads 0 while the model is loaded (raw/runs/vllm-8b-kv32k-r1/telemetry.txt), so device
  memory use could not be cross-checked from telemetry.
- Not comparable to EXP-03..05 (Llama-3.2-1B): different image (tt-metal 84b4c53, vLLM fork 222ee06) and model.
