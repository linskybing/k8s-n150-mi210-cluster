#!/usr/bin/env bash
# Run once per cluster: bash cluster.sh
set -euo pipefail
cd "$(dirname "$0")/.."
NS=tt-operator-system
PC=https://prometheus-community.github.io/helm-charts

# monitor CRDs first so Cilium (and everything after) can create ServiceMonitors before Prometheus runs
helm upgrade --install prometheus-operator-crds prometheus-operator-crds --repo "$PC" --version 32.0.1 -n monitoring --create-namespace
helm upgrade --install cilium cilium --repo https://helm.cilium.io --version 1.20.3 -n kube-system -f config/cilium-values.yaml --wait
kubectl wait --for=condition=Ready nodes --all --timeout=10m
helm upgrade --install kube-prometheus-stack kube-prometheus-stack --repo "$PC" --version 92.10.1 \
  -n monitoring -f config/monitoring-values.yaml --wait
helm upgrade --install metrics-server metrics-server --repo https://kubernetes-sigs.github.io/metrics-server --version 3.14.0 \
  -n kube-system -f config/metrics-server-values.yaml --wait

helm upgrade --install tt-operator oci://ghcr.io/tenstorrent/helm/tt-operator --version 0.3.0 \
  -n "$NS" --create-namespace -f config/tt-operator-values.yaml
until kubectl -n "$NS" get ds tt-fabric-manager-agent >/dev/null 2>&1; do sleep 5; done
kubectl -n "$NS" rollout status ds/tt-fabric-manager-agent --timeout=10m
# DRA plugin discovers boards only at startup, so restart it once the fabric manager is up
kubectl -n "$NS" rollout restart ds/tt-operator-tt-dra-driver-kubeletplugin
kubectl -n "$NS" rollout status ds/tt-operator-tt-dra-driver-kubeletplugin --timeout=10m
until kubectl get resourceslices -o jsonpath='{.items[*].spec.driver}' | grep -q tenstorrent; do sleep 5; done

helm upgrade --install k8s-gpu-dra-driver k8s-gpu-dra-driver --repo https://rocm.github.io/k8s-gpu-dra-driver --version v1.0.1 \
  -n kube-amd-gpu --create-namespace --wait
until kubectl get resourceslices -o jsonpath='{.items[*].spec.driver}' | grep -q gpu.amd.com; do sleep 5; done
helm upgrade --install amd-exporter device-metrics-exporter-charts --repo https://rocm.github.io/device-metrics-exporter --version v1.5.3 \
  -n kube-amd-gpu --set serviceMonitor.enabled=true --wait
kubectl get resourceslices -o jsonpath='{range .items[*]}{.spec.driver}{": "}{range .spec.devices[*]}{.name} {end}{"\n"}{end}'

helm upgrade --install kueue oci://registry.k8s.io/kueue/charts/kueue --version 0.20.1 \
  -n kueue-system --create-namespace -f config/kueue-values.yaml --wait
until kubectl apply -f config/kueue.yaml; do sleep 5; done   # Kueue webhook answers a little after helm --wait
kubectl apply -f config/job-defaults.yaml
