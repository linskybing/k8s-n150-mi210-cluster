#!/usr/bin/env bash
# Run as root on each node: sudo bash node.sh   (reboot afterwards so the amdgpu DKMS module is loaded)
set -euo pipefail
cd "$(dirname "$0")/.."
KMD=2.11.0
TOOLS=1.4.1
K8S=1.36.5-1.1
HELM=v4.3.0

export DEBIAN_FRONTEND=noninteractive
apt-get update
# python3-openai: users call the LLM from Python on the node
apt-get install -y dkms build-essential "linux-headers-$(uname -r)" curl gpg nftables python3-openai
install -m644 config/99-n150-sysctl.conf /etc/sysctl.d/99-n150.conf
install -m644 config/k8s-modules.conf /etc/modules-load.d/k8s.conf
modprobe overlay
modprobe br_netfilter
sysctl --system >/dev/null
install -m644 config/n150-firewall.nft /etc/n150-firewall.nft
install -m644 config/n150-firewall.service /etc/systemd/system/n150-firewall.service
systemctl daemon-reload
systemctl enable n150-firewall.service
systemctl restart n150-firewall.service

install -d -m755 /etc/apt/keyrings
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.36/deb/Release.key | gpg --dearmor --yes -o /etc/apt/keyrings/kubernetes.gpg
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
curl -fsSL https://repo.radeon.com/rocm/rocm.gpg.key | gpg --dearmor --yes -o /etc/apt/keyrings/rocm.gpg
install -m644 config/kubernetes.list /etc/apt/sources.list.d/kubernetes.list
install -m644 config/docker.list /etc/apt/sources.list.d/docker.list
install -m644 config/amdgpu.list /etc/apt/sources.list.d/amdgpu.list
apt-get update
apt-get install -y containerd.io kubelet="$K8S" kubeadm="$K8S" kubectl="$K8S" amdgpu-dkms
apt-mark hold kubelet kubeadm kubectl
install -m644 config/containerd.toml /etc/containerd/config.toml
systemctl restart containerd

curl -fsSLo /tmp/tenstorrent-dkms.deb "https://github.com/tenstorrent/tt-kmd/releases/download/ttkmd-$KMD/tenstorrent-dkms_${KMD}_all.deb"
curl -fsSLo /tmp/tenstorrent-tools.deb "https://github.com/tenstorrent/tt-system-tools/releases/download/v$TOOLS/tenstorrent-tools_${TOOLS}_all.deb"
apt-get install -y /tmp/tenstorrent-dkms.deb /tmp/tenstorrent-tools.deb
groupadd -f -g 2150 tenstorrent
install -m644 config/99-tenstorrent.rules /etc/udev/rules.d/99-tenstorrent.rules
udevadm control --reload
modprobe tenstorrent
udevadm trigger --subsystem-match=tenstorrent --settle
# hugepages must exist before kubelet starts so it reports hugepages-1Gi
systemctl enable --now tenstorrent-hugepages.service 'dev-hugepages\x2d1G.mount'

[ -e /etc/kubernetes/admin.conf ] || kubeadm init --config config/kubeadm.yaml
export KUBECONFIG=/etc/kubernetes/admin.conf
kubectl taint nodes --all node-role.kubernetes.io/control-plane- 2>/dev/null || true   # single node: run workloads here
kubectl completion bash > /etc/bash_completion.d/kubectl
U="${SUDO_USER:-root}"
install -Dm600 -o "$U" -g "$U" /etc/kubernetes/admin.conf "$(getent passwd "$U" | cut -d: -f6)/.kube/config"
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-4 | bash -s -- --version "$HELM"
