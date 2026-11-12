---
artifact_type: experiment-plan
id: EXP-02-plan
version: 1
status: READY
created_at: 2026-11-10
updated_at: 2026-11-10
derived_from: []
source_files: [scripts/llm.yaml, scripts/sglang-custom.yaml, scripts/llama-3.2-1b-n150.json, scripts/job.yaml, ../config/job-defaults.yaml, ../config/kueue.yaml]
verification_status: UNVERIFIED
produced_by: ai-draft
---

# EXP-02: Does Kueue serialize n150 users (a second service or Job waits until the card is released)?
## Question and figure
- Kind: correctness. Claims: Q1 while a vLLM server holds the n150, a submitted SGLang Job stays unadmitted with a quota reason and
  is admitted only after the vLLM Job is deleted (rejected if it is admitted, or gets a claim, while vLLM holds the card);
  Q2 two Jobs asking for the n150 at the same time run one after the other (rejected if their running intervals overlap).
- Table: `tab:queueing` -- per Job: submit, admitted, running, finished/deleted (s from first submit); pending reason text.
## Design
- (a) vLLM loaded (EXP-03 vLLM-A server), then submit sglang-custom.yaml; wait 60 s; delete vLLM; SGLang loads; delete SGLang.
- (b) n150/job.yaml with image busybox:1.37 and command `ls -l /dev/tenstorrent; sleep 30` (the tt-metalium image is not cached
  on the node), as n150-job-a and n150-job-b submitted back to back.
## Statistics and validation
Deterministic ordering claim: one run each; the checker is the claim count sampled every second (at most one allocated tenstorrent claim).
## Run procedure and preconditions
`scripts/queue.sh` on the node; same namespace and redaction as EXP-01.
## CHECKPOINT: EXPERIMENT_PLAN_READY
Decision (researcher, 2026-11-10): "plan approved" (plan mode exit).
