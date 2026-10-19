/* Dove si fa: la ricerca mentre si scrive, la scheda della struttura, il messaggio
   per il paziente e il registro dei pazienti indirizzati. Nessuna libreria.
   I risultati e la scheda arrivano gia' scritti dal server, con gli stessi modelli
   della pagina intera (_dove_risultati.html, _dove_scheda.html), dove i dati sono gia'
   codificati: qui si inseriscono cosi' come sono. Quello che arriva come JSON
   (pazienti, esito del registro) si scrive sempre con textContent. */
(function () {
  'use strict';

  var pagina = document.getElementById('pagina-dove');
  if (!pagina) { return; }
  function $(id) { return document.getElementById(id); }
  var campo = $('q-dove'), branca = $('branca-dove'), risultati = $('risultati-dove'), scheda = $('scheda-dove'),
      avvisi = $('avvisi-dove'), modulo = $('modulo-dove'), sede = $('sede-dove');
  if (!risultati) { return; }            // manca ancora il database delle prestazioni
  var paziente = pagina.getAttribute('data-paziente') || '';
  var struttura = pagina.getAttribute('data-struttura') || '';
  var numero = 0, numeroScheda = 0, attesa = null, apertoDa = null, segnato = null;

  function testo(el, t) { el.textContent = t; return el; }

  function crea(tag, classe, t) {
    var el = document.createElement(tag);
    if (classe) { el.className = classe; }
    if (t !== undefined) { el.textContent = t; }
    return el;
  }

  /* ------------------------------------------------ indirizzi */
  function parametri(extra) {
    var p = [], valori = {
      q: campo ? campo.value.trim() : '', branca: branca ? branca.value : '', sede: sede ? sede.value : '',
      paziente: paziente, struttura: struttura
    };
    Object.keys(extra || {}).forEach(function (k) { valori[k] = extra[k]; });
    Object.keys(valori).forEach(function (k) {
      if (valori[k]) { p.push(k + '=' + encodeURIComponent(valori[k])); }
    });
    return p.join('&');
  }

  function con(base, extra) {
    var qs = parametri(extra);
    return qs ? base + (base.indexOf('?') >= 0 ? '&' : '?') + qs : base;
  }

  // l'indirizzo della pagina segue la ricerca e la scheda aperta: ricaricando si ritrova tutto
  function ricordaIndirizzo(extra) {
    if (!window.history || !history.replaceState) { return; }
    try { history.replaceState(null, '', con(pagina.getAttribute('data-pagina'), extra)); } catch (e) { /* pazienza */ }
  }

  function schedaAperta() {
    var dentro = scheda && !scheda.hidden ? scheda.querySelector('.dentro-scheda') : null;
    return dentro ? { gruppo: dentro.getAttribute('data-gruppo'), voce: dentro.getAttribute('data-voce') } : null;
  }

  /* ------------------------------------------------ ricerca */
  function carica() {
    var n = ++numero;
    risultati.setAttribute('aria-busy', 'true');
    fetch(con(pagina.getAttribute('data-risultati')), { headers: { 'X-Richiesta': 'dove' } })
      .then(function (r) { if (!r.ok) { throw new Error(r.status); } return r.text(); })
      .then(function (html) {
        if (n !== numero) { return; }      // nel frattempo si e' scritto ancora: vale l'ultima
        risultati.innerHTML = html;
        risultati.setAttribute('aria-busy', 'false');
        segnaScelta();
        ricordaIndirizzo(schedaAperta());
        if (allaPrima) {
          allaPrima = false;
          var primo = voci()[0];
          if (primo) { primo.focus(); }
        }
      })
      .catch(function () {
        if (n !== numero) { return; }
        risultati.setAttribute('aria-busy', 'false');
        avviso('La ricerca non ha risposto: riprovare tra poco.', 'errore');
      });
  }

  function cerca(subito) {
    clearTimeout(attesa);
    attesa = setTimeout(function () { attesa = null; carica(); }, subito ? 0 : 170);
  }

  if (campo) {
    campo.addEventListener('input', function () { chiudiScheda(false); cerca(false); });
    campo.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') {
        var primo = voci()[0];
        if (primo) { e.preventDefault(); primo.focus(); }
      } else if (e.key === 'Escape' && campo.value) {
        e.preventDefault();
        campo.value = '';
        chiudiScheda(false);
        cerca(true);
      }
    });
  }
  if (branca) { branca.addEventListener('change', function () { chiudiScheda(false); cerca(true); }); }
  // Invio nel campo: i risultati arrivano gia' mentre si scrive, quindi si va alla prima
  // struttura (un altro Invio apre la sua scheda)
  var allaPrima = false;
  if (modulo) {
    modulo.addEventListener('submit', function (e) {
      e.preventDefault();
      if (attesa !== null || risultati.getAttribute('aria-busy') === 'true') { allaPrima = true; cerca(true); return; }
      var primo = voci()[0];
      if (primo) { primo.focus(); }
    });
  }

  /* frecce fra le strutture dei risultati (e su, dalla prima, di nuovo nel campo) */
  function voci() {
    return Array.prototype.slice.call(risultati.querySelectorAll('a.sede, a[data-branca], a.sede-grande, .nostri-dove a'));
  }
  risultati.addEventListener('keydown', function (e) {
    var tasti = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 };
    if (!tasti[e.key]) { return; }
    var lista = voci(), i = lista.indexOf(document.activeElement);
    if (i < 0) { return; }
    e.preventDefault();
    var j = i + tasti[e.key];
    if (j < 0) { if (campo) { campo.focus(); } return; }
    if (j < lista.length) { lista[j].focus(); }
  });

  /* ------------------------------------------------ la scheda della struttura */
  function segnaScelta() {
    var aperta = schedaAperta();
    risultati.querySelectorAll('a.scelta').forEach(function (a) { a.classList.remove('scelta'); });
    if (!aperta) { return; }
    risultati.querySelectorAll('a[data-gruppo="' + aperta.gruppo + '"]').forEach(function (a) {
      if ((a.getAttribute('data-voce') || '') === (aperta.voce || '')) { a.classList.add('scelta'); }
    });
  }

  function apriScheda(gruppo, voce, da) {
    var n = ++numeroScheda;
    apertoDa = da || null;
    var base = pagina.getAttribute('data-scheda').replace(/\/0$/, '/' + gruppo);
    fetch(con(base, { voce: voce || '' }), { headers: { 'X-Richiesta': 'dove' } })
      .then(function (r) { if (!r.ok) { throw new Error(r.status); } return r.text(); })
      .then(function (html) {
        if (n !== numeroScheda) { return; }
        scheda.innerHTML = html;
        scheda.hidden = false;
        document.body.classList.add('scheda-dove-aperta');
        posizionaScheda();
        segnato = null;
        preparaScheda();
        segnaScelta();
        ricordaIndirizzo({ voce: voce || '', gruppo: gruppo });
        scheda.scrollTop = 0;
        scheda.focus({ preventScroll: true });
      })
      .catch(function () { avviso('La scheda della struttura non si apre: ricaricare la pagina.', 'errore'); });
  }

  function chiudiScheda(tornaIndietro) {
    if (!scheda || scheda.hidden) { return; }
    numeroScheda++;
    scheda.hidden = true;
    scheda.textContent = '';
    document.body.classList.remove('scheda-dove-aperta');
    segnato = null;
    segnaScelta();
    ricordaIndirizzo();
    if (tornaIndietro !== false && apertoDa && document.body.contains(apertoDa)) { apertoDa.focus(); }
    apertoDa = null;
  }

  // la scheda comincia sotto il menu; scorrendo la pagina sale fino in cima
  var menu = document.querySelector('.menu');
  function posizionaScheda() {
    if (!scheda || scheda.hidden) { return; }
    var sotto = menu ? Math.max(0, Math.round(menu.getBoundingClientRect().bottom)) : 0;
    scheda.style.top = sotto + 'px';
  }
  window.addEventListener('scroll', posizionaScheda, { passive: true });
  window.addEventListener('resize', posizionaScheda);

  // il testo del messaggio si puo' cambiare: WhatsApp ed email mandano quello scritto
  function preparaScheda() {
    var area = $('messaggio-dove');
    if (!area) { return; }
    area.addEventListener('input', function () {
      scheda.querySelectorAll('a[data-base]').forEach(function (a) {
        a.href = a.getAttribute('data-base') + encodeURIComponent(area.value);
      });
    });
  }
  if (scheda && !scheda.hidden) { preparaScheda(); segnaScelta(); posizionaScheda(); }

  // la guida sullo schermo parla anche della scheda: se non e' aperta, si apre quella della prima struttura
  if (/[?&]guida=dove-si-fa(&|$)/.test(location.search) && scheda && scheda.hidden) {
    var primaSede = risultati.querySelector('a.sede');
    if (primaSede) { apriScheda(primaSede.getAttribute('data-gruppo'), primaSede.getAttribute('data-voce') || '', primaSede); }
  }

  // arrivati dalla ricerca rapida del menu con una prestazione: quella in vista
  var evidenziata = risultati.querySelector('.voce-dove.evidenziata');
  if (evidenziata && (!scheda || scheda.hidden)) {
    evidenziata.scrollIntoView({ block: 'center' });
    var prima = evidenziata.querySelector('a.sede');
    if (prima) { prima.focus({ preventScroll: true }); }
  }

  /* ------------------------------------------------ copia */
  function copia(t, fatto) {
    var riuscito = function () { if (fatto) { fatto(); } };
    var vecchio = function () {
      var a = crea('textarea');
      a.value = t;
      a.setAttribute('readonly', '');
      a.style.position = 'fixed';
      a.style.opacity = '0';
      document.body.appendChild(a);
      a.select();
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      document.body.removeChild(a);
      if (ok) { riuscito(); } else { avviso('Non si è potuto copiare: selezionare il testo e premere Ctrl+C.', 'errore'); }
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(t).then(riuscito, vecchio);
    } else {
      vecchio();
    }
  }

  /* ------------------------------------------------ avvisi in basso, con Annulla */
  function avviso(parole, livello, azione) {
    if (!avvisi) { return; }
    var el = crea('div', 'avviso-turni' + (livello ? ' livello-' + livello : ''));
    el.setAttribute('role', livello === 'errore' ? 'alert' : 'status');
    var corpo = crea('div', 'parole-avviso');
    corpo.appendChild(crea('p', '', parole));
    el.appendChild(corpo);
    if (azione) {
      var b = crea('button', 'azione-avviso', azione.testo);
      b.type = 'button';
      b.addEventListener('click', function () { togli(); azione.fai(); });
      el.appendChild(b);
    }
    var x = crea('button', 'chiudi-avviso', '×');
    x.type = 'button';
    x.setAttribute('aria-label', 'Chiudi');
    el.appendChild(x);
    var timer = null;
    function togli() { clearTimeout(timer); if (el.parentNode) { el.parentNode.removeChild(el); } }
    function piu_tardi() { clearTimeout(timer); timer = setTimeout(togli, azione ? 9000 : 5000); }
    x.addEventListener('click', togli);
    el.addEventListener('mouseenter', function () { clearTimeout(timer); });
    el.addEventListener('mouseleave', piu_tardi);
    // al massimo tre avvisi: i piu' vecchi se ne vanno
    while (avvisi.children.length >= 3) { avvisi.removeChild(avvisi.firstChild); }
    avvisi.appendChild(el);
    piu_tardi();
    return el;
  }

  /* ------------------------------------------------ registro dei pazienti indirizzati */
  function invia(url, dati) {
    return fetch(url, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Richiesta': 'dove' },
      body: JSON.stringify(dati || {})
    }).then(function (r) {
      return r.json().then(function (d) { if (!r.ok) { throw new Error(d.errore || r.status); } return d; });
    });
  }

  function segna(canale) {
    var dentro = scheda.querySelector('.dentro-scheda');
    if (!dentro) { return; }
    if (segnato) {
      avviso('Già segnato nel registro.', 'avviso');
      return;
    }
    segnato = { attesa: true };
    invia(pagina.getAttribute('data-indirizza'), {
      gruppo: dentro.getAttribute('data-gruppo'), voce: dentro.getAttribute('data-voce'),
      paziente: dentro.getAttribute('data-paziente'), canale: canale
    }).then(function (d) {
      segnato = d;
      avviso('Segnato: ' + d.testo, '', {
        testo: 'Annulla',
        fai: function () {
          invia(d.togli).then(function () {
            if (segnato && segnato.id === d.id) { segnato = null; }
            avviso('Tolto dal registro.');
          }).catch(function () { avviso('Non si è potuto togliere: provare dal registro.', 'errore'); });
        }
      });
    }).catch(function (e) {
      segnato = null;
      avviso('Non segnato nel registro: ' + (e && e.message ? e.message : 'riprovare') + '.', 'errore');
    });
  }

  /* ------------------------------------------------ clic */
  document.addEventListener('click', function (e) {
    if (e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) { return; }
    var t = e.target.closest ? e.target.closest('a, button') : null;
    if (!t) { return; }
    if ((t.hasAttribute('data-branca') || t.hasAttribute('data-sede')) && risultati.contains(t)) {
      // una branca dall'elenco, «tutte le branche», «tutte le strutture»
      e.preventDefault();
      if (branca && t.hasAttribute('data-branca')) { branca.value = t.getAttribute('data-branca'); }
      if (sede && t.hasAttribute('data-sede')) { sede.value = t.getAttribute('data-sede'); }
      chiudiScheda(false);
      cerca(true);
      if (campo) { campo.focus(); }
      return;
    }
    if (t.hasAttribute('data-gruppo') && risultati.contains(t)) {
      e.preventDefault();
      apriScheda(t.getAttribute('data-gruppo'), t.getAttribute('data-voce') || '', t);
      return;
    }
    if (!scheda || !scheda.contains(t)) { return; }
    if (t.hasAttribute('data-chiudi')) { e.preventDefault(); chiudiScheda(); return; }
    if (t.hasAttribute('data-branca-scheda') && branca && campo) {
      // cosa si fa in questa struttura: le sue prestazioni, di una branca o tutte
      e.preventDefault();
      branca.value = t.getAttribute('data-branca-scheda');
      if (sede) { sede.value = t.getAttribute('data-sede') || ''; }
      campo.value = '';
      chiudiScheda(false);
      cerca(true);
      campo.focus();
      return;
    }
    if (t.hasAttribute('data-copia')) {
      e.preventDefault();
      copia(t.getAttribute('data-copia'), function () { avviso('Copiato: ' + t.getAttribute('data-copia')); });
      return;
    }
    var azione = t.getAttribute('data-azione');
    if (azione === 'copia') {
      var area = $('messaggio-dove');
      copia(area ? area.value : '', function () {
        avviso('Messaggio copiato: si incolla con Ctrl+V.', '', segnato ? null : {
          testo: 'Segna come indirizzato', fai: function () { segna(($('canale-dove') || {}).value || 'telefono'); }
        });
      });
    } else if (azione === 'segna') {
      segna(($('canale-dove') || {}).value || 'telefono');
    } else if (azione === 'whatsapp' || azione === 'email' || azione === 'stampa') {
      // il collegamento si apre come sempre; intanto si segna nel registro
      segna(azione);
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && scheda && !scheda.hidden && !e.defaultPrevented) {
      e.preventDefault();
      chiudiScheda();
    }
  });

  /* ------------------------------------------------ per quale paziente */
  var cercaPaziente = $('paziente-dove'), box = $('suggerimenti-paziente-dove');
  if (cercaPaziente && box) {
    var attesaPaziente = null, proposte = [], scelta = -1, numeroPaziente = 0;
    var chiudi = function () { box.hidden = true; box.textContent = ''; proposte = []; scelta = -1; };
    var evidenzia = function (i) {
      proposte.forEach(function (b, k) { b.classList.toggle('attiva', k === i); });
      scelta = i;
    };
    var scegli = function (p) {
      paziente = String(p.id);
      window.location.href = con(pagina.getAttribute('data-pagina'), schedaAperta() || {});
    };
    var disegna = function (lista) {
      box.textContent = '';
      proposte = [];
      lista.forEach(function (p) {
        var b = crea('button', 'suggerimento');
        b.type = 'button';
        b.appendChild(testo(crea('b'), (p.cognome + ' ' + p.nome).trim()));
        var dettagli = [p.nascita ? 'nato il ' + p.nascita : '', p.telefono].filter(function (x) { return x; });
        if (dettagli.length) { b.appendChild(crea('span', '', ' ' + dettagli.join(' · '))); }
        b.addEventListener('mousedown', function (ev) { ev.preventDefault(); scegli(p); });
        box.appendChild(b);
        proposte.push(b);
      });
      if (!proposte.length) { box.appendChild(crea('div', 'nessuno', 'Nessun paziente con questo nome.')); }
      box.hidden = false;
      evidenzia(proposte.length ? 0 : -1);
    };
    cercaPaziente.addEventListener('input', function () {
      clearTimeout(attesaPaziente);
      var t = cercaPaziente.value.trim();
      if (t.length < 2) { chiudi(); return; }
      attesaPaziente = setTimeout(function () {
        var n = ++numeroPaziente, base = pagina.getAttribute('data-pazienti');
        fetch(base + (base.indexOf('?') >= 0 ? '&' : '?') + 'q=' + encodeURIComponent(t))
          .then(function (r) { return r.ok ? r.json() : []; })
          .then(function (lista) { if (n === numeroPaziente) { disegna(lista); } })
          .catch(chiudi);
      }, 160);
    });
    cercaPaziente.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { chiudi(); return; }
      if (box.hidden || !proposte.length) { return; }
      if (e.key === 'ArrowDown') { e.preventDefault(); evidenzia(Math.min(scelta + 1, proposte.length - 1)); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); evidenzia(Math.max(scelta - 1, 0)); }
      else if (e.key === 'Enter' && scelta >= 0) {
        e.preventDefault();
        proposte[scelta].dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
      }
    });
    cercaPaziente.addEventListener('blur', function () { setTimeout(chiudi, 150); });
  }
})();
