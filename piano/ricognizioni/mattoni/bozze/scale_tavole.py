"""Conta raggi, grandezze di carattere, spazi e colori nelle tavole Nefro (quelle col blu #1C4184)."""
import re, glob, os, collections, sys, json
CART = sys.argv[1]
file = [f for f in sorted(glob.glob(os.path.join(CART, '*.dc.html'))) if '#1C4184' in open(f, encoding='utf-8').read()]
r = collections.Counter(); fs = collections.Counter(); gap = collections.Counter(); pad = collections.Counter()
col = collections.Counter(); lh = collections.Counter(); fw = collections.Counter(); h = collections.Counter()
per_file_r = collections.defaultdict(set); per_file_fs = collections.defaultdict(set)
for f in file:
    t = open(f, encoding='utf-8').read()
    t = re.sub(r'data:image/[^"\')]+', '', t)
    b = os.path.basename(f)
    for m in re.finditer(r'border-radius:\s*([^;"\'}]+)', t):
        for v in m.group(1).split():
            r[v.strip()] += 1; per_file_r[v.strip()].add(b)
    for m in re.finditer(r'font-size:\s*([0-9.]+px)', t):
        fs[m.group(1)] += 1; per_file_fs[m.group(1)].add(b)
    for m in re.finditer(r'(?<![-\w])gap:\s*([^;"\'}]+)', t):
        for v in m.group(1).split(): gap[v] += 1
    for m in re.finditer(r'padding(?:-\w+)?:\s*([^;"\'}]+)', t):
        for v in m.group(1).split(): pad[v] += 1
    for m in re.finditer(r'line-height:\s*([^;"\'}]+)', t): lh[m.group(1).strip()] += 1
    for m in re.finditer(r'font-weight:\s*([0-9]+)', t): fw[m.group(1)] += 1
    for m in re.finditer(r'(?<![-\w])height:\s*([0-9.]+px)', t): h[m.group(1)] += 1
    for m in re.finditer(r'#[0-9A-Fa-f]{6}\b', t): col[m.group(0).upper()] += 1
out = {'file': [os.path.basename(f) for f in file],
       'raggi': sorted(r.items(), key=lambda x: -x[1]), 'caratteri': sorted(fs.items(), key=lambda x: float(x[0][:-2])),
       'gap': sorted(gap.items(), key=lambda x: -x[1])[:40], 'padding': sorted(pad.items(), key=lambda x: -x[1])[:40],
       'line_height': sorted(lh.items(), key=lambda x: -x[1])[:30], 'peso': sorted(fw.items()), 'altezze': sorted(h.items(), key=lambda x: -x[1])[:30],
       'colori': sorted(col.items(), key=lambda x: -x[1])[:120],
       'raggi_file': {k: len(v) for k, v in per_file_r.items()}, 'caratteri_file': {k: len(v) for k, v in per_file_fs.items()}}
json.dump(out, open(sys.argv[2], 'w'), indent=1, ensure_ascii=False)
print(len(file), 'tavole')
print('raggi', len(r), out['raggi'])
print('caratteri', len(fs), out['caratteri'])
print('gap', out['gap'][:25])
print('padding', out['padding'][:30])
print('lh', out['line_height'][:15])
print('peso', out['peso'])
print('altezze', out['altezze'][:25])
