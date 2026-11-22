"""La macro euro() di _pezzi.html contro i tre modi di oggi, su molti importi (interi, in centesimi)."""
import random, sys
sys.path.insert(0, '/home/user/gestionale-agende-versioni/gestionale')
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from modelli import importo_in_testo
B = sys.argv[1]
env = Environment(loader=FileSystemLoader([B + '/templates', '/home/user/gestionale-agende-versioni/gestionale/templates']),
                  undefined=StrictUndefined)
env.filters['euro'] = importo_in_testo
vecchie = env.from_string(
    "{% macro cassa(c) %}{{ '{:,.2f}'.format(c / 100.0).replace(',', 'x').replace('.', ',').replace('x', '.') }}{% endmacro %}"
    "{% macro stat(c) %}{% if c %}{{ '{:,.2f}'.format(c / 100.0).replace(',', 'x').replace('.', ',').replace('x', '.') }}{% else %}—{% endif %}{% endmacro %}"
    "{% from '_pezzi.html' import euro %}"
    "{{ c|euro }}|{{ cassa(c) }}|{{ stat(c) }}|{{ euro(c) }}|{{ euro(c, se_zero='—') }}|{{ euro(c, simbolo=true) }}")
r = random.Random(7)
valori = [0, 1, -1, 5, -5, 99, 100, 101, 12345, 125050, -125050, 10 ** 9, -10 ** 9 - 7] + \
         [r.randint(-10 ** 8, 10 ** 8) for _ in range(20000)] + [r.randint(0, 10 ** 12) for _ in range(2000)]
male = []
for c in valori:
    a, b, s, n1, n2, n3 = vecchie.render(c=c).split('|')
    if not (a == b == n1 and s == n2 and n3 == a + ' €'):
        male.append((c, a, b, s, n1, n2, n3))
# None: il filtro dà «», statistiche «—»; cassa_mese andrebbe in errore (oggi non succede: lì i totali sono sempre numeri)
n = env.from_string("{% from '_pezzi.html' import euro %}[{{ None|euro }}][{{ euro(None) }}][{{ euro(None, se_zero='—') }}][{{ euro(None, simbolo=true) }}]").render()
print('importi provati:', len(valori), ' diversi:', len(male), male[:5])
print('None:', n)
