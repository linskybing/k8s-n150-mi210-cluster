# n150 + MI210 on Kubernetes (kubeadm + DRA + Kueue)

Single node: Ubuntu 24.04 VM (kernel 7.0 HWE), Tenstorrent Wormhole n150 + 4x AMD Instinct MI210, no IOMMU (1G hugepages, trusted users only).
Users SSH in and submit Jobs with kubectl; Kueue queues them for the cards (Slurm-like). Every user has sudo and is cluster-admin (they experiment with Kubernetes itself).
User repo (examples + guide, no admin stuff): `../k8s-llm-example`, copied to each user's `~/k8s-llm-example`. Add/remove users: `docs/admin.md`.

```
scripts/node.sh      per node (root): containerd, kubeadm v1.36, amdgpu-dkms 31.60, tt-kmd DKMS, 1G hugepages, device group 2150, helm
scripts/cluster.sh   per cluster: Cilium, Prometheus stack + metrics-server, tt-operator (n150 DRA + tt-telemetry), AMD GPU DRA + metrics exporter, Kueue + queue, user Job defaults
scripts/add-user.sh  Linux user (sudo) + namespace u-<name> (cluster-admin) + ~/.kube/config + copy of the user repo
config/              kubeadm, containerd, firewall, apt repos, cilium, monitoring, tt-operator, kueue, udev, job-defaults (no retries; device groups; hugepages for Jobs using template n150)
```

## Install
```bash
rsync -a --exclude .env ./ <user>@<node>:n150/   # edit certSANs in config/kubeadm.yaml first
rsync -a ../k8s-llm-example <user>@<node>:              # add-user.sh reads it from ../k8s-llm-example
ssh <user>@<node>
sudo bash n150/scripts/node.sh && sudo reboot          # reboot loads the amdgpu DKMS module
bash n150/scripts/cluster.sh
sudo bash n150/scripts/add-user.sh alice                  # prints a random password, see docs/admin.md
```

## Notes
- Context length is set in `k8s-llm-example/n150/llama-3.2-1b-n150.json` (runtime model spec); the image default (128k) runs out of n150 DRAM.
- `/dev/tenstorrent` is `root:tenstorrent 0660`, `/dev/kfd` + `/dev/dri/renderD*` are `root:render(993) 0660`; Jobs get both groups via `supplementalGroups`, shell users cannot open the cards.
- AMD only validates Instinct on Ubuntu 24.04 with kernel 6.8 GA; here amdgpu-dkms runs on 7.0 HWE (validated for Radeon).
- Public IP: host firewall `config/n150-firewall.nft` lets in only SSH (22) and the API server (6443) from outside; everything else only from the node itself and pods. Web UIs via `kubectl port-forward`.
- Metrics: Prometheus scrapes every ServiceMonitor/PodMonitor in the cluster (control plane, etcd, kubelet, node-exporter, kube-state-metrics, Cilium/Hubble, Kueue, AMD exporter, tt-telemetry).
- Without IOMMU a pod holding the card can DMA into all VM memory; enabling vIOMMU on the hypervisor (and dropping `iommu=pt`) is the real fix.
