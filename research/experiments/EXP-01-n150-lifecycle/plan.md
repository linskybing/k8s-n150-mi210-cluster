---
artifact_type: experiment-plan
id: EXP-01-plan
version: 1
status: READY
created_at: 2026-11-10
updated_at: 2026-11-10
derived_from: []
source_files: [scripts/llm.yaml, scripts/sglang-custom.yaml, scripts/llama-3.2-1b-n150.json, scripts/job.yaml, ../config/job-defaults.yaml, ../config/kueue.yaml]
verification_status: UNVERIFIED
produced_by: ai-draft
---

# EXP-01: Does the n150 model lifecycle (load -> status -> inference -> unload) work end to end on Kubernetes for vLLM and SGLang?
## Question and figure
- No RQ (verification report); characterization run, allowed on a missing blueprint (experiment-schema exception). Kind: correctness + characterization.
- Claims: L1 each run allocates exactly one tenstorrent.com device through a ResourceClaim and Kueue charges tenstorrent.com/chip 1
  (rejected if any run is admitted without the charge, or two claims are allocated at once);
  L2 the server answers /health, /v1/models and a chat completion after Ready (rejected if any rep fails one of them);
  L3 deleting the Job frees the claim and the quota (rejected if the claim or the charge is still there 120 s after delete).
- Table: `tab:lifecycle` -- rows vLLM / SGLang; columns submit->admitted, admitted->pod running, running->Ready, delete->quota 0, delete->claim gone (s, mean and range of 3).
## Design
- Independent: framework {vLLM (n150/llm.yaml), SGLang (n150/sglang-custom.yaml)}. Controlled: model Llama-3.2-1B-Instruct, context 8192, same image, same node.
- Matrix: 2 frameworks x 3 reps = 6 loads. Weights are downloaded on every load (manifests mount no cache): load time includes the download.
## Statistics and validation
3 reps per framework, environment-sensitive (shared node, network download), mean and min-max reported, no CI claimed from n=3.
All timestamps from API objects or `date` on the node itself (single node: one clock).
## Run procedure and preconditions
`scripts/lc.sh load|query|unload <fw> <rep>` on the node as admin, namespace u-testuser, manifests identical to the user's copies (diffed 2026-11-10).
Secrets redacted at capture (`hf_...`). n150 must be free (cq tenstorrent.com/chip 0) before each load.
## CHECKPOINT: EXPERIMENT_PLAN_READY
Decision (researcher, 2026-11-10): "plan approved" (plan mode exit), with "remember there are two major inference frameworks, vLLM and SGLang" (translated).
