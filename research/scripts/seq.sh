#!/usr/bin/env bash
# run order on the node (EXP-01, EXP-02, EXP-03): setsid -f bash seq.sh [stage ...] > out/seq.log 2>&1 < /dev/null
# stages (default: all, in this order): vllm12 vllm3 queue-a sglang vllm-seq1 queue-b sglang-tt; on request: bench-clean (EXP-04),
#   tune-<base|sod|notrace|b16|len2k|nowarm> and cache (EXP-05, one stage per call so a failed setting does not stop the others),
#   8b, 8b-kv32k (EXP-06), seq1-c32 (EXP-04 addendum)
# history 2026-11-10: launch 1 (all) killed with its ssh session at vllm-r2 query 03:33:31Z; resumed from vllm-r2 query;
#   stopped by the agent after sglang-r1 submit (SGLang ran on CPU, see EXP-01 result); then: vllm-seq1 queue-b;
#   then trial sglang-tt r0 (lc.sh by hand) and: sglang-tt
# history 2026-11-11 (EXP-06): 8b: engine died with device DRAM OOM at 17:01:49Z (container exit 0, load kept waiting for
#   Ready); seq.sh/lc.sh stopped by the agent, lc.sh unload vllm-8b 1 by hand; then: 8b-kv32k
set -euo pipefail
cd "$(dirname "$0")"
NS=u-testuser
k() { kubectl -n $NS "$@"; }
# on any failure free the card and stop; failed runs are not retried
trap 'echo "FAILED line $LINENO $(date -u +%FT%TZ)"; k delete job n150-llm n150-sglang-custom n150-job-a n150-job-b --ignore-not-found --wait=false' ERR
sample() { while :; do echo "$(date -u +%FT%T.%3NZ) | $(k get workloads --no-headers -o custom-columns=W:.metadata.name,ADM:.status.conditions[?\(@.type==\"Admitted\"\)].status | tr '\n' ' ') | claims: $(k get resourceclaims --no-headers 2>/dev/null | tr '\n' ' ')"; sleep 1; done; }
run() { echo "== $* $(date -u +%FT%TZ)"; bash lc.sh "$@"; }
k get configmap llm-spec >/dev/null 2>&1 || k create configmap llm-spec --from-file=spec.json=llama-3.2-1b-n150.json
k get configmap llm-spec-seq1 >/dev/null 2>&1 || k create configmap llm-spec-seq1 --from-file=spec.json=llama-3.2-1b-n150-seq1.json

for stage in ${@:-vllm12 vllm3 queue-a sglang vllm-seq1 queue-b sglang-tt}; do case $stage in
vllm12)
  for r in 1 2; do run load vllm $r; run query vllm $r; run unload vllm $r; done ;;
vllm3)
  run load vllm 3; run query vllm 3; run bench vllm 3 ;;   # stays loaded for queue-a
queue-a)   # EXP-02 (a): SGLang submitted while vLLM holds the n150
  mkdir -p out/queue-a; sample > out/queue-a/sample.txt & SP=$!
  run load sglang q & LP=$!
  sleep 60
  k get workloads -o json > out/queue-a/workloads-pending.json
  k get events --field-selector involvedObject.kind=Workload -o json > out/queue-a/events-pending.json
  run unload vllm 3
  wait $LP
  kill $SP
  run query sglang q; run unload sglang q ;;
sglang)
  for r in 1 2; do run load sglang $r; run query sglang $r; run unload sglang $r; done
  run load sglang 3; run query sglang 3; run bench sglang 3; run unload sglang 3 ;;
vllm-seq1)
  run load vllm-seq1 1; run query vllm-seq1 1; run bench vllm-seq1 1; run unload vllm-seq1 1 ;;
queue-b)   # EXP-02 (b): two n150 Jobs submitted back to back
  mkdir -p out/queue-b; sample > out/queue-b/sample.txt & SP=$!
  for j in a b; do sed -e "s/name: n150-job/name: n150-job-$j/" -e 's#image: .*tt-metalium.*#image: busybox:1.37#' \
    -e 's#command: .*#command: [sh, -c, "date -u; ls -l /dev/tenstorrent; sleep 30; date -u"]#' job.yaml | k create -f -; done
  k wait --for=condition=Complete job/n150-job-a job/n150-job-b --timeout=10m
  kill $SP
  for j in a b; do k get job n150-job-$j -o json > out/queue-b/job-$j.json; k logs job/n150-job-$j > out/queue-b/job-$j.log; done
  k get workloads -o json > out/queue-b/workloads.json
  k get events --field-selector involvedObject.kind=Workload -o json > out/queue-b/events.json
  k delete job n150-job-a n150-job-b ;;
sglang-tt)   # SGLang with the plugin in every process (sitecustomize, configmap sglang-tt-site)
  k get configmap sglang-tt-site >/dev/null 2>&1 || k create configmap sglang-tt-site --from-file=sitecustomize.py
  for r in 1 2; do run load sglang-tt $r; run query sglang-tt $r; run unload sglang-tt $r; done
  run load sglang-tt 3; run query sglang-tt 3; run bench sglang-tt 3; run unload sglang-tt 3 ;;
bench-clean)   # EXP-04: EXP-03 again with a distinct seed per cell (no repeated prompts) and temperature 0
  export SEED_PER_CELL=1 BENCH_ARGS="--temperature 0"
  k get configmap sglang-tt-site >/dev/null 2>&1 || k create configmap sglang-tt-site --from-file=sitecustomize.py
  run load vllm clean; run bench vllm clean; run unload vllm clean
  run load sglang-tt clean; run bench sglang-tt clean; run unload sglang-tt clean
  run load vllm-seq1 clean; run bench vllm-seq1 clean; run unload vllm-seq1 clean ;;
tune-*)   # EXP-05: one vLLM setting per server (spec llama-3.2-1b-n150-<v>.json as configmap llm-spec-<v>); tune-base = llm.yaml
  export SEED_PER_CELL=1 BENCH_ARGS="--temperature 0"
  v=${stage#tune-}; fw=vllm-$v
  if [ $v = base ]; then fw=vllm; else k get configmap llm-spec-$v >/dev/null 2>&1 || k create configmap llm-spec-$v --from-file=spec.json=llama-3.2-1b-n150-$v.json; fi
  run load $fw 1; run query $fw 1
  if [ $v != nowarm ]; then run bench $fw 1; fi
  run unload $fw 1 ;;
cache)   # EXP-05: caches on a hostPath (llm-cache.yaml); r1 starts from an empty dir, r2 reuses it
  for r in 1 2; do run load vllm-cache $r; run query vllm-cache $r; run unload vllm-cache $r; done ;;
8b|8b-kv32k)   # EXP-06: Llama-3.1-8B-Instruct with the image Tenstorrent pairs with it for N150 (llm-8b.yaml)
  # 8b = TT's spec as released; 8b-kv32k = 32k context and KV cache (8b ran out of device DRAM in prefill trace warmup)
  export MODEL=meta-llama/Llama-3.1-8B-Instruct SEED_PER_CELL=1 BENCH_ARGS="--temperature 0"
  v=${stage#8b}
  k get configmap llm-spec-8b$v >/dev/null 2>&1 || k create configmap llm-spec-8b$v --from-file=spec.json=llama-3.1-8b-n150$v.json
  run load vllm-8b$v 1; run query vllm-8b$v 1; run bench vllm-8b$v 1; run unload vllm-8b$v 1 ;;
seq1-c32)   # EXP-04 addendum 2026-11-12: max batch 1 at concurrency 32 (left out on 2026-11-10), concurrency 1 again to compare days
  export SEED_PER_CELL=1 BENCH_ARGS="--temperature 0" BENCH_CS="1 32"
  run load vllm-seq1 c32; run bench vllm-seq1 c32; run unload vllm-seq1 c32 ;;
esac; done
echo "== DONE $(date -u +%FT%TZ)"
