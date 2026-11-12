---
artifact_type: experiment-plan
id: EXP-03-plan
version: 1
status: READY
created_at: 2026-11-10
updated_at: 2026-11-10
derived_from: []
source_files: [scripts/llm.yaml, scripts/sglang-custom.yaml, scripts/llama-3.2-1b-n150.json, scripts/job.yaml, ../config/job-defaults.yaml, ../config/kueue.yaml]
verification_status: UNVERIFIED
produced_by: ai-draft
---

# EXP-03: How do vLLM and SGLang throughput on the n150 scale with concurrency, and what does continuous batching contribute?
## Question and figure
- Kind: characterization. Claims: B1 vLLM with max_num_seqs 32 gives higher output tok/s at concurrency 8 than with max_num_seqs 1
  (rejected if the gain is < 1.5x); B2 both frameworks scale output tok/s from concurrency 1 to 8 (rejected if < 1.5x).
  No claim is made about which framework is faster beyond what is measured.
- Figure: `fig:throughput` -- x concurrency (1, 8, 32), y output throughput (tokens/s); series vLLM (max_num_seqs 32), vLLM (max_num_seqs 1), SGLang.
## Design
- Server configs: vLLM-A = llama-3.2-1b-n150.json as is; vLLM-B = same with max_num_seqs 1 and max_concurrency 1 (configmap llm-spec-seq1);
  SGLang = sglang-custom.yaml as is (its own scheduler defaults, recorded from the log).
- Client: `vllm bench serve` from the same image for all servers, run inside the server pod against localhost:8000, backend openai,
  /v1/completions, random dataset, ISL 128, OSL 128, --ignore-eos (same as the spec json perf_reference); num-prompts max(8, 2 x concurrency).
- Matrix: vLLM-A, SGLang x {1, 8, 32}; vLLM-B x {1, 8}; 3 reps each (seed = rep), one discarded warmup run per server.
## Statistics and validation
Environment-sensitive; mean and min-max of 3 per cell. Client in the server pod shares its CPU: noted, not controlled.
## Run procedure and preconditions
`scripts/lc.sh bench <fw> <rep>` while the server of EXP-01 rep 3 (vLLM-A, SGLang) or a dedicated vLLM-B load is up.
vLLM-B may not start if the TT model needs batch 32: the failure is recorded, not retried.
## CHECKPOINT: EXPERIMENT_PLAN_READY
Decision (researcher, 2026-11-10): "plan approved" (plan mode exit).
