# BOZZA tappa 9: da mettere in gestionale/app.py subito dopo @app.errorhandler(413) (app.py:227). Non è nel
# repository. Provata nella copia della cartella di lavoro (copia/app.py), vedi misure/confronto-bozze.txt.

# «Pagina non trovata» in italiano. Prima: la pagina inglese di Flask («404 Not Found») per i 41 abort(404) e per
# ogni indirizzo che non esiste. La risposta resta 404 (le prove guardano solo il numero).
#  - JSON (…​.json, o una richiesta fatta dallo script con X-Richiesta): un JSON corto, perché gli script
#    controllano r.ok e non leggono l'HTML (guida.js:146, dove.js:63, 145);
#  - /riepilogo-live*, /logo/, /static/: la pagina senza cornice. Il Modo schermo sugli altri PC passa dal portiere
#    (Caddy) solo per questi indirizzi: niente menu, campanella e /notifiche.json (la guardia del canarino, tappa 1);
#  - il resto: la pagina nella cornice, con il menu.
# Se il modello non c'è (l'eseguibile senza la cartella dei modelli: risorse_presenti), render_template fallisce e
# risponde il gestore del 500, che ha la sua pagina scritta qui (PAGINA_ERRORE).
@app.errorhandler(404)
def non_trovata(_):
    percorso = request.path or ''
    if percorso.endswith('.json') or request.headers.get('X-Richiesta'):
        return Response(json.dumps({'errore': 'non trovato'}), status=404, mimetype='application/json')
    senza_cornice = percorso.startswith(('/riepilogo-live', '/logo/', '/static/'))
    return render_template('non_trovata.html', senza_cornice=senza_cornice), 404

# Restano in inglese (domanda per Giovanni, non è nel piano): 405 «Method Not Allowed» (un indirizzo che accetta solo
# moduli, aperto dalla barra del browser, per esempio /appuntamento/1/stato) e i 6 abort(400) di invii.py, personale.py
# e sala.py. Con lo stesso gestore: @app.errorhandler(405) e (400) con la stessa pagina e un titolo diverso.
