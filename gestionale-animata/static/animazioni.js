/* Animazioni della versione "animata". Tutto quello che fa questo file e'
 * aggiuntivo: se non parte (browser vecchio, errore), il gestionale funziona
 * come l'originale. Le animazioni si spengono da Impostazioni, e da sole con
 * "Mostra animazioni" disattivato in Windows (movimento ridotto). */
(function () {
  'use strict';
  var questoFile = (document.currentScript && document.currentScript.src) || '';
  var radice = document.documentElement;
  var CHIAVE = 'gestionale-animazioni';
  var leggi = function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } };
  var scrivi = function (k, v) { try { localStorage.setItem(k, v); } catch (e) { /* niente memoria: resta com'e' */ } };
  var ridotto = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var attive = function () { return radice.classList.contains('anim'); };

  /* ------------------------------------------ interruttore in Impostazioni */
  document.querySelectorAll('input[name="animazioni"]').forEach(function (r) {
    r.checked = (r.value === 'spente') === (leggi(CHIAVE) === 'spente');
    r.addEventListener('change', function () {
      scrivi(CHIAVE, r.value);
      radice.classList.toggle('anim', r.value !== 'spente');
      var n = document.getElementById('stato-animazioni');
      if (n) { n.textContent = r.value === 'spente' ? 'Animazioni spente.' : 'Animazioni attive.'; }
    });
  });
  if (ridotto) {
    var avviso = document.getElementById('animazioni-ridotte');
    if (avviso) { avviso.hidden = false; }
  }

  /* --------------------------------------------- barra di caricamento */
  var barra = document.createElement('div');
  barra.className = 'caricamento';
  barra.setAttribute('aria-hidden', 'true');
  document.body.appendChild(barra);
  var parte = function () {
    if (!attive()) { return; }
    barra.classList.remove('in-corso');
    void barra.offsetWidth;          // riparte da zero
    barra.classList.add('in-corso');
  };
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href]');
    if (!a || e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey) { return; }
    var h = a.getAttribute('href') || '';
    if (a.target === '_blank' || a.hasAttribute('download') || h.charAt(0) === '#' || /^(mailto|tel|https?:\/\/(?!127\.0\.0\.1|localhost))/i.test(h)) { return; }
    if (/\/(excel|esporta|documenti)\b|\.xlsx|scarti/.test(h)) { return; }       // i download non cambiano pagina
    // il giorno prima e il giorno dopo entrano dal lato giusto
    var verso = a.getAttribute('data-tasto');
    if (verso === 'precedente' || verso === 'successivo') {
      try { sessionStorage.setItem('verso', verso === 'successivo' ? 'destra' : 'sinistra'); } catch (x) { /* pazienza */ }
    }
    parte();
  });
  document.addEventListener('submit', function (e) {
    if (!e.defaultPrevented && !(e.target.target === '_blank')) { setTimeout(parte, 0); }
  });
  window.addEventListener('pageshow', function () { barra.classList.remove('in-corso'); });
  try {
    var verso = sessionStorage.getItem('verso');
    sessionStorage.removeItem('verso');
    if (verso && document.querySelector('table.griglia, table.lista-giorno')) {
      radice.classList.add('verso-' + verso);
      setTimeout(function () { radice.classList.remove('verso-' + verso); }, 600);
    }
  } catch (x) { /* senza memoria: entra dal basso come le altre pagine */ }

  /* -------------------------------------------- onda sui pulsanti */
  document.addEventListener('pointerdown', function (e) {
    if (!attive()) { return; }
    var b = e.target.closest && e.target.closest('.bottone, .passo');
    if (!b) { return; }
    var r = b.getBoundingClientRect();
    var o = document.createElement('span');
    o.className = 'onda';
    o.style.left = (e.clientX - r.left) + 'px';
    o.style.top = (e.clientY - r.top) + 'px';
    b.appendChild(o);
    setTimeout(function () { if (o.parentNode) { o.parentNode.removeChild(o); } }, 600);
  });

  /* --------------------------------------- entrate una dopo l'altra */
  var sfalsa = function (selettore, massimo) {
    document.querySelectorAll(selettore).forEach(function (el, i) {
      el.style.setProperty('--i', Math.min(i, massimo));
    });
  };
  sfalsa('table.griglia thead th', 12);
  // gli appuntamenti della griglia: per ora, poi per stanza, cosi' "scorrono" dall'alto
  document.querySelectorAll('table.griglia tbody tr').forEach(function (tr, riga) {
    tr.querySelectorAll('.voce').forEach(function (v, k) { v.style.setProperty('--i', Math.min(riga + k, 30)); });
  });
  sfalsa('table.mese td, table.settimana tbody td', 40);
  sfalsa('ul.numeri li', 10);
  sfalsa('.barra-dato span', 20);
  sfalsa('.appunti-giorno li', 12);
  sfalsa('.avvisi .avviso', 5);
  sfalsa('.scheda-oggi', 8);
  sfalsa('.scheda-guida', 20);
  sfalsa('ol.passi-guida li', 10);
  sfalsa('ul.righe-oggi li', 10);
  sfalsa('.barra-letti span', 28);
  // la checklist spuntata: il contatore rimbalza (verde quando e' completa)
  if (window.MutationObserver) {
    document.querySelectorAll('.conto-checklist').forEach(function (c) {
      new MutationObserver(function () {
        if (!attive() || c.classList.contains('appena')) { return; }
        c.classList.add('appena');
        setTimeout(function () { c.classList.remove('appena'); }, 1600);
      }).observe(c, { childList: true, characterData: true, subtree: true });
    });
  }
  document.querySelectorAll('table.elenco').forEach(function (t) {
    var righe = Array.prototype.filter.call(t.rows, function (r) { return !r.querySelector('th'); });
    righe.slice(0, 40).forEach(function (r, i) { r.classList.add('entra'); r.style.setProperty('--i', i); });
  });

  /* ------------------------------------------ messaggi: la spunta */
  var SVG = '<svg class="spunta-animata" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9.5"/>' +
            '<path d="M7.5 12.4l3 3 6-6.4"/></svg>';
  document.querySelectorAll('.avvisi .avviso').forEach(function (m) {
    if (m.classList.contains('errore') || m.classList.contains('avviso-giallo')) { return; }
    m.classList.add('fatto');
    m.insertAdjacentHTML('afterbegin', SVG);
  });

  /* ------------------------------ numeri che contano fino al valore */
  if (attive() && !ridotto) {
    document.querySelectorAll('ul.numeri b').forEach(function (b) {
      var testo = b.textContent.trim();
      if (!/^\d{1,6}$/.test(testo)) { return; }           // importi e percentuali restano fermi
      var fine = parseInt(testo, 10);
      if (fine < 2) { return; }
      var durata = Math.min(900, 300 + fine * 8), inizio = null;
      b.style.fontVariantNumeric = 'tabular-nums';
      var passo = function (t) {
        if (inizio === null) { inizio = t; }
        var x = Math.min(1, (t - inizio) / durata);
        b.textContent = String(Math.round(fine * (1 - Math.pow(1 - x, 3))));
        if (x < 1) { requestAnimationFrame(passo); } else { b.textContent = testo; }
      };
      b.textContent = '0';
      requestAnimationFrame(passo);
    });
  }

  /* ------------------------------------- la linea dell'ora attuale */
  var griglia = document.querySelector('table.griglia[data-giorno]');
  if (griglia) {
    var telaio = griglia.closest('.telaio') || griglia.parentNode;
    var oggi = function () {
      var d = new Date();
      return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);
    };
    var linea = null;
    var metti = function () {
      if (griglia.getAttribute('data-giorno') !== oggi()) { if (linea) { linea.remove(); linea = null; } return; }
      var righe = Array.prototype.slice.call(griglia.tBodies[0].rows);
      var orari = righe.map(function (tr) {
        var m = /(\d{1,2}):(\d{2})/.exec((tr.cells[0] && tr.cells[0].textContent) || '');
        return m ? parseInt(m[1], 10) * 60 + parseInt(m[2], 10) : null;
      });
      if (!righe.length || orari.indexOf(null) >= 0) { return; }
      var ora = new Date(), minuti = ora.getHours() * 60 + ora.getMinutes() + ora.getSeconds() / 60;
      var passoFasce = orari.length > 1 ? orari[1] - orari[0] : 30;
      var k = -1;
      for (var i = 0; i < orari.length; i++) { if (orari[i] <= minuti) { k = i; } }
      var ultimaFine = orari[orari.length - 1] + passoFasce;
      if (k < 0 || minuti >= ultimaFine) { if (linea) { linea.remove(); linea = null; } return; }
      var fineRiga = k + 1 < orari.length ? orari[k + 1] : ultimaFine;
      var tr = righe[k];
      var cima = tr.offsetTop + griglia.offsetTop + tr.offsetHeight * (minuti - orari[k]) / (fineRiga - orari[k]);
      if (!linea) {
        linea = document.createElement('div');
        linea.className = 'adesso';
        linea.setAttribute('aria-hidden', 'true');
        linea.appendChild(document.createElement('span'));
        telaio.appendChild(linea);
      }
      // la linea attraversa le stanze; l'ora sta nella colonna degli orari
      var colonnaOre = griglia.tHead ? griglia.tHead.rows[0].cells[0].offsetWidth : 0;
      linea.style.top = cima + 'px';
      linea.style.left = (griglia.offsetLeft + colonnaOre) + 'px';
      linea.style.width = (griglia.offsetWidth - colonnaOre) + 'px';
      linea.style.right = 'auto';
      linea.firstChild.style.left = -(colonnaOre - 3) + 'px';
      linea.firstChild.style.width = (colonnaOre - 12) + 'px';
      linea.firstChild.textContent = ('0' + ora.getHours()).slice(-2) + ':' + ('0' + ora.getMinutes()).slice(-2);
    };
    metti();
    setInterval(metti, 30000);
    window.addEventListener('resize', metti);
  }

  /* ---------------------------------------------- icone animate (Lottie)
     Il lettore (168 KB) e le icone si caricano solo nelle pagine che le usano,
     dal programma stesso: niente internet. Spente le animazioni o con il
     movimento ridotto di Windows non si carica niente e la pagina resta
     quella della versione normale. */
  var cartella = questoFile.replace(/animazioni\.js(\?.*)?$/, 'animazioni/');
  var pronto = null;
  var carica = function (nome) {
    return new Promise(function (ok, ko) {
      var s = document.createElement('script');
      s.src = cartella + nome;
      s.onload = ok;
      s.onerror = ko;
      document.head.appendChild(s);
    });
  };
  var lettore = function () {
    if (!pronto) {
      pronto = Promise.all([carica('lottie_light.min.js'), carica('icone-animate.js')]).then(function () {
        if (!window.lottie || !window.ICONE_ANIMATE) { throw new Error('icone non caricate'); }
        return window.lottie;
      });
    }
    return pronto;
  };
  var conIcone = function () { return attive() && !ridotto && cartella; };
  // un'icona che si disegna una volta; "fine" = cosa fare quando ha finito
  var icona = function (nome, dove, classe, prima, fine) {
    if (!conIcone()) { return null; }
    var box = document.createElement('span');
    box.className = 'icona-animata ' + (classe || '');
    box.setAttribute('aria-hidden', 'true');
    if (prima) { dove.insertBefore(box, dove.firstChild); } else { dove.appendChild(box); }
    lettore().then(function (lottie) {
      var a = lottie.loadAnimation({ container: box, renderer: 'svg', loop: false, autoplay: false,
                                     animationData: JSON.parse(JSON.stringify(window.ICONE_ANIMATE[nome])) });
      a.addEventListener('DOMLoaded', function () { box.classList.add('pronta'); setTimeout(function () { a.play(); }, 250); });
      a.addEventListener('complete', function () { if (fine) { fine(box, a); } });
    }).catch(function () { if (box.parentNode) { box.parentNode.removeChild(box); } });
    return box;
  };

  // pagine vuote: un'icona che si anima, scelta da cosa dice il testo
  document.querySelectorAll('p.vuoto').forEach(function (p) {
    var testo = (p.textContent || '').trim();
    if (!/^(Nessun|Niente)/.test(testo) || testo.length > 160) { return; }
    var nome = 'folder';
    if (/^Niente|telefonata|aspettare|lista d'attesa|da confermare|da chiudere|appunt/i.test(testo)) { nome = 'checkBox'; }
    else if (/appuntament|intervent|posto libero|turno|giorn/i.test(testo)) { nome = 'calendar'; }
    p.classList.add('con-icona');
    icona(nome, p, 'grande', true);
  });

  // importazione riuscita: la spunta che si disegna accanto al titolo
  document.querySelectorAll('.pagina h1').forEach(function (h) {
    if (/completat[ao]$/i.test((h.textContent || '').trim())) { icona('checkmark', h, 'titolo', true); }
  });

  // checklist appena completata: una spunta verde accanto al contatore, poi sparisce
  if (window.MutationObserver) {
    document.querySelectorAll('.conto-checklist').forEach(function (c) {
      var era = c.classList.contains('completa');
      new MutationObserver(function () {
        var ora = c.classList.contains('completa');
        if (ora && !era && !(c.nextSibling && c.nextSibling.classList && c.nextSibling.classList.contains('spunta-checklist'))) {
          var box = icona('checkmark', c.parentNode, 'spunta-checklist', false, function (b) {
            setTimeout(function () { b.classList.add('via'); setTimeout(function () { if (b.parentNode) { b.parentNode.removeChild(b); } }, 400); }, 1400);
          });
          if (box) { c.parentNode.insertBefore(box, c.nextSibling); }
        }
        era = ora;
      }).observe(c, { attributes: true, attributeFilter: ['class'] });
    });
  }

  /* ------------------------------------ attesa lunga: importazione, backup
     Solo se la risposta tarda: le pagine veloci non la mostrano mai. */
  var velo = null, timerVelo = null;
  var LUNGHE = { importa: 1, anteprima: 1, backup_ora: 1 };
  document.addEventListener('submit', function (e) {
    var f = e.target;
    if (e.defaultPrevented || !attive() || f.target === '_blank') { return; }
    var azione = (e.submitter && e.submitter.name === 'azione' && e.submitter.value) ||
                 ((f.querySelector('input[type=hidden][name=azione]') || {}).value || '');
    if (!(f.enctype === 'multipart/form-data' || LUNGHE[azione] || /ripristin/.test(f.action || ''))) { return; }
    clearTimeout(timerVelo);
    timerVelo = setTimeout(function () {
      if (!velo) {
        velo = document.createElement('div');
        velo.className = 'attesa-lunga';
        velo.setAttribute('role', 'status');
        velo.innerHTML = '<div class="riquadro-attesa">' + (ridotto ? '' : '<span class="giro"></span>') +
                         '<b>Un momento…</b><span>' + (azione === 'importa' ? 'Importazione in corso: non chiudere la pagina.' :
                         azione === 'backup_ora' ? 'Backup in corso.' : azione === 'anteprima' ? 'Preparo l\'anteprima.' :
                         f.enctype === 'multipart/form-data' ? 'Caricamento del file.' : 'Il programma sta lavorando.') + '</span></div>';
        document.body.appendChild(velo);
        if (!ridotto) {
          lettore().then(function () {
            var g = velo && velo.querySelector('.giro');
            if (g && window.SPINNER_ATTESA) { g.innerHTML = window.SPINNER_ATTESA; }
          }).catch(function () {});
        }
      }
      velo.classList.add('visibile');
    }, 450);
  });
  window.addEventListener('pageshow', function () {
    clearTimeout(timerVelo);
    if (velo) { velo.classList.remove('visibile'); }
  });

  /* ---------------------- notifiche: il tempo che resta, in fondo */
  var scatola = document.getElementById('notifiche');
  if (scatola && window.MutationObserver) {
    new MutationObserver(function (cambi) {
      cambi.forEach(function (c) {
        Array.prototype.forEach.call(c.addedNodes, function (n) {
          if (!n.classList || !n.classList.contains('notifica')) { return; }
          var t = document.createElement('div');
          t.className = 'tempo-notifica';
          n.appendChild(t);
          if (n.classList.contains('errore')) {
            var titolo = n.querySelector('b');
            if (titolo) { icona('alertCircle', titolo, 'avviso-notifica', true); }
          }
          // uscito il mouse, gestionale.js le da' ancora 6 secondi: la barra riparte da li'
          n.addEventListener('mouseleave', function () {
            var nuova = t.cloneNode();
            nuova.style.animationDuration = '6s';
            t.replaceWith(nuova);
            t = nuova;
          });
        });
      });
    }).observe(scatola, { childList: true });
  }
})();
