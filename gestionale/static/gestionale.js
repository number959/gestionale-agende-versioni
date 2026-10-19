/* Gestionale agende - piccoli aiuti nei moduli. Nessuna libreria: il
   programma deve funzionare senza internet. I dati arrivano dal server e si
   scrivono sempre con textContent, mai come HTML. */
(function () {
  'use strict';

  function $(id) { return document.getElementById(id); }

  /* ------------------------------------------ paziente nel modulo di prenotazione */
  var cerca = $('cerca_paziente');
  if (cerca) {
    var box = $('suggerimenti'), campoId = $('paziente_id'), cognome = $('paziente'),
        nome = $('nome_paziente'), telefono = $('telefono'), email = $('email_paziente'),
        nascita = $('data_nascita'), codiceFiscale = $('codice_fiscale'), indirizzo = $('indirizzo_paziente'),
        scelto = $('paziente-scelto'), attesa = null, voci = [], evidenziata = -1,
        cognomeScelto = cognome ? cognome.value : '';

    function chiudi() { box.hidden = true; box.textContent = ''; voci = []; evidenziata = -1; }

    function scheda(id) {
      return cerca.getAttribute('data-scheda').replace(/\/0$/, '/' + id);
    }

    function mostraScelto(p) {
      scelto.textContent = 'Paziente in anagrafica: ';
      var a = document.createElement('a');
      a.href = scheda(p.id);
      a.textContent = (p.cognome + ' ' + p.nome).trim();
      scelto.appendChild(a);
    }

    function scegli(p) {
      campoId.value = p.id;
      cognome.value = p.cognome; nome.value = p.nome;
      telefono.value = p.telefono; email.value = p.email;
      if (nascita) { nascita.value = p.nascita_iso || ''; }
      if (codiceFiscale) { codiceFiscale.value = p.codice_fiscale || ''; }
      if (indirizzo) { indirizzo.value = p.indirizzo || ''; }
      if ($('sesso')) { $('sesso').value = p.sesso || ''; }
      if ($('luogo_nascita')) { $('luogo_nascita').value = p.luogo || ''; }
      if ($('luogo_nascita_testo')) { $('luogo_nascita_testo').value = p.luogo_testo || p.luogo || ''; }
      if (window.controllaCodiceFiscale) { window.controllaCodiceFiscale(); }
      cognomeScelto = p.cognome;
      mostraScelto(p);
      cerca.value = '';
      chiudi();
    }

    function evidenzia(i) {
      voci.forEach(function (v, k) { v.classList.toggle('attiva', k === i); });
      evidenziata = i;
    }

    function disegna(lista) {
      box.textContent = '';
      voci = [];
      if (!lista.length) {
        var vuoto = document.createElement('div');
        vuoto.className = 'nessuno';
        vuoto.textContent = 'Nessun paziente trovato: scrivere cognome e telefono qui sotto.';
        box.appendChild(vuoto);
        box.hidden = false;
        return;
      }
      lista.forEach(function (p) {
        var b = document.createElement('button');
        b.type = 'button';
        var riga = document.createElement('b');
        riga.textContent = (p.cognome + ' ' + p.nome).trim();
        b.appendChild(riga);
        var dettagli = [p.telefono, p.nascita ? 'nato il ' + p.nascita : '',
                        p.prossimo ? 'prossimo ' + p.prossimo : ''].filter(Boolean).join(' · ');
        if (dettagli) {
          var d = document.createElement('span');
          d.textContent = ' ' + dettagli;
          b.appendChild(d);
        }
        b.addEventListener('mousedown', function (e) { e.preventDefault(); scegli(p); });
        box.appendChild(b);
        voci.push(b);
      });
      box.hidden = false;
      evidenzia(0);
      box._dati = lista;
    }

    cerca.addEventListener('input', function () {
      clearTimeout(attesa);
      var q = cerca.value.trim();
      if (q.length < 2) { chiudi(); return; }
      attesa = setTimeout(function () {
        fetch(cerca.getAttribute('data-indirizzo') + '?q=' + encodeURIComponent(q))
          .then(function (r) { return r.ok ? r.json() : []; })
          .then(disegna)
          .catch(chiudi);
      }, 180);
    });
    cerca.addEventListener('keydown', function (e) {
      if (box.hidden || !voci.length) { return; }
      if (e.key === 'ArrowDown') { e.preventDefault(); evidenzia(Math.min(evidenziata + 1, voci.length - 1)); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); evidenzia(Math.max(evidenziata - 1, 0)); }
      else if (e.key === 'Enter') { e.preventDefault(); if (evidenziata >= 0) { scegli(box._dati[evidenziata]); } }
      else if (e.key === 'Escape') { chiudi(); }
    });
    cerca.addEventListener('blur', function () { setTimeout(chiudi, 150); });

    // cambiando il cognome dopo aver scelto dall'elenco non si parla piu' di lui
    if (cognome) {
      cognome.addEventListener('input', function () {
        if (campoId.value && cognome.value.trim().toLowerCase() !== cognomeScelto.trim().toLowerCase()) {
          campoId.value = '';
          scelto.textContent = 'Nuovo paziente: la scheda si crea al salvataggio.';
        }
      });
    }
  }

  /* ------------------------------------------ codice fiscale e luogo di nascita */
  // Il controllo lo fa il programma (pazienti.codice_fiscale_json, lo stesso
  // del salvataggio): mentre si scrive dice se il codice va e perche' no,
  // riempie dal codice data, sesso e luogo lasciati vuoti, e se il codice
  // manca lo calcola dai dati. Il codice calcolato qui si aggiorna se poi
  // cambiano i dati; quello scritto a mano non si tocca.
  var cf = $('codice_fiscale');
  if (cf && cf.getAttribute('data-controllo')) {
    var esitoCf = $('esito-cf'),
        campoCognome = $('cognome') || $('paziente'), campoNome = $('nome') || $('nome_paziente'),
        campoSesso = $('sesso'), campoData = $('data_nascita'),
        luogoTesto = $('luogo_nascita_testo'), luogoCodice = $('luogo_nascita'), boxLuogo = $('suggerimenti-luogo'),
        segnoCalcolato = document.createElement('input'),
        calcolatoQui = '', attesaCf = null, numeroCf = 0,
        // quello che abbiamo scritto noi dal codice: se cambia il codice si aggiorna, se lo cambia chi scrive no
        dalCodice = {data: null, sesso: null, luogo: null};
    segnoCalcolato.type = 'hidden';
    segnoCalcolato.name = 'cf_calcolato';
    cf.parentNode.appendChild(segnoCalcolato);

    var valoreDi = function (el) { return el ? el.value.trim() : ''; };
    var pulito = function () { return cf.value.replace(/[\s.\-]/g, '').toUpperCase(); };
    var segna = function () { segnoCalcolato.value = (calcolatoQui && pulito() === calcolatoQui) ? '1' : ''; };

    var mostra = function (classe, testo, avvisi) {
      if (!esitoCf) { return; }
      esitoCf.className = 'esito-cf' + (classe ? ' ' + classe : '');
      esitoCf.textContent = '';
      [testo].concat(avvisi || []).forEach(function (riga, i) {
        if (!riga) { return; }
        var r = document.createElement('span');
        if (i > 0) { r.className = 'avviso-cf'; }
        r.textContent = riga;
        esitoCf.appendChild(r);
      });
    };

    var applica = function (d, scritto, calcolando) {
      if (d.luogo && luogoCodice && !luogoCodice.value && valoreDi(luogoTesto)) {
        // il luogo scritto a mano, senza sceglierlo: il programma l'ha riconosciuto
        luogoCodice.value = d.luogo;
        if (d.luogo_testo) { luogoTesto.value = d.luogo_testo; }
      }
      if (d.stato === 'valido') {
        var dati = d.da_cf || {};
        var libero = function (valore, nostro) { return !valore || valore === nostro; };
        if (campoData && dati.data_nascita && libero(campoData.value, dalCodice.data)) {
          campoData.value = dalCodice.data = dati.data_nascita;
        }
        if (campoSesso && dati.sesso && libero(campoSesso.value, dalCodice.sesso)) {
          campoSesso.value = dalCodice.sesso = dati.sesso;
        }
        if (luogoCodice && dati.luogo && (libero(luogoCodice.value, dalCodice.luogo) && (!valoreDi(luogoTesto) ||
            luogoCodice.value === dalCodice.luogo))) {
          luogoCodice.value = dalCodice.luogo = dati.luogo;
          if (luogoTesto) { luogoTesto.value = dati.luogo_testo || dati.luogo; }
        }
        mostra(d.avvisi.length ? 'avviso' : 'ok', '✓ ' + d.messaggio, d.avvisi);
      } else if (d.stato === 'non_valido') {
        // mentre si scrivono i primi caratteri non si segnala niente: si aspetta il sedicesimo, o l'uscita dal campo
        if (scritto.length < 16 && document.activeElement === cf) { mostra('', '', []); return; }
        mostra('errore', '✗ ' + d.messaggio, []);
      } else if (d.stato === 'calcolato') {
        if (calcolando) { cf.value = d.calcolato; calcolatoQui = d.calcolato; }
        mostra('calcolato', d.messaggio, d.avvisi);
      } else if (d.stato === 'incompleto') {
        if (calcolando && calcolatoQui && pulito() === calcolatoQui) { cf.value = ''; calcolatoQui = ''; }
        mostra('', d.messaggio, []);
      }
      segna();
    };

    var esegui = function () {
      var scritto = pulito();
      var calcolando = !scritto || scritto === calcolatoQui;
      var dati = {cf: calcolando ? '' : scritto, cognome: valoreDi(campoCognome), nome: valoreDi(campoNome),
                  sesso: valoreDi(campoSesso), data_nascita: valoreDi(campoData),
                  luogo: luogoCodice ? luogoCodice.value : '', luogo_testo: valoreDi(luogoTesto)};
      var parti = Object.keys(dati).map(function (k) { return k + '=' + encodeURIComponent(dati[k]); });
      var numero = numeroCf;
      fetch(cf.getAttribute('data-controllo') + '?' + parti.join('&'))
        .then(function (r) { return r.ok ? r.json() : null; })
        // una risposta arrivata dopo che si e' scritto ancora non vale piu': ne arriva una piu' nuova
        .then(function (d) { if (d && numero === numeroCf) { applica(d, scritto, calcolando); } })
        .catch(function () {});
    };

    var controlla = function (subito) {
      numeroCf++;
      clearTimeout(attesaCf);
      attesaCf = setTimeout(esegui, subito ? 0 : 300);
    };
    window.controllaCodiceFiscale = function () { calcolatoQui = ''; controlla(true); };

    cf.addEventListener('input', function () { segna(); controlla(false); });
    cf.addEventListener('blur', function () { controlla(true); });
    [campoCognome, campoNome, campoData].forEach(function (el) {
      if (el) { el.addEventListener('input', function () { controlla(false); }); }
    });
    if (campoData) { campoData.addEventListener('change', function () { controlla(true); }); }
    if (campoSesso) { campoSesso.addEventListener('change', function () { controlla(true); }); }

    // ---- il luogo di nascita: suggerimenti mentre si scrive, il codice nel campo nascosto
    if (luogoTesto && luogoCodice && boxLuogo) {
      var vociLuogo = [], datiLuogo = [], scelta = -1, attesaLuogo = null;
      var chiudiLuogo = function () { boxLuogo.hidden = true; boxLuogo.textContent = ''; vociLuogo = []; datiLuogo = []; scelta = -1; };
      var evidenziaLuogo = function (i) {
        vociLuogo.forEach(function (v, k) { v.classList.toggle('attiva', k === i); });
        scelta = i;
      };
      var scegliLuogo = function (x) {
        luogoCodice.value = x.codice;
        luogoTesto.value = x.testo;
        chiudiLuogo();
        controlla(true);
      };
      var disegnaLuogo = function (lista) {
        boxLuogo.textContent = '';
        vociLuogo = [];
        datiLuogo = lista;
        if (!lista.length) {
          var vuoto = document.createElement('div');
          vuoto.className = 'nessuno';
          vuoto.textContent = 'Nessun comune o stato con questo nome.';
          boxLuogo.appendChild(vuoto);
          boxLuogo.hidden = false;
          return;
        }
        lista.forEach(function (x) {
          var b = document.createElement('button');
          b.type = 'button';
          var nome = document.createElement('b');
          nome.textContent = x.testo;
          b.appendChild(nome);
          if (x.periodo) {
            var periodo = document.createElement('span');
            periodo.textContent = ' ' + x.periodo;
            b.appendChild(periodo);
          }
          b.addEventListener('mousedown', function (e) { e.preventDefault(); scegliLuogo(x); });
          boxLuogo.appendChild(b);
          vociLuogo.push(b);
        });
        boxLuogo.hidden = false;
        evidenziaLuogo(0);
      };
      luogoTesto.addEventListener('input', function () {
        luogoCodice.value = '';               // il nome e' cambiato: il codice di prima non vale piu'
        clearTimeout(attesaLuogo);
        var q = luogoTesto.value.trim();
        if (q.length < 2) { chiudiLuogo(); controlla(false); return; }
        attesaLuogo = setTimeout(function () {
          fetch(luogoTesto.getAttribute('data-indirizzo') + '?q=' + encodeURIComponent(q) +
                '&data_nascita=' + encodeURIComponent(valoreDi(campoData)))
            .then(function (r) { return r.ok ? r.json() : []; })
            .then(disegnaLuogo)
            .catch(chiudiLuogo);
        }, 150);
      });
      luogoTesto.addEventListener('keydown', function (e) {
        if (boxLuogo.hidden || !vociLuogo.length) { return; }
        if (e.key === 'ArrowDown') { e.preventDefault(); evidenziaLuogo(Math.min(scelta + 1, vociLuogo.length - 1)); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); evidenziaLuogo(Math.max(scelta - 1, 0)); }
        else if (e.key === 'Enter') { e.preventDefault(); if (scelta >= 0) { scegliLuogo(datiLuogo[scelta]); } }
        else if (e.key === 'Escape') { chiudiLuogo(); }
      });
      luogoTesto.addEventListener('blur', function () { setTimeout(function () { chiudiLuogo(); controlla(true); }, 150); });
    }

    controlla(true);
  }

  /* ------------------------------------------ invii: il pulsante dice che sta lavorando */
  document.querySelectorAll('form[data-attesa]').forEach(function (f) {
    f.addEventListener('submit', function () {
      var b = f.querySelector('button[type="submit"]');
      if (!b) { return; }
      // dopo l'invio del modulo: un pulsante disattivato prima non verrebbe inviato
      setTimeout(function () { b.disabled = true; b.textContent = f.getAttribute('data-attesa'); }, 0);
    });
  });

  /* ------------------------------------------ campi in piu' secondo la prestazione */
  var prestazione = $('prestazione');
  if (prestazione) {
    var durata = $('durata');
    var aggiorna = function () {
      document.querySelectorAll('.campi-extra').forEach(function (g) {
        g.hidden = g.getAttribute('data-prestazione') !== prestazione.value;
      });
      var opzione = prestazione.options[prestazione.selectedIndex];
      if (durata && opzione && opzione.getAttribute('data-durata')) {
        durata.placeholder = opzione.getAttribute('data-durata') + ' (dalla prestazione)';
      }
    };
    prestazione.addEventListener('change', aggiorna);
    aggiorna();
  }

  /* ----------------------- degenza: per le sale operatorie, o se gia' indicata */
  var stanzaScelta = $('risorsa'), riquadroDegenza = $('campi-degenza');
  if (stanzaScelta && riquadroDegenza) {
    var degenza = $('degenza');
    var mostraDegenza = function () {
      var o = stanzaScelta.options[stanzaScelta.selectedIndex];
      var tipo = o ? o.getAttribute('data-tipo') : '';
      riquadroDegenza.hidden = !(tipo && tipo !== 'AMBULATORIO') && !riquadroDegenza.getAttribute('data-sempre') && !(degenza && degenza.value);
      document.querySelectorAll('.solo-ricovero').forEach(function (x) { x.hidden = !degenza || degenza.value !== 'RICOVERO'; });
    };
    stanzaScelta.addEventListener('change', mostraDegenza);
    if (degenza) { degenza.addEventListener('change', mostraDegenza); }
    mostraDegenza();
  }

  /* ------------------------------------------ turno settimanale o di un giorno */
  var ripetizione = $('ripetizione');
  if (ripetizione) {
    var cambia = function () {
      var singolo = ripetizione.value === 'giorno';
      document.querySelectorAll('.solo-giorno').forEach(function (x) { x.hidden = !singolo; });
      document.querySelectorAll('.solo-settimanale').forEach(function (x) { x.hidden = singolo; });
      var d = $('data_singola');
      if (d) { d.required = singolo; }
    };
    ripetizione.addEventListener('change', cambia);
    cambia();
  }
  /* ------------------------------------------ prezzo proposto dal listino */
  var importo = $('importo'), convenzione = $('convenzione');
  if (importo && prestazione && importo.getAttribute('data-tariffe')) {
    var tariffe = {};
    try { tariffe = JSON.parse(importo.getAttribute('data-tariffe')) || {}; } catch (e) { tariffe = {}; }
    var proposto = importo.value;
    var proponi = function () {
      // si propone solo se il campo e' vuoto o contiene l'ultimo prezzo proposto:
      // un importo scritto a mano non si tocca
      if (importo.value && importo.value !== proposto) { return; }
      var t = tariffe[prestazione.value] || {};
      var c = (convenzione ? convenzione.value : '').trim().toLowerCase().replace(/\s+/g, ' ');
      var v = (c && c !== 'privato' && t[c]) ? t[c] : (t[''] || '');
      importo.value = v;
      proposto = v;
    };
    prestazione.addEventListener('change', proponi);
    if (convenzione) { convenzione.addEventListener('change', proponi); }
    if (!importo.value) { proponi(); }
  }

  /* ------------------------------------------ ripetizione dell'appuntamento */
  var ripeti = $('ripeti');
  if (ripeti) {
    var mostraRipeti = function () {
      document.querySelectorAll('.solo-ripeti').forEach(function (x) { x.hidden = !ripeti.checked; });
    };
    ripeti.addEventListener('change', mostraRipeti);
    mostraRipeti();
  }

  /* ------------------------------------------ seleziona tutti (chiusura giornata) */
  document.querySelectorAll('input[data-seleziona-tutti]').forEach(function (casella) {
    casella.addEventListener('change', function () {
      var nome = casella.getAttribute('data-seleziona-tutti');
      document.querySelectorAll('input[name="' + nome + '"]').forEach(function (x) { x.checked = casella.checked; });
    });
  });

  /* ------------------------------------------ ricerca rapida nel menu */
  var rapida = $('ricerca-rapida'), risultati = $('risultati-rapidi');
  if (rapida && risultati) {
    var attesaRapida = null, vociRapide = [], scelta = -1;
    var chiudiRapida = function () { risultati.hidden = true; risultati.textContent = ''; vociRapide = []; scelta = -1; };
    var evidenziaRapida = function (i) {
      vociRapide.forEach(function (v, k) { v.classList.toggle('attiva', k === i); });
      scelta = i;
    };
    var voce = function (testo, dettaglio, url, gruppo) {
      var a = document.createElement('a');
      a.href = url;
      a.className = 'voce-rapida';
      var b = document.createElement('b');
      b.textContent = testo;
      a.appendChild(b);
      if (dettaglio) {
        var s = document.createElement('span');
        s.textContent = ' ' + dettaglio;
        a.appendChild(s);
      }
      if (gruppo) { a.setAttribute('data-gruppo', gruppo); }
      risultati.appendChild(a);
      vociRapide.push(a);
    };
    var disegnaRapida = function (dati) {
      risultati.textContent = '';
      vociRapide = [];
      if (dati.giorno) { voce('Vai a ' + dati.giorno.etichetta, '', dati.giorno.url, 'giorno'); }
      (dati.pazienti || []).forEach(function (p) { voce(p.etichetta, p.telefono, p.url, 'paziente'); });
      (dati.medici || []).forEach(function (m) { voce(m.etichetta, 'settimana del medico', m.url, 'medico'); });
      (dati.prestazioni || []).forEach(function (p) { voce(p.etichetta, p.dettaglio, p.url, 'prestazione'); });
      if (!vociRapide.length) {
        var n = document.createElement('div');
        n.className = 'nessuno';
        n.textContent = 'Nessun risultato.';
        risultati.appendChild(n);
      }
      risultati.hidden = false;
      evidenziaRapida(vociRapide.length ? 0 : -1);
    };
    rapida.addEventListener('input', function () {
      clearTimeout(attesaRapida);
      var q = rapida.value.trim();
      if (!q) { chiudiRapida(); return; }
      attesaRapida = setTimeout(function () {
        var base = rapida.getAttribute('data-indirizzo');
        fetch(base + (base.indexOf('?') >= 0 ? '&' : '?') + 'q=' + encodeURIComponent(q))
          .then(function (r) { return r.ok ? r.json() : {}; })
          .then(disegnaRapida)
          .catch(chiudiRapida);
      }, 160);
    });
    rapida.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { chiudiRapida(); rapida.blur(); return; }
      if (risultati.hidden || !vociRapide.length) { return; }
      if (e.key === 'ArrowDown') { e.preventDefault(); evidenziaRapida(Math.min(scelta + 1, vociRapide.length - 1)); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); evidenziaRapida(Math.max(scelta - 1, 0)); }
      else if (e.key === 'Enter' && scelta >= 0) { e.preventDefault(); window.location.href = vociRapide[scelta].href; }
    });
    rapida.addEventListener('blur', function () { setTimeout(chiudiRapida, 200); });
  }

  /* ------------------------------------------ tasti rapidi */
  var aiuto = $('aiuto-tasti');
  var sta_scrivendo = function (el) {
    if (!el) { return false; }
    var tag = el.tagName;
    return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable;
  };
  var clicca = function (nome) {
    var el = document.querySelector('[data-tasto="' + nome + '"]');
    if (el) { el.click(); return true; }
    return false;
  };
  document.addEventListener('keydown', function (e) {
    // Ctrl+Invio salva il modulo in cui si sta scrivendo
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && e.target && e.target.form) {
      e.preventDefault();
      var principale = e.target.form.querySelector('button[type="submit"].primario') ||
                       e.target.form.querySelector('button[type="submit"]:not([name])');
      if (principale) { principale.click(); } else { e.target.form.requestSubmit(); }
      return;
    }
    if (e.ctrlKey || e.metaKey || e.altKey || sta_scrivendo(e.target)) { return; }
    if (e.key === 'Escape' && aiuto && !aiuto.hidden) { aiuto.hidden = true; return; }
    if (e.key === '/' && rapida) { e.preventDefault(); rapida.focus(); rapida.select(); return; }
    if (e.key === '?' && aiuto) { aiuto.hidden = !aiuto.hidden; return; }
    var tasti = { ArrowLeft: 'precedente', ArrowRight: 'successivo', t: 'oggi', n: 'nuovo', g: 'g', e: 'e', c: 'c', d: 'd' };
    var nome = tasti[e.key.length === 1 ? e.key.toLowerCase() : e.key];
    if (nome && clicca(nome)) { e.preventDefault(); }
  });
  if (aiuto) { aiuto.addEventListener('click', function () { aiuto.hidden = true; }); }

  /* ------------------------------------------ notifiche a scomparsa */
  var scatola = $('notifiche');
  var leggiChiuse = function () {
    try { return JSON.parse(sessionStorage.getItem('notifiche-chiuse') || '[]'); } catch (e) { return []; }
  };
  var segnaChiusa = function (chiave) {
    try {
      var c = leggiChiuse();
      if (c.indexOf(chiave) < 0) { c.push(chiave); }
      sessionStorage.setItem('notifiche-chiuse', JSON.stringify(c.slice(-200)));
    } catch (e) { /* senza memoria del browser la notifica ricompare: pazienza */ }
  };
  var mostrate = {};
  // una notifica sparita da sola torna dopo due ore, non a ogni cambio di pagina
  var RIPRESENTA = 2 * 60 * 60 * 1000;
  var vistaDaPoco = function (chiave) {
    try {
      var v = JSON.parse(sessionStorage.getItem('notifiche-viste') || '{}');
      return v[chiave] && (Date.now() - v[chiave]) < RIPRESENTA;
    } catch (e) { return false; }
  };
  var segnaVista = function (chiave) {
    try {
      var v = JSON.parse(sessionStorage.getItem('notifiche-viste') || '{}');
      v[chiave] = Date.now();
      sessionStorage.setItem('notifiche-viste', JSON.stringify(v));
    } catch (e) { /* niente memoria: si ripresenta, pazienza */ }
  };
  var togli = function (el) {
    el.classList.add('uscita');
    setTimeout(function () { if (el.parentNode) { el.parentNode.removeChild(el); } }, 350);
  };
  var notifica = function (n) {
    if (mostrate[n.chiave] || leggiChiuse().indexOf(n.chiave) >= 0 || vistaDaPoco(n.chiave)) { return; }
    mostrate[n.chiave] = true;
    segnaVista(n.chiave);
    var el = document.createElement('div');
    el.className = 'notifica' + (n.livello === 'errore' ? ' errore' : '');
    el.setAttribute('role', 'status');
    var chiudi = document.createElement('button');
    chiudi.type = 'button';
    chiudi.className = 'chiudi-notifica';
    chiudi.setAttribute('aria-label', 'Chiudi');
    chiudi.textContent = '×';
    chiudi.addEventListener('click', function () { segnaChiusa(n.chiave); togli(el); });
    el.appendChild(chiudi);
    var titolo = document.createElement('b');
    titolo.textContent = n.titolo;
    el.appendChild(titolo);
    var testo = document.createElement('a');
    testo.href = n.link;
    testo.textContent = n.testo;
    el.appendChild(testo);
    if (n.azioni && n.azioni.length) {
      var riga = document.createElement('div');
      riga.className = 'azioni-notifica';
      n.azioni.forEach(function (x) {
        var b = document.createElement('button');
        b.type = 'button';
        b.className = 'bottone piccolo';
        b.textContent = x.etichetta;
        b.addEventListener('click', function () {
          fetch(x.url, { method: 'POST', headers: { 'X-Richiesta': 'notifica' } })
            .then(function () { segnaChiusa(n.chiave); togli(el); });
        });
        riga.appendChild(b);
      });
      el.appendChild(riga);
    }
    scatola.appendChild(el);
    // resta finche' non ci si passa sopra; poi sparisce da sola dopo 15 secondi
    var timer = setTimeout(function () { togli(el); }, 15000);
    el.addEventListener('mouseenter', function () { clearTimeout(timer); });
    el.addEventListener('mouseleave', function () { timer = setTimeout(function () { togli(el); }, 6000); });
  };
  var chiediNotifiche = function () {
    if (!scatola) { return; }
    fetch(scatola.getAttribute('data-indirizzo'))
      .then(function (r) { return r.ok ? r.json() : []; })
      .then(function (lista) {
        // al piu' quattro alla volta: prima gli errori, e non si perdono quelle
        // dopo le prime quattro se queste sono gia' state chiuse
        var nuove = lista.filter(function (n) {
          return !(mostrate[n.chiave] || leggiChiuse().indexOf(n.chiave) >= 0 || vistaDaPoco(n.chiave));
        });
        nuove = nuove.filter(function (n) { return n.livello === 'errore'; })
          .concat(nuove.filter(function (n) { return n.livello !== 'errore'; }));
        nuove.slice(0, Math.max(0, 4 - scatola.querySelectorAll('.notifica:not(.uscita)').length)).forEach(notifica);
      })
      .catch(function () {});
  };
  if (scatola) {
    setTimeout(chiediNotifiche, 800);
    setInterval(chiediNotifiche, 5 * 60 * 1000);
  }
})();

/* ---------------------------------------------------------- tema scuro
   La scelta vale per il PC (sta nel browser), come le dimensioni della
   finestra: chiaro, scuro, o come Windows. In stampa il foglio e' sempre chiaro. */
(function () {
  'use strict';
  var CHIAVE = 'gestionale-tema';
  var radice = document.documentElement;
  var leggi = function () { try { return localStorage.getItem(CHIAVE) || 'chiaro'; } catch (e) { return 'chiaro'; } };
  var sistema = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  var carta = document.body && document.body.classList.contains('pagina-stampa');   // fogli da stampare: sempre chiari
  var applica = function (scelta) {
    if (carta) { radice.classList.remove('scuro'); return; }
    radice.classList.toggle('scuro', scelta === 'scuro' || (scelta === 'sistema' && !!sistema && sistema.matches));
  };
  if (sistema && sistema.addEventListener) {
    sistema.addEventListener('change', function () { if (leggi() === 'sistema') { applica('sistema'); } });
  }
  document.querySelectorAll('input[name="tema"]').forEach(function (r) {
    r.checked = r.value === leggi();
    r.addEventListener('change', function () {
      try { localStorage.setItem(CHIAVE, r.value); } catch (e) { /* senza memoria vale finche' la pagina resta aperta */ }
      applica(r.value);
      var n = document.getElementById('stato-tema');
      if (n) { n.textContent = { chiaro: 'Tema chiaro.', scuro: 'Tema scuro.', sistema: 'Segue Windows.' }[r.value] || ''; }
    });
  });
  // un'altra scheda aperta cambia il tema: si allinea anche questa
  window.addEventListener('storage', function (e) { if (e.key === CHIAVE) { applica(leggi()); } });
})();

/* ------------------------------------------- checklist pre-operatoria
   Ogni casella si salva appena spuntata, senza ricaricare la pagina. Se il
   salvataggio non riesce la casella torna com'era e lo si dice. */
(function () {
  'use strict';
  document.querySelectorAll('form.checklist[data-auto]').forEach(function (modulo) {
    var riquadro = modulo.closest('.riquadro-modulo');
    var conto = modulo.querySelector('.conto-checklist') || (riquadro && riquadro.querySelector('.conto-checklist'));
    modulo.querySelectorAll('input[type="checkbox"][name="spunte"]').forEach(function (casella) {
      casella.addEventListener('change', function () {
        var dati = new FormData();
        dati.append('voce', casella.value);
        dati.append('fatto', casella.checked ? '1' : '0');
        casella.disabled = true;
        fetch(modulo.action, { method: 'POST', body: dati, headers: { 'X-Richiesta': 'fetch' } })
          .then(function (r) { if (!r.ok) { throw new Error(r.status); } return r.json(); })
          .then(function (esito) {
            if (conto) {
              conto.textContent = esito.fatte + '/' + esito.totale;
              conto.className = 'conto-checklist ' + (esito.completa ? 'completa' : 'incompleta');
            }
            var etichetta = casella.closest('label');
            if (etichetta) { etichetta.title = casella.checked ? 'fatto il ' + esito.quando : 'da fare'; }
          })
          .catch(function () {
            casella.checked = !casella.checked;
            alert('Checklist non salvata: il programma non risponde. Riprovare.');
          })
          .then(function () { casella.disabled = false; });
      });
    });
  });
})();

/* --------------------------------------------- gruppi del menu e tendine
   Si aprono anche solo passandoci sopra (CSS); qui il clic, che li tiene
   aperti, Esc che li chiude, e aria-expanded per i lettori di schermo. */
(function () {
  'use strict';
  var gruppi = document.querySelectorAll('.menu .gruppo, .gruppo-comandi');
  var chiudiTutti = function (tranne) {
    gruppi.forEach(function (g) {
      if (g === tranne) { return; }
      g.classList.remove('aperto');
      var b = g.querySelector('.apri-gruppo');
      if (b) { b.setAttribute('aria-expanded', 'false'); }
    });
  };
  gruppi.forEach(function (g) {
    var b = g.querySelector('.apri-gruppo');
    if (!b) { return; }
    b.addEventListener('click', function (e) {
      e.preventDefault();
      var apri = !g.classList.contains('aperto');
      chiudiTutti(g);
      g.classList.remove('chiuso');
      g.classList.toggle('aperto', apri);
      b.setAttribute('aria-expanded', apri ? 'true' : 'false');
      if (!apri) { g.classList.add('chiuso'); b.blur(); }
    });
    // chiusa con Esc o con un clic resta chiusa finche' il mouse e il fuoco non escono dal gruppo
    var libera = function () { if (!g.matches(':hover') && !g.contains(document.activeElement)) { g.classList.remove('chiuso'); } };
    g.addEventListener('mouseleave', function () { setTimeout(libera, 0); });
    g.addEventListener('focusout', function () { setTimeout(libera, 0); });
    // scelta una voce, la tendina si chiude (anche se il mouse e' ancora sopra)
    g.querySelectorAll('.tendina a').forEach(function (a) {
      a.addEventListener('click', function () {
        g.classList.remove('aperto'); g.classList.add('chiuso'); b.setAttribute('aria-expanded', 'false');
        if (a.blur) { a.blur(); }
      });
    });
    g.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { chiudiTutti(); g.classList.add('chiuso'); b.focus(); }
      if (e.key === 'ArrowDown' && document.activeElement === b) {
        var primo = g.querySelector('.tendina a:not([hidden])');
        if (primo) { e.preventDefault(); g.classList.add('aperto'); primo.focus(); }
      }
    });
  });
  document.addEventListener('click', function (e) {
    if (!e.target.closest || !e.target.closest('.menu .gruppo, .gruppo-comandi')) { chiudiTutti(); }
  });
})();
