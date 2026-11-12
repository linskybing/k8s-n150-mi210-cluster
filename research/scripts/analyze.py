#!/usr/bin/env python3
"""EXP-01/02/03/04/05 raw -> processed CSVs. Run from research/: python3 scripts/analyze.py
Times: API object timestamps (1 s resolution) and marks.txt (node `date`, ms); one clock (single node)."""
import csv
import glob
import json
import os
import re
import statistics as st
from datetime import datetime

E1 = 'experiments/EXP-01-n150-lifecycle'
E2 = 'experiments/EXP-02-n150-queueing'
E3 = 'experiments/EXP-03-n150-batching'
E4 = 'experiments/EXP-04-n150-throughput-clean'
E5 = 'experiments/EXP-05-n150-vllm-tuning'
E6 = 'experiments/EXP-06-n150-llama31-8b'


def t(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()


def marks(d):
    m = {}
    for line in open(f'{d}/marks.txt'):
        k, v = line.split()
        m[k] = t(v)  # a repeated key (vllm-r2 query, interrupted then rerun) keeps the last one
    return m


def logtime(path, pattern):
    """first 'YYYY-MM-DD HH:MM:SS' timestamp on a line matching pattern (server log clock = node clock, UTC)"""
    for line in open(path, errors='replace'):
        if re.search(pattern, line):
            ts = re.search(r'(\d{4}-\d\d-\d\d[ T]\d\d:\d\d:\d\d)', line)
            if ts:
                return t(ts.group(1).replace(' ', 'T') + 'Z')
    return None


def server_up(path):
    """server's own ready line: SGLang '[YYYY-MM-DD HH:MM:SS] The server is fired up', vLLM 'INFO MM-DD HH:MM:SS ... Starting vLLM API server'"""
    for line in open(path, errors='replace'):
        if 'The server is fired up' in line:
            return logtime(path, 'The server is fired up')
        if 'Starting vLLM API server' in line:
            mm, dd, hms = re.search(r'(\d\d)-(\d\d) (\d\d:\d\d:\d\d)', line).groups()
            return t(f'2026-{mm}-{dd}T{hms}Z')  # vLLM log lines carry no year; all runs are in 2026
    return None


def klog(path, pattern):
    """(time, duration_ms) of klog lines 'IMMDD HH:MM:SS.ffffff ... duration="..."' matching pattern (DRA kubelet plugin)"""
    out = []
    for line in open(path, errors='replace'):
        if re.search(pattern, line):
            mm, dd, hms = re.match(r'I(\d\d)(\d\d) (\d\d:\d\d:\d\d\.\d+)', line).groups()
            dur = re.search(r'duration="([\d.]+)(ms|µs)"', line)
            ms = float(dur.group(1)) / (1000 if dur and dur.group(2) == 'µs' else 1) if dur else None
            out.append((t(f'2026-{mm}-{dd}T{hms}Z'), ms))  # klog lines carry no year; all runs are in 2026
    return out


def lifecycle(d):
    m = marks(d)
    job = json.load(open(f'{d}/job.json'))
    wl = [w for w in json.load(open(f'{d}/workload.json'))['items']
          if any(o['uid'] == job['metadata']['uid'] for o in w['metadata'].get('ownerReferences', []))][0]
    cond = {c['type']: t(c['lastTransitionTime']) for c in wl['status']['conditions']}
    pod = json.load(open(f'{d}/pod.json'))
    pc = {c['type']: t(c['lastTransitionTime']) for c in pod['status']['conditions']}
    started = t(pod['status']['containerStatuses'][0]['state']['running']['startedAt'])
    claim = [c for c in json.load(open(f'{d}/resourceclaim.json'))['items']
             if c['metadata']['name'] == pod['status']['resourceClaimStatuses'][0]['resourceClaimName']][0]
    alloc = t(claim['status']['allocation']['allocationTimestamp'])
    log = f'{d}/server-full.log'
    dl0, dl1 = logtime(log, 'Downloading weights'), logtime(log, 'MODEL_WEIGHTS_DIR')
    init = re.search(r'init engine .* took ([\d.]+) seconds', open(log, errors='replace').read())
    r = dict(submit_to_admitted_s=cond['Admitted'] - t(job['metadata']['creationTimestamp']),
             admitted_to_allocated_s=alloc - cond['Admitted'],
             allocated_to_running_s=started - alloc,
             running_to_ready_s=m['ready'] - started,
             submit_to_ready_s=m['ready'] - m['submit'],
             weights_download_s=(dl1 - dl0) if dl0 and dl1 else '',
             engine_init_s=float(init.group(1)) if init else '',
             delete_to_quota_released_s=m['quota-released'] - m['delete'],
             delete_to_pod_gone_s=m['pod-gone'] - m['delete'],
             delete_to_claim_gone_s=m['claim-gone'] - m['delete'],
             submit_to_server_up_s=server_up(log) - m['submit'],
             dra_prepare_ms=klog(f'{d}/dra-plugin.log', r'PrepareResourceClaims finished.*numClaims=1')[0][1],
             dra_unprepare_ms=klog(f'{d}/dra-plugin.log', r'UnprepareResourceClaims finished.*numClaims=1')[0][1])
    # self-check: events in order, the claim holds exactly the one n150 device
    assert m['submit'] <= m['ready'] and m['delete'] <= m['quota-released'] and m['pod-gone'] <= m['claim-gone'], d
    res = claim['status']['allocation']['devices']['results']
    assert len(res) == 1 and res[0]['driver'] == 'tenstorrent.com' and res[0]['device'] == 'tt-0', d
    assert wl['status']['admission']['podSetAssignments'][0]['resourceUsage']['tenstorrent.com/chip'] == '1', d
    return r


def summarize(rows, keys, cols):
    out = []
    for k in sorted({tuple(r[c] for c in keys) for r in rows}):
        g = [r for r in rows if tuple(r[c] for c in keys) == k]
        s = dict(zip(keys, k), n=len(g))
        for c in cols:
            v = [float(r[c]) for r in g if r[c] != '']
            if v:
                s[c + '_mean'], s[c + '_min'], s[c + '_max'] = round(st.mean(v), 3), round(min(v), 3), round(max(v), 3)
        out.append(s)
    return out


def write(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        w.writerows(rows)
    print(path, len(rows))


# EXP-01
rows = []
for d in sorted(glob.glob(f'{E1}/raw/runs/*-r[0-9]')):
    fw, rep = os.path.basename(d).rsplit('-r', 1)
    rows.append(dict(framework=fw, rep=int(rep), **{k: round(v, 3) if v != '' else v for k, v in lifecycle(d).items()}))
write(f'{E1}/processed/lifecycle.csv', rows)
write(f'{E1}/processed/lifecycle-summary.csv', summarize(rows, ['framework'], [k for k in rows[0] if k.endswith(('_s', '_ms'))]))

# EXP-03 (seed = rep), EXP-04 and EXP-05 (seed 10 x concurrency + rep, temperature 0): same processing
# EXP-03/04 keep each bench in raw/<server>/; EXP-05 keeps lc.sh's layout raw/runs/<setting>-r<rep>/bench/
for E, pat in ((E3, 'raw/*/c*-r*.json'), (E4, 'raw/*/c*-r*.json'), (E5, 'raw/runs/*/bench/c*-r*.json'),
               (E6, 'raw/runs/*/bench/c*-r*.json')):
  rows = []
  for f in sorted(glob.glob(f'{E}/{pat}')):
      b = json.load(open(f))
      p = f.split('/')
      srv = p[-3].rsplit('-r', 1)[0] if p[-2] == 'bench' else p[-2]
      assert b['completed'] == b['num_prompts'] and b.get('failed', 0) == 0, f  # vLLM 6e67d2d (EXP-06) writes no 'failed'
      assert b['total_output_tokens'] == 128 * b['completed'], f  # --ignore-eos: every request returns exactly 128 tokens
      rows.append(dict(server=srv, concurrency=b['max_concurrency'], rep=int(re.search(r'-r(\d)\.json$', f).group(1)),
                       num_prompts=b['num_prompts'], duration_s=round(b['duration'], 3),
                       output_tok_s=round(b['output_throughput'], 3), request_s=round(b['request_throughput'], 4),
                       mean_ttft_ms=round(b['mean_ttft_ms'], 2), median_ttft_ms=round(b['median_ttft_ms'], 2),
                       p99_ttft_ms=round(b['p99_ttft_ms'], 2), mean_tpot_ms=round(b['mean_tpot_ms'], 2),
                       mean_e2el_ms=round(b['mean_e2el_ms'], 2)))
  if rows:
      write(f'{E}/processed/throughput.csv', rows)
      write(f'{E}/processed/throughput-summary.csv',
            summarize(rows, ['server', 'concurrency'], ['output_tok_s', 'mean_ttft_ms', 'mean_tpot_ms', 'mean_e2el_ms']))

# EXP-02: event times in seconds from the first submit; at most one allocated tenstorrent claim in every 1 s sample
def max_claims(sample):
    return max(line.split('claims:')[1].count('allocated') for line in open(sample) if 'claims:' in line)


qa, qb = f'{E2}/raw/queue-a', f'{E2}/raw/queue-b'
v3, sq = marks(f'{E1}/raw/runs/vllm-r3'), marks(f'{E2}/raw/sglang-rq')
swl = [w for w in json.load(open(f'{E2}/raw/sglang-rq/workload.json'))['items'] if 'sglang' in w['metadata']['name']][0]
# Kueue's Admitted event carries microseconds; the Workload condition is truncated to the second
sadm = [t(e['eventTime']) for e in json.load(open(f'{E2}/raw/sglang-rq/events.json'))['items']
        if e['reason'] == 'Admitted' and 'sglang' in e['involvedObject']['name']][0]
dra = f'{E2}/raw/sglang-rq/dra-plugin.log'  # covers both claims: vLLM's unprepare and SGLang's prepare
vunprep = klog(dra, r'"Unprepared claim"')[0][0]
sprep = klog(dra, r'PrepareResourceClaims finished.*numClaims=1')[0][0]
t0 = sq['submit']
rows = [dict(case='a', job='n150-sglang-custom', event=e, t_s=round(v - t0, 3)) for e, v in
        [('submit', sq['submit']), ('admitted (Kueue event)', sadm), ('claim prepared (DRA plugin)', sprep), ('ready', sq['ready'])]]
rows += [dict(case='a', job='n150-llm', event=e, t_s=round(v3[k] - t0, 3)) for e, k in
         [('delete', 'delete'), ('quota released', 'quota-released'), ('claim gone', 'claim-gone')]]
rows.append(dict(case='a', job='n150-llm', event='claim unprepared (DRA plugin)', t_s=round(vunprep - t0, 3)))
ja, jb = (json.load(open(f'{qb}/job-{j}.json'))['status'] for j in 'ab')
t0 = min(t(ja['startTime']), t(jb['startTime']))
for name, s in (('n150-job-a', ja), ('n150-job-b', jb)):
    rows += [dict(case='b', job=name, event=e, t_s=round(t(s[k]) - t0, 3)) for e, k in (('start', 'startTime'), ('complete', 'completionTime'))]
assert sadm >= v3['delete'], 'SGLang admitted before vLLM was deleted'
assert sprep > vunprep, 'SGLang claim prepared before the vLLM claim was unprepared'
assert t(jb['startTime']) >= t(ja['completionTime']), 'n150 Jobs overlapped'
assert max_claims(f'{qa}/sample.txt') == 1 and max_claims(f'{qb}/sample.txt') == 1, 'two claims allocated at once'
write(f'{E2}/processed/queueing.csv', rows)

# EXP-04 P1: prefix-cache reuse during the bench (vLLM counters after the bench; SGLang prefill log lines with cached tokens).
# Expected residue: `vllm bench serve` sends each run's first prompt once as a test request before the run (10 runs incl. warmup).
if os.path.isdir(f'{E4}/raw'):
    for srv in ('vllm-a', 'vllm-b'):
        m = {l.split('{')[0]: l.split()[-1] for l in open(f'{E4}/raw/{srv}/metrics-after.txt') if l.startswith('vllm:prefix_cache_')}
        print(f'EXP-04 {srv}: prefix_cache_hits_total {m.get("vllm:prefix_cache_hits_total")} of queries {m.get("vllm:prefix_cache_queries_total")}')
    n = sum(1 for l in open(f'{E4}/raw/sglang-run/server-full.log', errors='replace') if re.search(r'#cached-token: [1-9]', l))
    total = sum(1 for l in open(f'{E4}/raw/sglang-run/server-full.log', errors='replace') if 'Prefill batch' in l)
    print(f'EXP-04 sglang: prefill batches with cached tokens {n} of {total}')

# EXP-05: load times per setting, and the self-check that each setting took effect (server log)
EXPECT = {
    'vllm': ['trace_mode=all, sample_on_device_mode=None, enable_model_warmup=True', "'max_num_seqs': 32", "'max_model_len': 8192"],
    'vllm-sod': ['sample_on_device_mode=all'],
    'vllm-notrace': ['trace_mode=none'],
    'vllm-b16': ["'max_num_seqs': 16"],
    'vllm-len2k': ["'max_model_len': 2048"],
    'vllm-nowarm': ['enable_model_warmup=False'],
    'vllm-cache': ['trace_mode=all, sample_on_device_mode=None, enable_model_warmup=True'],
}
rows = []
for d in sorted(glob.glob(f'{E5}/raw/runs/*-r[0-9]')):
    fw, rep = os.path.basename(d).rsplit('-r', 1)
    log = open(f'{d}/server-full.log', errors='replace').read()
    for s in EXPECT[fw]:
        assert s in log, (d, s)
    m = marks(d)
    rows.append(dict(setting=fw, rep=int(rep), **{k: round(v, 3) if v != '' else v for k, v in lifecycle(d).items()},
                     first_request_s=round(m['chat-done'] - m['chat-start'], 3),
                     weights_downloaded=int('Downloading weights' in log)))
if rows:
    assert all(r['weights_downloaded'] == (0 if r['setting'] == 'vllm-cache' and r['rep'] == 2 else 1) for r in rows), 'download'
    write(f'{E5}/processed/tuning-lifecycle.csv', rows)
