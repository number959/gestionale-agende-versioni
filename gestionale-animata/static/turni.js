/* Turni del personale (le pagine sotto /personale).

   - La griglia del mese e della settimana si usa come un foglio di calcolo: un
     clic su una cella apre la scelta del turno; trascinando, con Maiusc+clic o
     Maiusc+frecce si scelgono piu' celle, con Ctrl+clic una cella in piu'. Da
     tastiera basta scrivere il codice (M, P, N, SN...): si passa da solo al
     giorno dopo. Canc toglie, Invio apre la scelta, Ctrl+Z annulla, Ctrl+Y rifa'.
   - Nella vista del giorno la stessa scelta si apre sulla riga della persona.
   - Lo schema a rotazione mostra, prima di applicarlo, come verranno i turni.
   - Nelle pagine dei tipi di turno e delle persone, i campi che servono.

   Le regole (sovrapposizioni, riposi, coperture) le controlla il programma: qui
   si manda la richiesta e si ridisegna quello che risponde. Le richieste passano
   da una coda, una alla volta, cosi' le risposte arrivano nell'ordine giusto. */
(function () {
  'use strict';

  var $ = function (id) { return document.getElementById(id); };
  var MESI = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto', 'settembre',
              'ottobre', 'novembre', 'dicembre'];
  var GIORNI = ['dom', 'lun', 'mar', 'mer', 'gio', 'ven', 'sab'];
  var INIZIALI = ['D', 'L', 'M', 'M', 'G', 'V', 'S'];
  var MOLTE = 8;          // celle gia' piene oltre le quali si chiede conferma prima di sostituirle o svuotarle
  var MEMORIA = 50;       // modifiche che si possono annullare

  var TIPI = [];
  try { TIPI = JSON.parse(($('tipi-turno') || {}).textContent || '[]'); } catch (e) { TIPI = []; }
  var PER_CODICE = {};
  var PER_ID = {};
  TIPI.forEach(function (t) { PER_CODICE[t.codice] = t; PER_ID[String(t.id)] = t; });

  /* ------------------------------------------------------------ piccoli aiuti */
  function nuovo(tag, classe, testo) {
    var x = document.createElement(tag);
    if (classe) { x.className = classe; }
    if (testo !== undefined && testo !== null) { x.textContent = String(testo); }
    return x;
  }
  function elenco(lista) { return Array.prototype.slice.call(lista); }
  function dataDi(iso) { var p = String(iso).split('-'); return new Date(+p[0], +p[1] - 1, +p[2]); }
  function isoDi(d) {
    return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);
  }
  function giornoScritto(iso) { var d = dataDi(iso); return GIORNI[d.getDay()] + ' ' + d.getDate() + ' ' + MESI[d.getMonth()]; }
  function giornoBreve(iso) { var d = dataDi(iso); return d.getDate() + '/' + (d.getMonth() + 1); }
  function giorniTra(a, b) { return Math.round((dataDi(b) - dataDi(a)) / 86400000); }
  function oraBreve(hhmm) {
    var p = String(hhmm).split(':');
    var h = +p[0], m = +p[1] || 0;
    return m ? h + ':' + ('0' + m).slice(-2) : String(h);
  }
  function maiuscola(t) { return t ? t.charAt(0).toUpperCase() + t.slice(1) : t; }
  function testoDi(x) { return x ? x.textContent.replace(/\s+/g, ' ').trim() : ''; }
  function staScrivendo(x) {
    if (!x) { return false; }
    var tag = x.tagName;
    return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || x.isContentEditable;
  }
  function luminanza(hex) {
    var c = [1, 3, 5].map(function (i) {
      var v = parseInt(hex.substr(i, 2), 16) / 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  }
  // lo stesso conto di modelli.testo_su: il blu scuro del programma o il bianco, quello che si legge meglio
  function testoSu(hex) {
    if (!/^#[0-9A-Fa-f]{6}$/.test(hex || '')) { hex = '#E8E8EC'; }
    var L = luminanza(hex);
    return (L + 0.05) / (luminanza('#16263F') + 0.05) >= 1.05 / (L + 0.05) ? '#16263F' : '#FFFFFF';
  }

  // il disegno di un turno in una cella: lo stesso della macro contenuto() di _personale_cella.html
  function chipCella(v, larga, doppio) {
    var classi = 'turno';
    if (v.categoria === 'ASSENZA' || v.categoria === 'RIPOSO') { classi += ' senza-orario'; }
    if (v.categoria === 'REPERIBILITA') { classi += ' reperibile'; }
    if (!v.codice) { classi += ' a-mano'; }
    if (v.diverso) { classi += ' diverso'; }
    if (doppio) { classi += ' doppio'; }
    var s = nuovo('span', classi);
    s.style.setProperty('--c', v.colore);
    s.style.setProperty('--t', v.testo);
    if (v.id) { s.setAttribute('data-id', v.id); }
    if (v.desc) { s.setAttribute('data-desc', v.desc); }
    if (v.area) { s.setAttribute('data-area', v.area); }
    var b = nuovo('b');
    if (v.codice || larga) {
      b.textContent = v.codice || v.orario;
    } else {
      // un orario scritto a mano, nella cella stretta del mese: su due righe (con due turni, solo l'inizio)
      var o = String(v.orario || '').split('–');
      if (doppio) { b.textContent = o[0]; } else {
        b.className = 'orario-stretto';
        b.appendChild(nuovo('span', null, o[0]));
        b.appendChild(nuovo('span', null, o[1] || ''));
      }
    }
    s.appendChild(b);
    if (larga && v.orario && v.codice) { s.appendChild(nuovo('small', 'ore-turno', v.orario)); }
    if (larga && v.area) { s.appendChild(nuovo('small', 'area-turno', v.area)); }
    return s;
  }

  /* ------------------------------------------------------------ avvisi in basso
     Uno solo alla volta per le modifiche riuscite (con «Annulla»): il nuovo
     prende il posto del vecchio. Errori e avvisi si aggiungono, al piu' quattro. */
  var scatola = null;
  var avvisoFatto = null;
  function avvisa(righe, livello, azione) {
    righe = [].concat(righe || []).filter(function (r) { return !!r; });
    if (!righe.length) { return null; }
    livello = livello || 'ok';
    if (!scatola) {
      scatola = nuovo('div', 'avvisi-turni');
      scatola.setAttribute('aria-live', 'polite');
      document.body.appendChild(scatola);
    }
    var a = nuovo('div', 'avviso-turni livello-' + livello);
    if (livello === 'errore') { a.setAttribute('role', 'alert'); }
    var testo = nuovo('div', 'parole-avviso');
    righe.slice(0, 6).forEach(function (r) { testo.appendChild(nuovo('p', null, r)); });
    a.appendChild(testo);
    var timer = null;
    var via = function () {
      clearTimeout(timer);
      if (a.parentNode) { a.parentNode.removeChild(a); }
      if (avvisoFatto === a) { avvisoFatto = null; }
    };
    if (azione) {
      var b = nuovo('button', 'azione-avviso', azione.etichetta);
      b.type = 'button';
      b.addEventListener('click', function () { via(); azione.fai(); });
      a.appendChild(b);
    }
    var x = nuovo('button', 'chiudi-avviso', '×');
    x.type = 'button';
    x.setAttribute('aria-label', 'Chiudi');
    x.addEventListener('click', via);
    a.appendChild(x);
    if (livello === 'ok') {
      if (avvisoFatto && avvisoFatto.parentNode) { avvisoFatto.parentNode.removeChild(avvisoFatto); }
      avvisoFatto = a;
    }
    scatola.appendChild(a);
    while (scatola.children.length > 4) { scatola.removeChild(scatola.firstChild); }
    var durata = livello === 'errore' ? 12000 : livello === 'avviso' ? 10000 : 7000;
    var parti = function (ms) { clearTimeout(timer); timer = setTimeout(via, ms); };
    parti(durata);
    a.addEventListener('mouseenter', function () { clearTimeout(timer); });
    a.addEventListener('mouseleave', function () { parti(4000); });
    a.addEventListener('focusin', function () { clearTimeout(timer); });
    a.addEventListener('focusout', function () { parti(4000); });
    return a;
  }

  /* ------------------------------------------------------------ richieste, in coda */
  var coda = Promise.resolve();
  var inCorso = 0;
  function accoda(lavoro) {
    inCorso++;
    coda = coda.then(lavoro).catch(function () { /* l'errore l'ha gia' detto il lavoro */ })
      .then(function () { inCorso--; });
    return coda;
  }
  window.addEventListener('beforeunload', function (e) {
    if (inCorso > 0) { e.preventDefault(); e.returnValue = ''; }
  });
  function manda(indirizzo, struttura, corpo) {
    var url = indirizzo + (struttura ? (indirizzo.indexOf('?') < 0 ? '?' : '&') + 'struttura=' +
                           encodeURIComponent(struttura) : '');
    var testo = JSON.stringify(corpo);
    return fetch(url, {
      method: 'POST', credentials: 'same-origin', keepalive: testo.length < 60000,
      headers: { 'Content-Type': 'application/json', 'X-Richiesta': 'turni' }, body: testo
    }).then(function (r) {
      return r.json().then(function (d) { return { stato: r.status, d: d }; },
                           function () { return { stato: r.status, d: null }; });
    });
  }
  var NON_RISPONDE = 'Non salvato: il programma non risponde. Riprovare tra poco.';

  /* ------------------------------------------------------------ codice scritto da tastiera
     Si aspetta un attimo solo se il codice potrebbe continuare (M e MA):
     altrimenti vale subito. Invio lo conferma, Esc lo lascia perdere. */
  function nuovoBuffer(mostra, applica) {
    var testo = '';
    var timer = null;
    var sconosciuto = function (s) {
      avvisa('Nessun turno ha il codice «' + s + '»: i codici sono nella legenda sopra la griglia.', 'errore');
    };
    var conferma = function () {
      clearTimeout(timer);
      var t = PER_CODICE[testo];
      var scritto = testo;
      testo = '';
      mostra('');
      if (t) { applica(t); } else if (scritto) { sconosciuto(scritto); }
    };
    return {
      scrivi: function (car) {
        testo += car.toUpperCase();
        clearTimeout(timer);
        var esatto = !!PER_CODICE[testo];
        var continua = TIPI.some(function (t) { return t.codice.length > testo.length && t.codice.indexOf(testo) === 0; });
        if (!esatto && !continua) { var s = testo; testo = ''; mostra(''); sconosciuto(s); return; }
        if (esatto && !continua) { conferma(); return; }
        mostra(testo);
        timer = setTimeout(conferma, 800);
      },
      conferma: conferma,
      attivo: function () { return testo !== ''; },
      annulla: function () { clearTimeout(timer); testo = ''; mostra(''); }
    };
  }

  /* ------------------------------------------------------------ la scelta del turno */
  var Scelta = (function () {
    var pop = $('scelta-turno');
    if (!pop) { return null; }
    document.body.appendChild(pop);   // fuori da ogni contenitore che scorre
    var bottoni = elenco(pop.querySelectorAll('.scelta-tipo'));
    var attuali = $('scelta-attuali');
    var errore = $('scelta-errore');
    var altro = $('scelta-altro');
    var togliTutto = $('scelta-togli');
    var campo = { inizio: $('scelta-inizio'), fine: $('scelta-fine'), area: $('scelta-area'), nota: $('scelta-nota'),
                  aggiungi: $('scelta-aggiungi') };
    var iconaX = pop.querySelector('.scelta-chiudi .icona');
    var corrente = null;

    var mostraErrore = function (t) { errore.textContent = t || ''; errore.hidden = !t; };
    var orari = function () {
      var a = campo.inizio.value;
      var b = campo.fine.value;
      if (!a && !b) { return {}; }
      if (!a || !b) { return { errore: 'Scrivere sia l\'inizio sia la fine (oppure nessuno dei due).' }; }
      if (a === b) { return { errore: 'Inizio e fine sono uguali.' }; }
      return { inizio: a, fine: b };
    };
    var dettagli = function (dati) {
      dati.area = campo.area.value.trim();
      dati.note = campo.nota.value.trim();
      if (!dati.area && corrente.tieniArea && dati.azione === 'metti') { dati.tieni_area = true; }
      return dati;
    };
    var scegli = function (dati) {
      if (!corrente) { return; }
      var c = corrente;
      chiudi(true);
      c.quando(dati);
    };
    var scegliTipo = function (t) {
      var o = orari();
      if (o.errore) { altro.open = true; mostraErrore(o.errore); return; }
      var dati = dettagli({ azione: campo.aggiungi.checked ? 'aggiungi' : 'metti', tipo: t.id, descrizione: t.nome });
      if (o.inizio && t.inizio) {
        dati.inizio = o.inizio;
        dati.fine = o.fine;
        dati.descrizione = t.nome + ' ' + oraBreve(o.inizio) + '–' + oraBreve(o.fine);
      }
      scegli(dati);
    };
    var buffer = nuovoBuffer(function () {}, scegliTipo);

    bottoni.forEach(function (b) {
      b.addEventListener('click', function () {
        var t = PER_ID[b.getAttribute('data-tipo')];
        if (t) { scegliTipo(t); }
      });
    });
    $('scelta-metti-orario').addEventListener('click', function () {
      var o = orari();
      if (!o.inizio) {
        mostraErrore(o.errore || 'Scrivere l\'inizio e la fine del turno.');
        (campo.inizio.value ? campo.fine : campo.inizio).focus();
        return;
      }
      scegli(dettagli({ azione: campo.aggiungi.checked ? 'aggiungi' : 'metti', inizio: o.inizio, fine: o.fine,
                        descrizione: 'orario ' + oraBreve(o.inizio) + '–' + oraBreve(o.fine) }));
    });
    togliTutto.addEventListener('click', function () { scegli({ azione: 'togli' }); });
    pop.querySelector('.scelta-chiudi').addEventListener('click', function () { chiudi(true); });

    pop.addEventListener('keydown', function (e) {
      e.stopPropagation();   // i tasti della scelta non vanno ai tasti rapidi della pagina
      if (e.key === 'Escape') { e.preventDefault(); chiudi(true); return; }
      if (staScrivendo(e.target) || e.ctrlKey || e.metaKey || e.altKey) { return; }
      var i = bottoni.indexOf(e.target);
      var passo = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: 2, ArrowUp: -2 }[e.key];
      if (i >= 0 && passo) {
        e.preventDefault();
        bottoni[Math.max(0, Math.min(bottoni.length - 1, i + passo))].focus();
        return;
      }
      if (e.key === 'Delete' || e.key === 'Backspace') {
        e.preventDefault();
        if (!togliTutto.disabled) { scegli({ azione: 'togli' }); }
        return;
      }
      if (e.key === 'Enter' && buffer.attivo()) { e.preventDefault(); buffer.conferma(); return; }
      if (e.key.length === 1 && /[A-Za-z0-9]/.test(e.key)) { e.preventDefault(); buffer.scrivi(e.key); }
    });

    // un clic fuori la chiude (un clic su un'altra cella invece la sposta: ci pensa chi l'ha aperta)
    document.addEventListener('mousedown', function (e) {
      if (!corrente || pop.contains(e.target)) { return; }
      if (corrente.ignora && corrente.ignora(e.target)) { return; }
      chiudi(false);
    }, true);

    var posiziona = function () {
      if (!corrente) { return; }
      var r = corrente.rettangolo ? corrente.rettangolo() : corrente.ancora.getBoundingClientRect();
      var vw = document.documentElement.clientWidth;
      var vh = document.documentElement.clientHeight;
      var w = pop.offsetWidth;
      var h = pop.offsetHeight;
      var spazio = 6;
      var x = Math.min(Math.max(8, r.left), vw - w - 8);
      var y;
      if (r.bottom + spazio + h <= vh - 8) { y = r.bottom + spazio; }
      else if (r.top - spazio - h >= 8) { y = r.top - spazio - h; }
      else {
        y = Math.min(vh - h - 8, r.top);
        if (r.right + spazio + w <= vw - 8) { x = r.right + spazio; }
        else if (r.left - spazio - w >= 8) { x = r.left - spazio - w; }
      }
      pop.style.left = Math.round(Math.max(8, x)) + 'px';
      pop.style.top = Math.round(Math.max(8, y)) + 'px';
    };
    var inAttesa = false;
    var riposiziona = function () {
      if (!corrente || inAttesa) { return; }
      inAttesa = true;
      window.requestAnimationFrame(function () { inAttesa = false; posiziona(); });
    };
    window.addEventListener('resize', riposiziona);
    document.addEventListener('scroll', riposiziona, true);

    function chiudi(restituisci) {
      if (!corrente) { return; }
      var c = corrente;
      corrente = null;
      buffer.annulla();
      pop.hidden = true;
      pop.classList.remove('aperta');
      if (c.chiusa) { c.chiusa(restituisci || pop.contains(document.activeElement)); }
    }

    /* o: titolo, sotto, attuali [{id, desc, codice, colore, testo}], area, pieno,
       tieniArea, ancora (elemento), rettangolo (funzione, facoltativa),
       daTastiera, ignora(elemento), quando(dati), chiusa(restituisci) */
    function apri(o) {
      if (corrente && corrente !== o && corrente.chiusa) { corrente.chiusa(false); }
      corrente = o;
      buffer.annulla();
      $('scelta-titolo').textContent = o.titolo || 'Turno';
      $('scelta-sotto').textContent = o.sotto || '';
      attuali.textContent = '';
      var lista = o.attuali || [];
      lista.forEach(function (v) {
        var riga = nuovo('span', 'attuale');
        var c = nuovo('span', 'turno' + (v.codice ? '' : ' a-mano'));
        c.style.setProperty('--c', v.colore || '#F1F3F4');
        c.style.setProperty('--t', v.testo || '#16263F');
        c.appendChild(nuovo('b', null, v.codice || '·'));
        riga.appendChild(c);
        riga.appendChild(nuovo('span', 'desc-attuale', v.desc));
        var x = nuovo('button');
        x.type = 'button';
        x.title = 'Togli questo turno';
        x.setAttribute('aria-label', 'Togli: ' + v.desc);
        if (iconaX) { x.appendChild(iconaX.cloneNode(true)); } else { x.textContent = '×'; }
        x.addEventListener('click', function () { scegli({ azione: 'togli', turno: v.id, descrizione: v.desc }); });
        riga.appendChild(x);
        attuali.appendChild(riga);
      });
      attuali.hidden = !lista.length;
      var codici = lista.map(function (v) { return v.codice; });
      bottoni.forEach(function (b) {
        var si = codici.indexOf(b.getAttribute('data-codice')) >= 0;
        b.classList.toggle('attuale-tipo', si);
        b.setAttribute('aria-pressed', si ? 'true' : 'false');
      });
      campo.inizio.value = '';
      campo.fine.value = '';
      campo.area.value = o.area || '';
      campo.nota.value = '';
      campo.aggiungi.checked = false;
      altro.open = false;
      mostraErrore('');
      togliTutto.disabled = !o.pieno;
      pop.hidden = false;
      pop.classList.remove('aperta');
      void pop.offsetWidth;            // per far ripartire l'animazione (nella versione animata)
      pop.classList.add('aperta');
      posiziona();
      if (o.daTastiera) {
        (pop.querySelector('.scelta-tipo.attuale-tipo') || bottoni[0] || togliTutto).focus({ preventScroll: true });
      }
    }

    return {
      apri: apri,
      chiudi: chiudi,
      aperta: function () { return corrente; },
      posiziona: posiziona
    };
  })();

  // i turni di una cella (o di una riga del giorno), letti dal disegno della pagina
  function turniDi(contenitore) {
    return elenco(contenitore.querySelectorAll('[data-id]')).map(function (x) {
      var b = x.querySelector('b');
      var codice = x.hasAttribute('data-codice') ? x.getAttribute('data-codice')
        : (x.classList.contains('a-mano') ? '' : testoDi(b));
      return { id: x.getAttribute('data-id'), desc: x.getAttribute('data-desc') || '', codice: codice,
               area: x.getAttribute('data-area') || '',
               colore: x.style.getPropertyValue('--c').trim(), testo: x.style.getPropertyValue('--t').trim() };
    });
  }
  function descrizioneDi(dati) {
    if (dati.azione === 'togli') { return dati.turno ? 'turno tolto' : 'turni tolti'; }
    return (dati.azione === 'aggiungi' ? 'aggiunto ' : '') + (dati.descrizione || 'turno');
  }
  function corpoDi(dati, base) {
    ['tipo', 'inizio', 'fine', 'area', 'note', 'turno', 'tieni_area'].forEach(function (x) {
      if (dati[x]) { base[x] = dati[x]; }
    });
    return base;
  }

  /* ------------------------------------------------------------ la griglia del mese e della settimana */
  var griglia = null;
  (function () {
    var tab = $('griglia-turni');
    if (!tab) { return; }
    var vista = tab.getAttribute('data-vista');
    var larga = vista === 'settimana';
    var indirizzo = tab.getAttribute('data-indirizzo');
    var struttura = tab.getAttribute('data-struttura') || '';
    var righe = elenco(tab.querySelectorAll('tr.riga-persona'));
    var M = [];
    var perChiave = {};
    var perPersona = {};
    var perCopertura = {};
    righe.forEach(function (tr, r) {
      perPersona[tr.getAttribute('data-persona')] = tr;
      var celle = elenco(tr.querySelectorAll('td.cella'));
      celle.forEach(function (td, c) { td._r = r; td._c = c; perChiave[td.getAttribute('data-k')] = td; });
      M.push(celle);
    });
    elenco(tab.querySelectorAll('td.cop')).forEach(function (td) { perCopertura[td.getAttribute('data-c')] = td; });
    if (!M.length || !M[0].length) { return; }
    tab.setAttribute('aria-multiselectable', 'true');

    var fuoco = null;
    var ancora = null;
    var scelte = [];
    var trascina = false;
    var pilaAnnulla = [];
    var pilaRifai = [];
    var chiave = function (td) { return td.getAttribute('data-k'); };
    var nomeDi = function (td) { return testoDi(td.parentNode.querySelector('th.nome-col a')); };

    // si entra nella griglia con Tab sulla cella di oggi (o sulla prima)
    var colonne = elenco(tab.querySelectorAll('thead th.giorno-col'));
    var oggi = colonne.map(function (th) { return th.classList.contains('oggi'); }).indexOf(true);
    (M[0][Math.max(0, oggi)] || M[0][0]).tabIndex = 0;

    function segna(nuove) {
      scelte.forEach(function (td) { td.classList.remove('scelta'); td.removeAttribute('aria-selected'); });
      scelte = nuove;
      scelte.forEach(function (td) { td.classList.add('scelta'); td.setAttribute('aria-selected', 'true'); });
    }
    function rettangolo(a, b) {
      var l = [];
      for (var r = Math.min(a._r, b._r); r <= Math.max(a._r, b._r); r++) {
        for (var c = Math.min(a._c, b._c); c <= Math.max(a._c, b._c); c++) {
          if (M[r] && M[r][c]) { l.push(M[r][c]); }
        }
      }
      return l;
    }
    // modo: 'solo' (solo questa cella), 'estendi' (dal punto di partenza a qui), 'aggiungi' (una in piu', o in meno)
    function vaiA(td, modo, senzaScorrere) {
      if (!td) { return; }
      if (modo === 'estendi' && ancora) {
        segna(rettangolo(ancora, td));
      } else if (modo === 'aggiungi') {
        var l = scelte.slice();
        var i = l.indexOf(td);
        if (i >= 0 && l.length > 1) { l.splice(i, 1); } else if (i < 0) { l.push(td); }
        segna(l);
        ancora = td;
      } else {
        segna([td]);
        ancora = td;
      }
      M.forEach(function (riga) { riga.forEach(function (x) { if (x.tabIndex !== -1 && x !== td) { x.tabIndex = -1; } }); });
      if (fuoco && fuoco !== td) { fuoco.classList.remove('fuoco'); }
      fuoco = td;
      td.classList.add('fuoco');
      td.tabIndex = 0;
      if (document.activeElement !== td) { td.focus({ preventScroll: true }); }
      if (!senzaScorrere) { td.scrollIntoView({ block: 'nearest', inline: 'nearest' }); }
    }

    var conCodice = null;
    var buffer = nuovoBuffer(function (t) {
      if (conCodice) { conCodice.removeAttribute('data-scrivendo'); }
      conCodice = t && fuoco ? fuoco : null;
      if (conCodice) { conCodice.setAttribute('data-scrivendo', t); }
    }, function (tipo) { mettiTipo(tipo, true); });

    function rettangoloScelte() {
      var l = scelte.length > 120 ? [scelte[0], scelte[scelte.length - 1], fuoco] : scelte;
      var r = { left: Infinity, top: Infinity, right: -Infinity, bottom: -Infinity };
      l.forEach(function (td) {
        var b = td.getBoundingClientRect();
        r.left = Math.min(r.left, b.left); r.top = Math.min(r.top, b.top);
        r.right = Math.max(r.right, b.right); r.bottom = Math.max(r.bottom, b.bottom);
      });
      var cont = tab.parentNode.getBoundingClientRect();     // la parte visibile della griglia
      r.left = Math.max(r.left, cont.left); r.right = Math.min(r.right, cont.right);
      r.top = Math.max(r.top, cont.top); r.bottom = Math.min(r.bottom, cont.bottom);
      if (r.bottom < r.top) { r.bottom = r.top; }
      if (r.right < r.left) { r.right = r.left; }
      return r;
    }

    function apriScelta(daTastiera) {
      if (!Scelta || !scelte.length) { return; }
      var una = scelte.length === 1 ? scelte[0] : null;
      var attuali = una ? turniDi(una) : [];
      var persone = {};
      var giorni = {};
      scelte.forEach(function (td) { var p = chiave(td).split('_'); persone[p[0]] = true; giorni[p[1]] = true; });
      var np = Object.keys(persone).length;
      var gs = Object.keys(giorni).sort();
      var quando = gs.length === 1 ? giornoScritto(gs[0]) : 'dal ' + giornoBreve(gs[0]) + ' al ' + giornoBreve(gs[gs.length - 1]);
      Scelta.apri({
        titolo: una ? nomeDi(una) : scelte.length + ' celle',
        sotto: una ? quando + (una.classList.contains('con-avviso') ? ' · riposo breve prima' : '')
          : (np === 1 ? nomeDi(scelte[0]) : np + ' persone') + ' · ' + quando,
        attuali: attuali,
        area: attuali.length === 1 ? attuali[0].area : '',
        pieno: scelte.some(function (td) { return !!td.querySelector('.turno'); }),
        tieniArea: scelte.length > 1,
        ancora: fuoco,
        rettangolo: rettangoloScelte,
        daTastiera: daTastiera,
        ignora: function (x) { return !!(x.closest && x.closest('#griglia-turni td.cella')); },
        quando: function (dati) { cambia(dati, scelte.slice()); },
        chiusa: function (restituisci) { if (restituisci && fuoco) { fuoco.focus({ preventScroll: true }); } }
      });
    }

    function mettiTipo(tipo, daTastiera) {
      var l = scelte.slice();
      if (!l.length) { return; }
      cambia({ azione: 'metti', tipo: tipo.id, tieni_area: true, descrizione: tipo.nome }, l);
      if (daTastiera && l.length === 1 && fuoco) {      // come in un foglio di calcolo: si passa al giorno dopo
        var dopo = M[fuoco._r][fuoco._c + 1];
        if (dopo) { vaiA(dopo, 'solo'); }
      }
    }

    function disegna(td, c) {
      td.textContent = '';
      c.turni.forEach(function (v) { td.appendChild(chipCella(v, larga, c.turni.length > 1)); });
      if (c.avviso) {
        var i = nuovo('i', 'segno-riposo');
        i.setAttribute('aria-hidden', 'true');
        td.appendChild(i);
      }
      td.classList.toggle('piena', c.turni.length > 0);
      td.classList.toggle('con-avviso', !!c.avviso);
      td.title = c.titolo;
      td.setAttribute('aria-label', c.titolo);
    }
    function lampeggia(td) {
      td.classList.remove('appena-cambiata');
      void td.offsetWidth;
      td.classList.add('appena-cambiata');
      setTimeout(function () { td.classList.remove('appena-cambiata'); }, 900);
    }
    function totali(tr, t) {
      var ore = tr.querySelector('td.tot[data-tot="ore"]');
      if (ore) {
        ore.textContent = '';
        ore.appendChild(nuovo('b', null, t.ore));
        if (t.previste) {
          ore.appendChild(nuovo('small', null, '/ ' + t.previste));
          if (vista === 'settimana' && t.segno) {
            ore.appendChild(nuovo('span', 'scarto ' + t.segno,
                                  t.segno === 'pari' ? '✓' : (t.segno === 'sopra' ? '+' : '') + t.differenza));
          }
        }
      }
      [['notti', t.notti], ['festivi', t.festivi], ['assenze', t.assenze]].forEach(function (x) {
        var td = tr.querySelector('td.tot[data-tot="' + x[0] + '"]');
        if (td) { td.textContent = x[1] ? String(x[1]) : ''; }
      });
      var ass = tr.querySelector('td.tot[data-tot="assenze"]');
      if (ass) { ass.title = t.dettaglio_assenze || ''; }
    }
    function copertura(td, c) {
      var manca = !!(c.carenze && c.carenze.length);
      td.textContent = '';
      td.classList.toggle('manca', manca);
      if (manca) {
        var i = nuovo('i', 'segno-manca');
        i.setAttribute('aria-hidden', 'true');
        td.appendChild(i);
      }
      (c.testo || '').split(' ').forEach(function (x) { if (x) { td.appendChild(nuovo('span', null, x)); } });
      td.title = manca ? 'Manca: ' + c.carenze.join('; ') : 'Al lavoro: ' + (c.testo || 'nessuno');
    }
    function applica(d, toccate) {
      Object.keys(d.celle || {}).forEach(function (k) {
        var td = perChiave[k];
        if (!td) { return; }
        disegna(td, d.celle[k]);
        if (toccate.indexOf(k) >= 0) { lampeggia(td); }
      });
      Object.keys(d.totali || {}).forEach(function (pid) { if (perPersona[pid]) { totali(perPersona[pid], d.totali[pid]); } });
      Object.keys(d.copertura || {}).forEach(function (k) { if (perCopertura[k]) { copertura(perCopertura[k], d.copertura[k]); } });
      if (Scelta && Scelta.aperta()) { Scelta.posiziona(); }
    }

    // mentre si aspetta la risposta la cella mostra gia' il turno scelto (un po' sbiadito)
    function anteprima(td, dati) {
      if (dati.azione === 'togli') {
        if (!dati.turno) { td.textContent = ''; return; }
        var x = td.querySelector('.turno[data-id="' + dati.turno + '"]');
        if (x) { x.parentNode.removeChild(x); }
        return;
      }
      var t = dati.tipo ? PER_ID[String(dati.tipo)] : null;
      var orario = dati.inizio ? oraBreve(dati.inizio) + '–' + oraBreve(dati.fine) : (t ? t.orario : '');
      var v = { codice: t ? t.codice : '', orario: orario, colore: t ? t.colore : '#F1F3F4', testo: t ? t.testo : '#16263F',
                categoria: t ? t.categoria : 'LAVORO', area: dati.area || '' };
      if (dati.azione === 'metti') { td.textContent = ''; }
      var doppio = !!td.querySelector('.turno');
      elenco(td.querySelectorAll('.turno')).forEach(function (x) { x.classList.add('doppio'); });
      td.appendChild(chipCella(v, larga, doppio));
    }

    function frase(dati, tds, fatti) {
      var cosa = descrizioneDi(dati);
      if (tds.length === 1) { return cosa + ' a ' + nomeDi(tds[0]) + ', ' + giornoScritto(chiave(tds[0]).split('_')[1]); }
      return cosa + ' in ' + fatti + (fatti === 1 ? ' cella' : ' celle');
    }

    function cambia(dati, tds) {
      tds = tds.filter(Boolean);
      if (!tds.length) { return; }
      var piene = tds.filter(function (td) { return !!td.querySelector('.turno'); }).length;
      if (dati.azione === 'togli' && !piene) { return; }
      var sostituisce = dati.azione === 'togli' && !dati.turno || dati.azione === 'metti';
      if (sostituisce && piene >= MOLTE && !window.confirm(
          (dati.azione === 'togli' ? 'Togliere i turni di ' : 'Sostituire i turni già messi in ') + piene +
          ' celle? (Ctrl+Z annulla)')) { return; }
      var copie = tds.map(function (td) {
        return { td: td, html: td.innerHTML, titolo: td.title, piena: td.classList.contains('piena'),
                 avviso: td.classList.contains('con-avviso') };
      });
      var ripristinaCopie = function () {
        copie.forEach(function (c) {
          c.td.innerHTML = c.html;
          c.td.title = c.titolo;
          c.td.setAttribute('aria-label', c.titolo);
          c.td.classList.toggle('piena', c.piena);
          c.td.classList.toggle('con-avviso', c.avviso);
        });
      };
      tds.forEach(function (td) { anteprima(td, dati); td.classList.add('in-attesa'); });
      var chiavi = tds.map(chiave);
      var corpo = corpoDi(dati, { azione: dati.azione, celle: chiavi, dal: tab.getAttribute('data-dal'),
                                  al: tab.getAttribute('data-al'), ruolo: tab.getAttribute('data-ruolo'),
                                  area_filtro: tab.getAttribute('data-area') });
      accoda(function () {
        return manda(indirizzo, struttura, corpo).then(function (esito) {
          tds.forEach(function (td) { td.classList.remove('in-attesa'); });
          var d = esito.d;
          if (!d || !d.celle) {
            ripristinaCopie();
            tds.forEach(function (td) { td.classList.add('sbagliata'); setTimeout(function () { td.classList.remove('sbagliata'); }, 1200); });
            avvisa((d && d.errore) || NON_RISPONDE, 'errore');
            return;
          }
          applica(d, chiavi);
          if (d.prima && Object.keys(d.prima).length) {
            var testo = frase(dati, tds, d.fatti);
            pilaAnnulla.push({ stato: d.prima, testo: testo });
            if (pilaAnnulla.length > MEMORIA) { pilaAnnulla.shift(); }
            pilaRifai = [];
            avvisa(maiuscola(testo) + '.', 'ok', { etichetta: 'Annulla', fai: annullaUltimo });
          }
          avvisa(d.errori, 'errore');
          avvisa(d.avvisi, 'avviso');
        }, function () {
          tds.forEach(function (td) { td.classList.remove('in-attesa'); });
          ripristinaCopie();
          avvisa(NON_RISPONDE, 'errore');
        });
      });
    }

    // annulla e rifai: le celle tornano come le ha descritte il programma prima della modifica
    function ripristina(voce, annullando) {
      var chiavi = Object.keys(voce.stato);
      var tds = chiavi.map(function (k) { return perChiave[k]; }).filter(Boolean);
      tds.forEach(function (td) { td.classList.add('in-attesa'); });
      accoda(function () {
        return manda(indirizzo, struttura, { azione: 'ripristina', stato: voce.stato, dal: tab.getAttribute('data-dal'),
                                              al: tab.getAttribute('data-al'), ruolo: tab.getAttribute('data-ruolo'),
                                              area_filtro: tab.getAttribute('data-area') }).then(function (esito) {
          tds.forEach(function (td) { td.classList.remove('in-attesa'); });
          var d = esito.d;
          if (!d || !d.celle) { avvisa((d && d.errore) || NON_RISPONDE, 'errore'); return; }
          applica(d, chiavi);
          if (d.errori && d.errori.length) { avvisa(d.errori, 'errore'); return; }
          (annullando ? pilaRifai : pilaAnnulla).push({ stato: d.prima, testo: voce.testo });
          avvisa((annullando ? 'Annullato: ' : 'Rifatto: ') + voce.testo + '.', 'ok',
                 annullando ? { etichetta: 'Rifai', fai: rifaiUltimo } : { etichetta: 'Annulla', fai: annullaUltimo });
        }, function () {
          tds.forEach(function (td) { td.classList.remove('in-attesa'); });
          avvisa(NON_RISPONDE, 'errore');
        });
      });
    }
    function annullaUltimo() {
      var v = pilaAnnulla.pop();
      if (v) { ripristina(v, true); } else { avvisa('Niente da annullare.', 'ok'); }
    }
    function rifaiUltimo() {
      var v = pilaRifai.pop();
      if (v) { ripristina(v, false); } else { avvisa('Niente da rifare.', 'ok'); }
    }

    /* il mouse: clic, trascinare, Maiusc+clic, Ctrl+clic */
    tab.addEventListener('mousedown', function (e) {
      var td = e.target.closest ? e.target.closest('td.cella') : null;
      if (!td || e.button !== 0) { return; }
      e.preventDefault();
      if (buffer.attivo()) { buffer.conferma(); }     // un codice a meta' vale per la cella di prima
      vaiA(td, e.shiftKey ? 'estendi' : (e.ctrlKey || e.metaKey) ? 'aggiungi' : 'solo', true);
      trascina = true;
    });
    tab.addEventListener('mouseover', function (e) {
      if (!trascina) { return; }
      var td = e.target.closest ? e.target.closest('td.cella') : null;
      if (td && td !== fuoco) { vaiA(td, 'estendi', true); }
    });
    document.addEventListener('mouseup', function () {
      if (!trascina) { return; }
      trascina = false;
      apriScelta(false);
    });
    tab.addEventListener('focusin', function (e) {
      var td = e.target.closest ? e.target.closest('td.cella') : null;
      if (td && td !== fuoco && !trascina) { vaiA(td, 'solo', true); }
    });

    /* la tastiera */
    var mosse = { ArrowLeft: [0, -1], ArrowRight: [0, 1], ArrowUp: [-1, 0], ArrowDown: [1, 0] };
    tab.addEventListener('keydown', function (e) {
      var td = e.target.closest ? e.target.closest('td.cella') : null;
      if (!td || e.ctrlKey || e.metaKey || e.altKey) { return; }
      if (td !== fuoco) { vaiA(td, 'solo', true); }
      var k = e.key;
      if (mosse[k]) {
        e.preventDefault();
        e.stopPropagation();          // le frecce qui muovono nella griglia, non cambiano mese
        if (buffer.attivo()) { buffer.conferma(); }
        var dove = M[fuoco._r + mosse[k][0]] && M[fuoco._r + mosse[k][0]][fuoco._c + mosse[k][1]];
        if (dove) {
          if (Scelta) { Scelta.chiudi(false); }
          vaiA(dove, e.shiftKey ? 'estendi' : 'solo');
        }
        return;
      }
      if (k === 'Home' || k === 'End') {
        e.preventDefault();
        e.stopPropagation();
        var riga = M[fuoco._r];
        vaiA(k === 'Home' ? riga[0] : riga[riga.length - 1], e.shiftKey ? 'estendi' : 'solo');
        return;
      }
      if (k === 'Enter' || k === 'F2' || k === ' ') {
        e.preventDefault();
        e.stopPropagation();
        if (buffer.attivo()) { buffer.conferma(); } else { apriScelta(true); }
        return;
      }
      if (k === 'Escape') {
        if (buffer.attivo()) { e.preventDefault(); buffer.annulla(); return; }
        if (Scelta && Scelta.aperta()) { e.preventDefault(); Scelta.chiudi(true); return; }
        if (scelte.length > 1) { e.preventDefault(); vaiA(fuoco, 'solo', true); }
        return;
      }
      if (k === 'Delete' || k === 'Backspace') {
        e.preventDefault();
        e.stopPropagation();
        buffer.annulla();
        if (Scelta) { Scelta.chiudi(false); }
        cambia({ azione: 'togli' }, scelte.slice());
        return;
      }
      if (k.length === 1 && /[A-Za-z0-9]/.test(k)) {
        e.preventDefault();
        e.stopPropagation();          // le lettere qui sono codici di turno, non tasti rapidi
        if (Scelta) { Scelta.chiudi(false); }
        buffer.scrivi(k);
      }
    });

    // Ctrl+Z e Ctrl+Y valgono in tutta la pagina, tranne mentre si scrive in un campo
    document.addEventListener('keydown', function (e) {
      if (!(e.ctrlKey || e.metaKey) || e.altKey || staScrivendo(e.target)) { return; }
      var schema = $('finestra-schema');
      if (schema && schema.open) { return; }
      var k = (e.key || '').toLowerCase();
      if (k === 'z' && !e.shiftKey) { e.preventDefault(); annullaUltimo(); }
      else if (k === 'y' || (k === 'z' && e.shiftKey)) { e.preventDefault(); rifaiUltimo(); }
    });

    griglia = {
      // le persone e i giorni delle celle scelte (per lo schema a rotazione)
      scelta: function () {
        if (scelte.length < 2) { return null; }
        var persone = [];
        var giorni = [];
        scelte.forEach(function (td) {
          var p = chiave(td).split('_');
          if (persone.indexOf(p[0]) < 0) { persone.push(p[0]); }
          giorni.push(p[1]);
        });
        giorni.sort();
        return { persone: persone, dal: giorni[0], al: giorni[giorni.length - 1] };
      }
    };
  })();

  /* ------------------------------------------------------------ la vista del giorno */
  (function () {
    var vg = $('vista-giorno');
    if (!vg || !Scelta) { return; }
    var indirizzo = vg.getAttribute('data-indirizzo');
    var struttura = vg.getAttribute('data-struttura') || '';
    var giorno = vg.getAttribute('data-giorno');
    var piste = elenco(vg.querySelectorAll('.pista[data-k]'));
    var MEMORIA_PAGINA = 'turni-giorno-ultima';
    var pagina = window.location.pathname + window.location.search;
    var ultima = null;      // l'ultima modifica, da poter annullare (sopravvive al ricaricare della pagina)

    var nomeDi = function (pista) { return testoDi(pista.parentNode.querySelector('.nome-giorno a')); };
    var ricorda = function (voce) {
      try { window.sessionStorage.setItem(MEMORIA_PAGINA, JSON.stringify(voce)); } catch (e) { /* pazienza: niente Annulla */ }
    };

    function cambiaGiorno(dati, k, nome) {
      var corpo = corpoDi(dati, { azione: dati.azione, celle: [k], dal: giorno, al: giorno,
                                  ruolo: vg.getAttribute('data-ruolo'), area_filtro: vg.getAttribute('data-area') });
      var testo = descrizioneDi(dati) + ' a ' + nome;
      var ricarica = false;
      accoda(function () {
        return manda(indirizzo, struttura, corpo).then(function (esito) {
          var d = esito.d;
          if (!d || !d.celle) { avvisa((d && d.errore) || NON_RISPONDE, 'errore'); return; }
          avvisa(d.errori, 'errore');
          if (d.fatti) {
            ricorda({ stato: d.prima, testo: testo, verso: 'annulla', avvisi: d.avvisi || [], pagina: pagina, quando: Date.now() });
            ricarica = true;
          }
        }, function () { avvisa(NON_RISPONDE, 'errore'); });
      }).then(function () { if (ricarica) { window.location.reload(); } });
    }
    function ripristina(voce) {
      var ricarica = false;
      accoda(function () {
        return manda(indirizzo, struttura, { azione: 'ripristina', stato: voce.stato, dal: giorno, al: giorno,
                                              ruolo: vg.getAttribute('data-ruolo'),
                                              area_filtro: vg.getAttribute('data-area') }).then(function (esito) {
          var d = esito.d;
          if (!d || !d.celle) { avvisa((d && d.errore) || NON_RISPONDE, 'errore'); return; }
          if (d.errori && d.errori.length) { avvisa(d.errori, 'errore'); return; }
          ricorda({ stato: d.prima, testo: voce.testo, verso: voce.verso === 'annulla' ? 'rifai' : 'annulla',
                    rifatto: voce.verso !== 'annulla', avvisi: [], pagina: pagina, quando: Date.now() });
          ricarica = true;
        }, function () { avvisa(NON_RISPONDE, 'errore'); });
      }).then(function () { if (ricarica) { window.location.reload(); } });
    }
    function usaUltima() {
      if (!ultima) { avvisa('Niente da annullare.', 'ok'); return; }
      var v = ultima;
      ultima = null;
      ripristina(v);
    }

    // dopo il ricaricare: com'e' andata l'ultima modifica, con «Annulla» (o «Rifai»)
    try {
      var salvata = JSON.parse(window.sessionStorage.getItem(MEMORIA_PAGINA) || 'null');
      window.sessionStorage.removeItem(MEMORIA_PAGINA);
      if (salvata && salvata.pagina === pagina && Date.now() - salvata.quando < 120000 && salvata.stato) {
        ultima = salvata;
        var frase = salvata.verso === 'rifai' ? 'Annullato: ' + salvata.testo + '.'
          : (salvata.rifatto ? 'Rifatto: ' + salvata.testo + '.' : maiuscola(salvata.testo) + '.');
        avvisa(frase, 'ok', { etichetta: salvata.verso === 'rifai' ? 'Rifai' : 'Annulla', fai: usaUltima });
        avvisa(salvata.avvisi, 'avviso');
      }
    } catch (e) { /* senza memoria del browser: niente Annulla dopo il ricaricare */ }

    function apri(k, ancora, nome, contenitore, daTastiera) {
      var attuali = contenitore ? turniDi(contenitore) : [];
      ancora.classList.add('aperta');
      Scelta.apri({
        titolo: nome,
        sotto: giornoScritto(giorno),
        attuali: attuali,
        area: attuali.length === 1 ? attuali[0].area : '',
        pieno: attuali.length > 0,
        tieniArea: false,
        ancora: ancora,
        daTastiera: daTastiera,
        ignora: function (x) { return !!(x.closest && x.closest('.pista[data-k]')); },
        quando: function (dati) { cambiaGiorno(dati, k, nome); },
        chiusa: function (restituisci) {
          ancora.classList.remove('aperta');
          // «Turno a...»: la tendina torna vuota, cosi' si puo' scegliere di nuovo la stessa persona
          if (ancora.tagName === 'SELECT') { ancora.value = ''; }
          if (restituisci && ancora.focus) { ancora.focus({ preventScroll: true }); }
        }
      });
    }
    var attiva = null;
    var conCodice = null;
    var buffer = nuovoBuffer(function (t) {
      if (conCodice) { conCodice.removeAttribute('data-scrivendo'); }
      conCodice = t && attiva ? attiva : null;
      if (conCodice) { conCodice.setAttribute('data-scrivendo', t); }
    }, function (tipo) {
      if (attiva) {
        cambiaGiorno({ azione: 'metti', tipo: tipo.id, tieni_area: true, descrizione: tipo.nome },
                     attiva.getAttribute('data-k'), nomeDi(attiva));
      }
    });

    piste.forEach(function (p, i) {
      p.addEventListener('click', function () { attiva = p; apri(p.getAttribute('data-k'), p, nomeDi(p), p.parentNode, false); });
      p.addEventListener('focus', function () { if (attiva !== p) { buffer.annulla(); } attiva = p; });
      p.addEventListener('keydown', function (e) {
        if (e.ctrlKey || e.metaKey || e.altKey) { return; }
        var k = e.key;
        if (k === 'Enter' || k === ' ' || k === 'F2') {
          e.preventDefault();
          if (buffer.attivo()) { buffer.conferma(); } else { apri(p.getAttribute('data-k'), p, nomeDi(p), p.parentNode, true); }
        } else if (k === 'ArrowDown' || k === 'ArrowUp') {
          e.preventDefault();
          e.stopPropagation();
          buffer.annulla();
          var altra = piste[i + (k === 'ArrowDown' ? 1 : -1)];
          if (altra) { altra.focus(); }
        } else if (k === 'Escape' && buffer.attivo()) {
          e.preventDefault();
          buffer.annulla();
        } else if (k === 'Delete' || k === 'Backspace') {
          e.preventDefault();
          e.stopPropagation();
          if (turniDi(p.parentNode).length) { cambiaGiorno({ azione: 'togli' }, p.getAttribute('data-k'), nomeDi(p)); }
        } else if (k.length === 1 && /[A-Za-z0-9]/.test(k)) {
          e.preventDefault();
          e.stopPropagation();
          buffer.scrivi(k);
        }
      });
    });

    // «Turno a...»: scelta la persona, si apre la scelta del turno
    var sel = $('aggiungi-persona');
    if (sel) {
      var ultimoTasto = 0;
      var apriPerScelta = function () {
        if (!sel.value) { return; }
        var testo = testoDi(sel.options[sel.selectedIndex]);
        var k = sel.value + '_' + giorno;
        var pista = vg.querySelector('.pista[data-k="' + k + '"]');
        apri(k, sel, testo, pista ? pista.parentNode : null, true);
      };
      sel.addEventListener('keydown', function (e) {
        e.stopPropagation();
        if (e.key === 'Enter') { e.preventDefault(); apriPerScelta(); } else { ultimoTasto = Date.now(); }
      });
      // con le frecce sulla tendina chiusa il valore cambia a ogni tasto: si apre solo con Invio
      sel.addEventListener('change', function () { if (Date.now() - ultimoTasto > 400) { apriPerScelta(); } });
    }

    document.addEventListener('keydown', function (e) {
      if (!(e.ctrlKey || e.metaKey) || e.altKey || staScrivendo(e.target)) { return; }
      var k = (e.key || '').toLowerCase();
      if (k === 'z' || k === 'y') { e.preventDefault(); usaUltima(); }
    });
  })();

  /* ------------------------------------------------------------ lo schema a rotazione */
  (function () {
    var fin = $('finestra-schema');
    if (!fin) { return; }
    var modulo = fin.querySelector('form');
    var seq = $('schema-sequenza');
    var ant = $('schema-anteprima');
    var prova = $('schema-prova');
    var errore = $('schema-errore');
    var dal = modulo.querySelector('input[name="dal"]');
    var al = modulo.querySelector('input[name="al"]');
    var sfasamento = modulo.querySelector('input[name="sfasamento"]');
    var caselle = elenco(modulo.querySelectorAll('input[name="persone"]'));
    var tutti = elenco(modulo.querySelectorAll('input[data-tutti]'));

    function leggi() {
      var pezzi = seq.value.toUpperCase().split(/[\s,;]+/).filter(function (x) { return !!x; });
      var voci = [];
      var sconosciuti = [];
      pezzi.forEach(function (x) {
        if (x === '-' || x === '.' || x === '_') { voci.push(null); }
        else if (PER_CODICE[x]) { voci.push(PER_CODICE[x]); }
        else if (sconosciuti.indexOf(x) < 0) { sconosciuti.push(x); }
      });
      return { voci: voci, sconosciuti: sconosciuti, troppi: pezzi.length > 60 };
    }
    function chipDi(t) {
      if (!t) {
        var vuoto = nuovo('span', 'turno vuoto-schema', '–');
        vuoto.title = 'giorno vuoto';
        return vuoto;
      }
      var c = chipCella({ codice: t.codice, orario: t.orario, colore: t.colore, testo: t.testo, categoria: t.categoria }, false, false);
      c.title = t.nome + (t.orario ? ' ' + t.orario : '');
      return c;
    }
    function scelteOrdinate() { return caselle.filter(function (c) { return c.checked; }); }
    function aggiorna() {
      var l = leggi();
      ant.textContent = '';
      l.voci.forEach(function (t) { ant.appendChild(chipDi(t)); });
      if (l.sconosciuti.length) { ant.appendChild(nuovo('span', 'errore-codice', 'Codici sconosciuti: ' + l.sconosciuti.join(', '))); }
      if (l.voci.length) { ant.appendChild(nuovo('span', 'lunghezza-schema', l.voci.length + (l.voci.length === 1 ? ' giorno' : ' giorni') + ', poi si ripete')); }
      tutti.forEach(function (t) {
        var del = caselle.filter(function (c) { return c.getAttribute('data-ruolo') === t.getAttribute('data-tutti'); });
        var quante = del.filter(function (c) { return c.checked; }).length;
        t.checked = del.length > 0 && quante === del.length;
        t.indeterminate = quante > 0 && quante < del.length;
      });
      // come verranno i primi giorni, per le prime persone scelte
      prova.textContent = '';
      var persone = scelteOrdinate();
      if (!l.voci.length || l.sconosciuti.length || !dal.value) { return; }
      if (!persone.length) {
        prova.appendChild(nuovo('p', 'aiuto', 'Scelte le persone, qui si vede come vengono i primi giorni.'));
        return;
      }
      var totale = al.value && al.value >= dal.value ? giorniTra(dal.value, al.value) + 1 : 1;
      var n = Math.min(14, totale);
      var passo = Math.max(0, parseInt(sfasamento.value, 10) || 0);
      var tabella = nuovo('table', 'tabella-schema');
      var testa = nuovo('tr');
      testa.appendChild(nuovo('th'));
      var inizio = dataDi(dal.value);
      for (var d = 0; d < n; d++) {
        var g = new Date(inizio.getFullYear(), inizio.getMonth(), inizio.getDate() + d);
        var th = nuovo('th', g.getDay() === 0 ? 'domenica' : '');
        th.appendChild(nuovo('span', null, INIZIALI[g.getDay()]));
        th.appendChild(nuovo('b', null, g.getDate()));
        testa.appendChild(th);
      }
      tabella.appendChild(testa);
      persone.slice(0, 6).forEach(function (c, i) {
        var tr = nuovo('tr');
        tr.appendChild(nuovo('th', null, testoDi(c.parentNode)));
        for (var d = 0; d < n; d++) {
          var td = nuovo('td');
          td.appendChild(chipDi(l.voci[(d + i * passo) % l.voci.length]));
          tr.appendChild(td);
        }
        tabella.appendChild(tr);
      });
      prova.appendChild(tabella);
      var resto = [];
      if (persone.length > 6) { resto.push('altre ' + (persone.length - 6) + ' persone'); }
      if (totale > n) { resto.push('fino al ' + giornoBreve(al.value)); }
      if (resto.length) { prova.appendChild(nuovo('p', 'aiuto', '… e così via: ' + resto.join(', ') + '.')); }
    }

    elenco(document.querySelectorAll('[data-apri-schema]')).forEach(function (a) {
      a.addEventListener('click', function (e) {
        e.preventDefault();
        // con un gruppo di celle scelto nella griglia: quelle persone e quei giorni
        var s = griglia && griglia.scelta();
        if (s) {
          caselle.forEach(function (c) { c.checked = s.persone.indexOf(c.value) >= 0; });
          dal.value = s.dal;
          al.value = s.al;
        }
        errore.hidden = true;
        aggiorna();
        if (Scelta) { Scelta.chiudi(false); }
        fin.showModal();
        seq.focus();
      });
    });
    elenco(fin.querySelectorAll('[data-chiudi-schema]')).forEach(function (b) {
      b.addEventListener('click', function () { fin.close(); });
    });
    elenco(fin.querySelectorAll('[data-aggiungi-codice]')).forEach(function (b) {
      b.addEventListener('click', function () {
        seq.value = (seq.value.replace(/\s+$/, '') + ' ' + b.getAttribute('data-aggiungi-codice')).trim();
        aggiorna();
      });
    });
    tutti.forEach(function (t) {
      t.addEventListener('change', function () {
        caselle.forEach(function (c) { if (c.getAttribute('data-ruolo') === t.getAttribute('data-tutti')) { c.checked = t.checked; } });
        aggiorna();
      });
    });
    caselle.forEach(function (c) { c.addEventListener('change', aggiorna); });
    [seq, dal, al, sfasamento].forEach(function (x) { x.addEventListener('input', aggiorna); x.addEventListener('change', aggiorna); });
    // i tasti dentro la finestra non devono arrivare ai tasti rapidi della pagina (le frecce cambierebbero mese)
    fin.addEventListener('keydown', function (e) {
      if (!(e.key === 'Enter' && (e.ctrlKey || e.metaKey))) { e.stopPropagation(); }
    });
    modulo.addEventListener('submit', function (e) {
      var l = leggi();
      var problema = '';
      if (!l.voci.length) { problema = 'Scrivere la sequenza dei turni, per esempio: M M P P N SN R R.'; }
      else if (l.sconosciuti.length) { problema = 'Codici sconosciuti: ' + l.sconosciuti.join(', ') + '. I codici sono quelli dei pulsanti colorati.'; }
      else if (l.troppi) { problema = 'Sequenza troppo lunga: al massimo 60 giorni.'; }
      else if (!scelteOrdinate().length) { problema = 'Scegliere almeno una persona.'; }
      else if (!dal.value || !al.value || al.value < dal.value) { problema = 'Il periodo non va: «Al» deve venire dopo «Dal».'; }
      else if (giorniTra(dal.value, al.value) >= 120) { problema = 'Periodo troppo lungo: al massimo 120 giorni alla volta.'; }
      if (problema) {
        e.preventDefault();
        errore.textContent = problema;
        errore.hidden = false;
      }
    });
  })();

  /* ------------------------------------------------------------ copia la settimana prima */
  elenco(document.querySelectorAll('[data-copia-settimana]')).forEach(function (a) {
    a.addEventListener('click', function (e) {
      e.preventDefault();
      var f = $('modulo-copia');
      if (f && window.confirm('Copiare qui i turni della settimana prima? Le celle già piene restano come sono.')) {
        f.submit();
      }
    });
  });

  /* ------------------------------------------------------------ pagina dei tipi di turno */
  (function () {
    var categoria = document.querySelector('[data-categoria-tipo]');
    if (!categoria) { return; }
    var prova = $('anteprima-tipo');
    var colore = $('colore');
    var codice = $('codice');
    var aggiorna = function () {
      var conOrario = categoria.value === 'LAVORO' || categoria.value === 'REPERIBILITA';
      elenco(document.querySelectorAll('.orario-tipo')).forEach(function (x) { x.hidden = !conOrario; });
      ['ora_inizio', 'ora_fine'].forEach(function (id) { var x = $(id); if (x) { x.required = conOrario; } });
      if (prova && colore) {
        prova.style.setProperty('--c', colore.value);
        prova.style.setProperty('--t', testoSu(colore.value));
        prova.classList.toggle('senza-orario', !conOrario);
        prova.classList.toggle('reperibile', categoria.value === 'REPERIBILITA');
        prova.querySelector('b').textContent = (codice && codice.value.replace(/\s/g, '').toUpperCase().slice(0, 4)) || 'M';
      }
    };
    [categoria, colore, codice].forEach(function (x) {
      if (x) { x.addEventListener('input', aggiorna); x.addEventListener('change', aggiorna); }
    });
    aggiorna();
  })();

  /* ------------------------------------------------------------ scheda di una persona */
  (function () {
    var ruoli = elenco(document.querySelectorAll('.scelta-ruolo input[name="ruolo"]'));
    var medico = document.querySelector('.campo-medico');
    if (!ruoli.length || !medico) { return; }
    var tendina = medico.querySelector('select');
    var aggiorna = function () {
      var scelto = ruoli.filter(function (r) { return r.checked; })[0];
      var e = !scelto || scelto.value === 'MEDICO';
      // il collegamento all'agenda vale solo per i medici: per gli altri il campo sparisce e non si salva
      medico.hidden = !e;
      if (tendina) { tendina.disabled = !e; }
    };
    ruoli.forEach(function (r) { r.addEventListener('change', aggiorna); });
    aggiorna();
  })();
})();
