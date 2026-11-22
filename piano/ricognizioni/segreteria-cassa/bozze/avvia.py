import os, sys
codice, db, porta = sys.argv[1], sys.argv[2], int(sys.argv[3])
sys.path.insert(0, codice); os.chdir(codice)
os.environ.setdefault('LOCALAPPDATA', os.path.join(os.path.dirname(db), 'locale-' + str(porta)))
import app as A
from modelli import crea_sessione
A.Sessione = crea_sessione('sqlite:///' + db); A._registro = None
from waitress import serve
serve(A.app, host='127.0.0.1', port=porta, threads=4)
