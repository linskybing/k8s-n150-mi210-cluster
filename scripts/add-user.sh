#!/usr/bin/env bash
# Add a user (Linux account with sudo + namespace u-<name> + ~/.kube/config); users add their own HF token (README):
#   sudo bash scripts/add-user.sh <name>
# New accounts get a random password, printed at the end. See docs/admin.md.
set -euo pipefail
cd "$(dirname "$0")/.."
U=${1:?usage: sudo bash scripts/add-user.sh <name>}
NS=u-$U
export KUBECONFIG=/etc/kubernetes/admin.conf

P=""
if ! id "$U" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "$U"
  P=$(openssl rand -hex 8)
  echo "$U:$P" | chpasswd
fi
usermod -aG sudo "$U"
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -
# n150/user: queued by Kueue + Job defaults; privileged: Jobs may use hostPath (e.g. their home) and devices
kubectl label namespace "$NS" --overwrite n150/user=true pod-security.kubernetes.io/enforce=privileged
kubectl apply -n "$NS" -f config/user.yaml
# users experiment with Kubernetes itself: full cluster-admin (trusted users only, see docs/admin.md)
kubectl create clusterrolebinding "$NS-admin" --clusterrole=cluster-admin --serviceaccount="$NS:user" --dry-run=client -o yaml | kubectl apply -f -

H=$(getent passwd "$U" | cut -d: -f6)
C=$H/.kube/config
install -d -o "$U" -g "$U" "$H/.kube"
kubectl config --kubeconfig "$C" set-cluster n150 --server=https://127.0.0.1:6443 \
  --certificate-authority=/etc/kubernetes/pki/ca.crt --embed-certs
kubectl config --kubeconfig "$C" set-credentials "$U" --token="$(kubectl -n "$NS" create token user --duration=8760h)"
kubectl config --kubeconfig "$C" set-context n150 --cluster=n150 --user="$U" --namespace="$NS"
kubectl config --kubeconfig "$C" use-context n150
chown "$U:$U" "$C" && chmod 600 "$C"
# examples mount /home/<you> via hostPath: fill in the name; never overwrite user edits
[ -e "$H/k8s-llm-example" ] || { cp -r ../k8s-llm-example "$H/" \
  && find "$H/k8s-llm-example" -name .git -prune -o -type f -exec sed -i "s/<you>/$U/g" {} + && chown -R "$U:$U" "$H/k8s-llm-example"; }
echo "$U password: ${P:-unchanged}"
