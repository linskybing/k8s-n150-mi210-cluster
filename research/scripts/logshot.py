#!/usr/bin/env python3
"""Log screenshots for the report (figs/log-*.png).

Each command runs for real (bash, in the shot's directory, on the saved experiment logs); the image shows the
command and its output verbatim, with red boxes around the evidence. Needs Pillow and jq.
  python3 scripts/logshot.py
"""
import re
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

R = Path(__file__).resolve().parent.parent
FONT = '/System/Library/Fonts/Menlo.ttc'  # shortcut: macOS font, point to any monospace .ttf elsewhere
COLS, SIZE, PAD, BAR = 100, 22, 24, 40
BG, FG, CMD, COMMENT, PROMPT, BOX = '#1e1e1e', '#d4d4d4', '#ffffff', '#7f8c8d', '#4ec9b0', '#ff4d4d'
DRA = r"""grep -E '"(Prepared|Unprepared) claim"' dra-plugin.log | sed -E 's/ (logger|requestID|method|uid|lockWait|checkpointRead|checkpointWrite)=("[^"]*"|[^ ]*)//g'"""
CHIP = """jq -c '.status.flavorsUsage[].resources[] | select(.name=="tenstorrent.com/chip")'"""
TUNE = 'experiments/EXP-05-n150-vllm-tuning/raw/runs'

# name: (directory, commands, strings to box)
SHOTS = {
    'log-load': (f'{TUNE}/vllm-r1', [
        'cat status.txt  # kubectl get resourceclaims -o wide; kubectl get workloads -o wide',
        "jq -c '.items[].status.allocation.devices.results[]' resourceclaim.json",
        f'{CHIP} cq-loaded.json',
        'cat devices.txt  # ls -l /dev/tenstorrent/ in the vLLM container',
        'cat device-fds.txt  # processes holding /dev/tenstorrent: pid, fds, command',
        "sed -n '1,2p;5,6p' query.txt",
        "sed -n 4p query.txt | jq -c '.data[] | {id, max_model_len}'",
    ], ['allocated,reserved', '"device":"tt-0"', '"total":"1"', 'VLLM::EngineCore', '200 0.003205s']),
    'log-dra': (f'{TUNE}/vllm-r1', [
        DRA,
        "grep -E '^(submit|delete|quota-released|claim-gone) ' marks.txt  # times from the test script",
        f'{CHIP} cq-unloaded.json',
    ], ['duration="2.219028ms"', 'duration="1.3106ms"', '"total":"0"']),
    'log-queue': ('experiments/EXP-02-n150-queueing/raw/queue-b', [
        "jq -c '.spec.template.spec | {resourceClaims, command: .containers[0].command}' job-a.json",
        """jq -r '.items[] | select(.involvedObject.name=="job-n150-job-b-433e7") | "\\(.eventTime[11:23]) \\(.reason): \\(.message)"' events.json""",
        """jq -r '"\\(.metadata.name) start=\\(.status.startTime) completion=\\(.status.completionTime)"' job-a.json job-b.json""",
        "sed -n '2p;29,32p' sample.txt  # every second: Workload Admitted | ResourceClaims",
        'tail -n +1 job-a.log job-b.log  # container output',
    ], ['insufficient unused quota for tenstorrent.com/chip', 'wait time since queued was 35s',
        'completion=2026-11-10T04:05:36Z', 'job-n150-job-b-433e7   True', 'Tue Nov 10 04:05:34 UTC 2026',
        'Tue Nov 10 04:05:38 UTC 2026']),
    'log-tuning': (TUNE, [
        """for d in vllm-*; do echo "$d $(grep -o 'trace_mode=.*' $d/server-full.log)"; done""",
        """for d in vllm-*; do echo "$d $(grep -oE "'(max_model_len|max_num_seqs)': [0-9]+" $d/server-full.log | tr '\\n' ' ')"; done""",
        "grep -c 'Downloading weights' vllm-cache-r*/server-full.log",
    ], ['trace_mode=none', 'sample_on_device_mode=all', 'enable_model_warmup=False', "'max_num_seqs': 16",
        "'max_model_len': 2048", 'vllm-cache-r2/server-full.log:0']),
}


def wrap(s):
    """Split at spaces like a terminal pager would, keeping every character so the parts join back to s."""
    return textwrap.wrap(s, COLS, drop_whitespace=False, replace_whitespace=False, break_on_hyphens=False) or ['']


def render(name, cwd, cmds, boxes):
    rows = []  # (part, color, offset of part in its line, line, where the comment starts)
    for cmd in cmds:
        out = subprocess.run(['bash', '-c', cmd], cwd=R / cwd, capture_output=True, text=True, check=True).stdout
        assert out.strip(), (name, cmd)
        lines = [('$ ' + cmd, CMD)] + [(l.rstrip(), FG) for l in
                                       re.sub(r'\x1b\[[0-9;]*m', '', out).expandtabs(8).rstrip('\n').split('\n')]
        for line, color in lines:
            off = 0
            for part in wrap(line):
                rows.append((part, color, off, line, line.find('  # ') if color == CMD else -1))
                off += len(part)
    text = '\n'.join(r[0] for r in rows)
    for b in boxes:  # every box must be in the real output
        assert any(b in r[3] for r in rows if r[1] == FG), (name, b)
    font, bold = ImageFont.truetype(FONT, SIZE, index=0), ImageFont.truetype(FONT, SIZE, index=1)
    cw, lh = font.getlength('M'), int(SIZE * 1.45)
    img = Image.new('RGB', (int(PAD * 2 + COLS * cw), BAR + PAD * 2 + lh * len(rows)), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, img.width, BAR], fill='#2d2d2d')
    for i, c in enumerate(('#ff5f56', '#ffbd2e', '#27c93f')):
        d.ellipse([16 + i * 26, BAR // 2 - 7, 30 + i * 26, BAR // 2 + 7], fill=c)
    for n, (s, color, off, line, cut) in enumerate(rows):
        x, y = PAD, BAR + PAD + n * lh
        if color == CMD and off == 0 and n:
            d.line([PAD, y - 4, img.width - PAD, y - 4], fill='#3a3a3a')
        c = min(max(cut - off, 0), len(s)) if cut >= 0 else len(s)  # comment part of a command row
        head = s[:c]
        if color == CMD and off == 0:
            d.text((x, y), '$', font=bold, fill=PROMPT)
            head = '  ' + head[2:]
        d.text((x, y), head, font=bold if color == CMD else font, fill=color)
        d.text((x + cw * c, y), s[c:], font=font, fill=COMMENT)
        for b in boxes if color == FG else []:
            for m in re.finditer(re.escape(b), line):
                a, z = max(m.start(), off) - off, min(m.end(), off + len(s)) - off
                if a < z:
                    d.rectangle([x + cw * a - 3, y - 2, x + cw * z + 3, y + lh - 4], outline=BOX, width=3)
    img.save(R / 'figs' / f'{name}.png')
    return text


if __name__ == '__main__':
    for name, spec in SHOTS.items():
        print(f'== {name}\n' + render(name, *spec))
