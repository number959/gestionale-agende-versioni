# i commenti HTML del <main> di una tavola (spiegano ogni pezzo), in ordine
import re, sys
for f in sys.argv[1:]:
    s = open(f, encoding='utf-8').read()
    i = s.find('<main')
    j = s.find('</main>')
    corpo = s[i:j] if i >= 0 else s
    print('=====', f.rsplit('/', 1)[-1])
    for m in re.finditer(r'<!--(.*?)-->', corpo, re.S):
        print('-', re.sub(r'\s+', ' ', m.group(1)).strip())
