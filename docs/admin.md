# 管理員：新增／移除使用者

以下指令都在 node 上，用管理員帳號執行。

## 新增使用者
```bash
ssh sky@<node-ip>
sudo bash n150/scripts/add-user.sh alice
```
Hugging Face token 由使用者自己建立（README 有指令），不要把管理員的 token 放到 node 上：使用者有 sudo 和 cluster-admin，node 上的任何 secret 和檔案他們都讀得到。

最後一行會印出隨機產生的密碼：
```
alice password: <random password>
```
把這些交給使用者：
- 帳號 `alice` 和這組密碼（登入後可以用 `passwd` 自己改）
- 登入方式：`ssh alice@<node-ip>`
- 登入後看家目錄裡的 `k8s-llm-example/README.md`（範例和說明）

腳本會建立：
- Linux 帳號 `alice`，密碼隨機產生，在 sudo 群組
- namespace `u-alice`（PSA privileged）：這裡的 Job 預設要排隊
- **cluster-admin**（clusterrolebinding `u-alice-admin`）：使用者可以動整個 cluster（實驗需要），只開給信任的人
- ResourceClaimTemplate `n150`、`mi210`（1 張 MI210）：Job 引用才會拿到卡；要多張可以自己建立 `count: N` 的 template
- `~/.kube/config`：登入後直接就能用 `kubectl`
- `~/k8s-llm-example`：使用者 repo（`../k8s-llm-example`）的副本，範例裡的 `<you>` 換成 `alice`（Job 用 hostPath 掛 `/home/alice`）

對已經存在的帳號重跑一次，不會改密碼，只會更新設定。`~/k8s-llm-example` 已存在時不會複製，使用者改過的檔案不會被覆蓋。

## 重設密碼
```bash
sudo passwd alice
```

## 卡不見了
`kubectl get resourceslices` 少了 n150（driver `tenstorrent.com`）或 MI210（driver `gpu.amd.com`，應該有 4 個）時，Job 會一直等卡。重啟對應的 DRA plugin：
```bash
kubectl -n tt-operator-system rollout restart ds/tt-operator-tt-dra-driver-kubeletplugin   # n150
kubectl -n kube-amd-gpu get ds                                                              # MI210: 找到 kubeletplugin 再 rollout restart
```

## 監控
```bash
kubectl -n monitoring port-forward svc/kube-prometheus-stack-prometheus 9090 &   # http://127.0.0.1:9090/targets
kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80 &   # 帳號 admin，密碼：
kubectl -n monitoring get secret kube-prometheus-stack-grafana -o jsonpath='{.data.admin-password}' | base64 -d
```
Prometheus 會抓 cluster 裡所有的 ServiceMonitor/PodMonitor，使用者自己的 exporter 也一樣。

## Host IP 變了
kubeadm 的憑證和 etcd 都綁在 IP 上。使用者的 kubeconfig 走 127.0.0.1，不受影響。最簡單的做法是重建：改 `config/kubeadm.yaml` 的 certSANs，然後
`sudo kubeadm reset -f`，重跑 `node.sh`、`cluster.sh`，再對每個使用者重跑 `add-user.sh`（家目錄保留）。

## 移除使用者
```bash
kubectl delete ns/u-alice clusterrolebinding/u-alice-admin
sudo userdel -r alice   # 家目錄會一起刪除
```

## 憑證一年到期
kubeadm 的憑證和使用者 token（add-user.sh 簽 8760h）都是一年。到期前執行 `sudo kubeadm certs renew all`，重啟 control plane（`sudo systemctl restart kubelet`），再對每個使用者重跑 `add-user.sh`。

## 防火牆
node 在公網 IP。`config/n150-firewall.nft`（`n150-firewall.service`）只讓外部連 22（SSH）和 6443（API server），其他 port（metrics、etcd、kubelet、NodePort）只有 node 自己和 pod 連得到。要多開 port 就改 `tcp dport { 22, 6443 }`，然後 `sudo install -m644 n150/config/n150-firewall.nft /etc/ && sudo systemctl restart n150-firewall`。
