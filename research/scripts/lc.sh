#!/usr/bin/env bash
# EXP-01/03/05 phases on the node (admin kubeconfig, ns u-testuser): bash lc.sh load|query|bench|unload <vllm|vllm-seq1|vllm-<v>|sglang> <rep>
# writes out/<fw>-r<rep>/; manifests are copies of k8s-llm-example/n150 (llm-seq1.yaml = llm.yaml with configmap llm-spec-seq1)
set -euo pipefail
cd "$(dirname "$0")"
PH=$1 FW=$2 REP=$3
NS=u-testuser
export MODEL=${MODEL:-meta-llama/Llama-3.2-1B-Instruct}   # chat.py reads it too
case $FW in
  vllm)      M=llm.yaml;           J=n150-llm ;;
  vllm-seq1) M=llm-seq1.yaml;      J=n150-llm ;;
  vllm-cache) M=llm-cache.yaml;    J=n150-llm ;;   # EXP-05: caches on a hostPath
  vllm-8b*)  M=llm-8b.yaml; CM=llm-spec-${FW#vllm-}; J=n150-llm ;;   # EXP-06: Llama-3.1-8B-Instruct, 0.9.0 image (llm-spec-8b[-kv32k])
  vllm-*)    M=llm.yaml; CM=llm-spec-${FW#vllm-}; J=n150-llm ;;   # EXP-05: configmap llm-spec-<v> from llama-3.2-1b-n150-<v>.json
  sglang)    M=sglang-custom.yaml; J=n150-sglang-custom ;;
  sglang-tt) M=sglang-tt.yaml;     J=n150-sglang-custom ;;   # needs configmap sglang-tt-site (sitecustomize.py)
esac
O=out/$FW-r$REP; mkdir -p "$O"
k() { kubectl -n $NS "$@"; }
red() { sed -E 's/hf_[A-Za-z0-9]{8,}/hf_REDACTED/g'; }
mark() { echo "$1 $(date -u +%FT%T.%3NZ)" >> "$O/marks.txt"; }
pod() { k get pod -l job-name=$J -o jsonpath='{.items[0].metadata.name}' 2>/dev/null; }
prom() { kubectl get --raw "/api/v1/namespaces/monitoring/services/kube-prometheus-stack-prometheus:9090/proxy/api/v1/query?query=$1"; echo; }

case $PH in
load)
  mark submit
  sed "s/{name: llm-spec}/{name: ${CM:-llm-spec}}/" $M | k create -f -
  until [ -n "$(pod)" ]; do sleep 1; done
  P=$(pod)
  k wait --for=condition=Ready pod/$P --timeout=90m
  mark ready
  k get job $J -o json > $O/job.json
  k get pod $P -o json | red > $O/pod.json
  k get workloads -o json > $O/workload.json
  k get resourceclaims -o json > $O/resourceclaim.json
  kubectl get cq default -o json > $O/cq-loaded.json
  k exec $P -- ls -l /dev/tenstorrent/ > $O/devices.txt 2>&1
  # which processes really hold the card open (pid, number of /dev/tenstorrent fds, command)
  k exec $P -- bash -c 'for p in /proc/[0-9]*; do n=$(ls -l $p/fd 2>/dev/null | grep -c tenstorrent); [ "$n" -gt 0 ] && echo "$(basename $p) $n $(tr "\0" " " < $p/cmdline | cut -c1-100)"; done; true' > $O/device-fds.txt 2>&1
  k logs $P | red > $O/server-load.log
  ;;
query)
  P=$(pod)
  k port-forward pod/$P 8000:8000 > /dev/null 2>&1 & PF=$!
  for i in $(seq 30); do curl -s -o /dev/null localhost:8000/health && break; sleep 1; done
  { mark query
    echo "## /health"; curl -s -o /dev/null -w '%{http_code} %{time_total}s\n' localhost:8000/health
    echo "## /v1/models"; curl -s localhost:8000/v1/models; echo
    if [[ $FW = sglang* ]]; then echo "## /get_model_info"; curl -s localhost:8000/get_model_info; echo
      echo "## /get_server_info"; curl -s localhost:8000/get_server_info | red; echo; fi
    echo "## chat.py"; mark chat-start; python3 chat.py "In one sentence, what is Kubernetes?"; mark chat-done   # first request (EXP-05 nowarm)
    echo "## curl /v1/chat/completions"
    curl -s -w '\n%{http_code} %{time_total}s\n' localhost:8000/v1/chat/completions -H 'Content-Type: application/json' \
      -d '{"model":"'"$MODEL"'","messages":[{"role":"user","content":"List three uses of an AI accelerator."}],"max_tokens":64,"temperature":0}'
  } > $O/query.txt 2>&1
  curl -s localhost:8000/metrics > $O/metrics.txt
  kill $PF
  for m in tt_ai_clock_mhz tt_asic_temperature_celsius tt_tdp_w tt_tdc_a tt_vcore_v tt_device_dram_used_megabytes \
    tt_device_dram_total_megabytes tt_process_count tt_device_accessible; do echo "## $m"; prom $m; done > $O/telemetry.txt
  { k get resourceclaims -o wide; k get workloads -o wide; } > $O/status.txt
  ;;
bench)
  P=$(pod)
  B="source \$PYTHON_ENV_DIR/bin/activate && vllm bench serve --backend openai --base-url http://localhost:8000 --endpoint /v1/completions \
    --model $MODEL --dataset-name random --random-input-len 128 --random-output-len 128 --ignore-eos \
    --percentile-metrics ttft,tpot,itl,e2el --save-result --result-dir /tmp/bench ${BENCH_ARGS:-}"
  # SEED_PER_CELL=1: seed 10*C + r, so no prompt repeats across cells (EXP-04); default seed = r (EXP-03)
  mkdir -p $O/bench
  CS=${BENCH_CS:-"1 8 32"}; [ $FW = vllm-seq1 ] && CS=${BENCH_CS:-"1 8"}   # BENCH_CS overrides (EXP-04 addendum)
  k exec $P -- bash -c "$B --num-prompts 4 --max-concurrency 4 --seed 0 --result-filename warmup.json" 2>&1 | grep -v Triton > $O/bench/warmup.log
  for C in $CS; do for r in 1 2 3; do
    N=$(( C*2 > 8 ? C*2 : 8 ))
    mark bench-c$C-r$r
    S=$r; [ -n "${SEED_PER_CELL:-}" ] && S=$(( 10*C + r ))
    k exec $P -- bash -c "$B --num-prompts $N --max-concurrency $C --seed $S --result-filename c$C-r$r.json" 2>&1 | grep -v Triton > $O/bench/c$C-r$r.log
    k exec $P -- cat /tmp/bench/c$C-r$r.json > $O/bench/c$C-r$r.json
  done; done
  mark bench-done
  # server counters after the bench (prefix-cache hits, request totals)
  k exec $P -- python3 -c 'import urllib.request; print(urllib.request.urlopen("http://localhost:8000/metrics").read().decode())' > $O/bench/metrics-after.txt 2>&1 || true
  ;;
unload)
  P=$(pod)
  C=$(k get pod $P -o jsonpath='{.status.resourceClaimStatuses[0].resourceClaimName}')
  W=$(k get workloads -l kueue.x-k8s.io/job-uid=$(k get job $J -o jsonpath='{.metadata.uid}') -o name)
  k logs $P | red > $O/server-full.log
  mark delete
  k delete job $J --wait=false
  until ! k get $W >/dev/null 2>&1; do sleep 0.2; done; mark quota-released
  until ! k get pod $P >/dev/null 2>&1; do sleep 0.2; done; mark pod-gone
  until ! k get resourceclaim $C >/dev/null 2>&1; do sleep 0.2; done; mark claim-gone
  kubectl get cq default -o json > $O/cq-unloaded.json
  kubectl -n tt-operator-system logs ds/tt-operator-tt-dra-driver-kubeletplugin --since-time=$(head -1 $O/marks.txt | cut -d' ' -f2) > $O/dra-plugin.log 2>&1
  k get events -o json > $O/events.json
  ;;
esac
