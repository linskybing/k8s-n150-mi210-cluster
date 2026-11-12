---
artifact_type: research-state
id: research-state
version: 1
status: DRAFT
created_at: 2026-11-10
updated_at: 2026-11-11
derived_from: []
source_files: []
verification_status: UNVERIFIED
produced_by: ai-draft
---

# Research state

## Researcher context
Engineering verification report (not a paper): Tenstorrent n150 on Kubernetes (kubeadm + tt-operator DRA + Kueue) as a proxy for
domestic (Taiwan-made) AI chips; v4 (2026-11-11) reframes it that way, focuses on vLLM tuning (EXP-05), moves SGLang to an appendix,
and adds a DRA driver template for a custom chip (dra-template/).
Testbed: single KVM node, see experiments/EXP-01-n150-lifecycle/raw/env/. Deliverable: report-2026-11-15.md (Traditional Chinese).

## State
```yaml
project:
  title: AI Container model resource scheduling and cluster management integration verification (n150)
  deliverable: report
  venue: project report, 2026-11-15
  current_stage: review
research_question: "[MATERIAL GAP] none -- verification report, no RQ"
research_gap: "[MATERIAL GAP] none -- verification report"
methodology: "[MATERIAL GAP] none -- plans are characterization runs (experiment-schema exception)"
paper: report-2026-11-15.md
literature: "[MATERIAL GAP] none -- citations listed in the report appendix"
open_questions: [physical host spec not visible inside the VM]
risks: [shared node, n150 may be busy]
next_actions: ["researcher: review report v12 (SGLang and appendices removed; fig 4 queueing now the two-Job case queue-b, "within 2 s after the previous Job completed" replaces 1.6 s; log screenshots fig 2-5 in 6.2; one job per chapter: checklist and settings moved to ch7, results split 6.2/6.3; .docx via scripts/report-docx.py)", "optional: re-run EXP-04/05 on another day for REPRODUCED"]
```

## Checkpoints passed
| Checkpoint | Date | Artifact@version | Decision (quoted; research-artifact-contract.md Sec. 8) |
|---|---|---|---|
| EXPERIMENT_PLAN_READY | 2026-11-10 | experiments/EXP-0{1,2,3}/plan.md@1 | "plan approved" (researcher, plan mode exit, 2026-11-10) |
| EXPERIMENT_PLAN_READY | 2026-11-10 | experiments/EXP-04-n150-throughput-clean/plan.md@1 | "re-run (recommended)" (researcher, 2026-11-10, translated) |
| Gate 4 (report audit) | 2026-11-10 | integrity/gate4-2026-11-10.md@2 | PASS, one INSUFFICIENT EVIDENCE item (host spec); F14 closed by "only write the n150" (researcher, 2026-11-10, translated) |
| EXPERIMENT_PLAN_READY | 2026-11-11 | experiments/EXP-05-n150-vllm-tuning/plan.md@1 | "新增調教實驗 (Recommended)" (researcher, plan mode, 2026-11-11) |
| Gate 4 (report audit) | 2026-11-11 | integrity/gate4-2026-11-11.md@1 | PASS WITH FIXES; all MUST/SHOULD-FIX applied (agent, 2026-11-11) |

## Artifact index
<!-- artifact-index:start -->
| Artifact | Type | v | Status | Verification | Stale | Issues |
|---|---|---|---|---|---|---|
| `experiments/EXP-01-n150-lifecycle/plan.md` | experiment-plan | 1 | READY | UNVERIFIED | - | - |
| `experiments/EXP-01-n150-lifecycle/result.md` | experiment-result | 1 | DRAFT | ANALYZED | - | - |
| `experiments/EXP-02-n150-queueing/plan.md` | experiment-plan | 1 | READY | UNVERIFIED | - | - |
| `experiments/EXP-02-n150-queueing/result.md` | experiment-result | 1 | DRAFT | ANALYZED | - | - |
| `experiments/EXP-03-n150-batching/plan.md` | experiment-plan | 1 | READY | UNVERIFIED | - | - |
| `experiments/EXP-03-n150-batching/result.md` | experiment-result | 1 | DRAFT | ANALYZED | - | - |
| `experiments/EXP-04-n150-throughput-clean/plan.md` | experiment-plan | 1 | READY | UNVERIFIED | - | - |
| `experiments/EXP-04-n150-throughput-clean/result.md` | experiment-result | 1 | DRAFT | ANALYZED | - | - |
| `experiments/EXP-05-n150-vllm-tuning/plan.md` | experiment-plan | 1 | READY | UNVERIFIED | - | - |
| `experiments/EXP-05-n150-vllm-tuning/result.md` | experiment-result | 1 | DRAFT | ANALYZED | - | - |
| `integrity/gate4-2026-11-11.md` | integrity-report | 1 | READY | CHECKED | - | - |
| `integrity/gate4-2026-11-10.md` | integrity-report | 2 | READY | CHECKED | yes (v3) | - |
| `report-2026-11-15.md` | report | 12 | DRAFT | CHECKED (v4 gate4; v9 concise report, real YAML, subject ben-bao-gao; v10 one job per chapter, English terms and Taiwan usage, headings 1. 1.1. 1.1.1.; v11 log screenshots fig 2-5 from saved logs via scripts/logshot.py; v12 SGLang, ref 18 and appendices removed, fig 4 from queue-b; linted with research nstc-report-zh) | - | - |
| `research-state.md` | research-state | 1 | DRAFT | UNVERIFIED | - | - |
<!-- artifact-index:end -->
