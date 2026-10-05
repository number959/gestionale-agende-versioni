/* Guida sullo schermo: un fumetto per volta illumina il punto della pagina
 * dove si fa una cosa. I passi arrivano da /aiuto/<guida>/passi.json, gli
 * stessi della guida con le immagini (guida.py): scritti una volta sola.
 *
 * Si avvia da Aiuto → Guida di questa pagina, dal pulsante "Mostrami sullo
 * schermo" di un articolo (la pagina si apre con ?guida=...), dall'invito che
 * compare la prima volta su una pagina, e al primo avvio dalla pagina Oggi.
 * Frecce o Invio per andare avanti e indietro, Esc per chiudere.
 * Qui c'e' anche la finestra delle videoguide ("Guarda il video"). */
(function () {
  'use strict';
  var corpo = document.body;
  if (!corpo || corpo.classList.contains('pagina-stampa')) { return; }
  var pagina = corpo.getAttribute('data-pagina') || '';
  var radiceAiuto = corpo.getAttribute('data-aiuto') || '/aiuto';
  var leggi = function (k) { try { return JSON.parse(localStorage.getItem(k) || 'null'); } catch (e) { return null; } };
  var scrivi = function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* senza memoria */ } };

  var visibile = function (el) {
    if (!el) { return false; }
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden';
  };
  var trova = function (p) {
    if (!p.sel) { return null; }
    var tutti;
    try { tutti = document.querySelectorAll(p.sel); } catch (e) { return null; }
    for (var i = 0; i < tutti.length; i++) {
      var el = tutti[i];
      if (p.contiene && (el.textContent || '').indexOf(p.contiene) < 0) { continue; }
      if (visibile(el)) { return el; }
    }
    return null;
  };

  /* ----------------------------------------------------------- il giro */
  var giro = null;
  var chiudi = function () {
    if (!giro) { return; }
    ['velo', 'luce', 'fumetto'].forEach(function (k) { if (giro[k] && giro[k].parentNode) { giro[k].parentNode.removeChild(giro[k]); } });
    corpo.classList.remove('giro-in-corso');
    window.removeEventListener('keydown', tasti, true);
    window.removeEventListener('resize', posiziona);
    window.removeEventListener('scroll', posiziona, true);
    var viste = leggi('guida-viste') || {};
    viste[pagina] = 1;
    scrivi('guida-viste', viste);
    if (giro.prima && giro.prima.focus) { try { giro.prima.focus(); } catch (e) { /* pazienza */ } }
    giro = null;
  };
  var tasti = function (e) {
    if (!giro) { return; }
    var k = e.key;
    if (k === 'Escape' || k === 'ArrowRight' || k === 'ArrowLeft' || k === 'Enter') {
      e.preventDefault();
      e.stopPropagation();
      if (e.stopImmediatePropagation) { e.stopImmediatePropagation(); }
      if (k === 'Escape') { chiudi(); } else if (k === 'ArrowLeft') { vai(giro.i - 1); } else { vai(giro.i + 1); }
    }
  };
  var posiziona = function () {
    if (!giro) { return; }
    var p = giro.passi[giro.i], el = p._el, luce = giro.luce, f = giro.fumetto;
    var W = window.innerWidth, H = window.innerHeight, fw = f.offsetWidth, fh = f.offsetHeight;
    if (!el) {
      luce.classList.add('al-centro');
      luce.style.left = (W / 2) + 'px'; luce.style.top = (H / 2) + 'px';
      f.style.left = Math.max(12, (W - fw) / 2) + 'px'; f.style.top = Math.max(12, (H - fh) / 2) + 'px';
      return;
    }
    luce.classList.remove('al-centro');
    var r = el.getBoundingClientRect(), m = 6;
    luce.style.left = (r.left - m) + 'px'; luce.style.top = (r.top - m) + 'px';
    luce.style.width = (r.width + 2 * m) + 'px'; luce.style.height = (r.height + 2 * m) + 'px';
    var top;
    if (r.bottom + m + 12 + fh < H) { top = r.bottom + m + 12; }
    else if (r.top - m - 12 - fh > 0) { top = r.top - m - 12 - fh; }
    else { top = Math.max(12, H - fh - 12); }
    var left = Math.min(Math.max(12, r.left + r.width / 2 - fw / 2), W - fw - 12);
    f.style.left = left + 'px'; f.style.top = top + 'px';
  };
  var vai = function (i) {
    if (!giro) { return; }
    if (i >= giro.passi.length) { chiudi(); return; }
    if (i < 0) { i = 0; }
    giro.i = i;
    var p = giro.passi[i], f = giro.fumetto, ultimo = i === giro.passi.length - 1;
    p._el = trova(p);
    f.innerHTML = '';
    var x = document.createElement('button');
    x.type = 'button'; x.className = 'giro-chiudi'; x.setAttribute('aria-label', 'Chiudi la guida'); x.textContent = '×';
    x.addEventListener('click', chiudi);
    var h = document.createElement('h3'); h.textContent = p.titolo;
    var t = document.createElement('p'); t.textContent = p.testo;
    var piede = document.createElement('div'); piede.className = 'giro-piede';
    var conto = document.createElement('span'); conto.className = 'giro-conto';
    conto.textContent = (i + 1) + ' di ' + giro.passi.length;
    piede.appendChild(conto);
    if (ultimo && giro.articolo) {
      var a = document.createElement('a'); a.className = 'giro-articolo'; a.href = giro.articolo; a.textContent = 'La guida con le immagini';
      piede.appendChild(a);
    }
    if (i > 0) {
      var ind = document.createElement('button'); ind.type = 'button'; ind.className = 'bottone piccolo'; ind.textContent = 'Indietro';
      ind.addEventListener('click', function () { vai(giro.i - 1); });
      piede.appendChild(ind);
    }
    var av = document.createElement('button'); av.type = 'button'; av.className = 'bottone piccolo primario';
    av.textContent = ultimo ? 'Fine' : 'Avanti';
    av.addEventListener('click', function () { vai(giro.i + 1); });
    piede.appendChild(av);
    f.appendChild(x); f.appendChild(h); f.appendChild(t); f.appendChild(piede);
    f.setAttribute('aria-label', 'Guida: ' + giro.titolo + ', passo ' + (i + 1));
    if (p._el) {
      var r = p._el.getBoundingClientRect();
      if (r.top < 60 || r.bottom > window.innerHeight - 40) {
        p._el.scrollIntoView({ block: 'center', behavior: 'auto' });
      }
    }
    posiziona();
    requestAnimationFrame(posiziona);
    setTimeout(posiziona, 450);     // dopo le animazioni d'entrata della pagina
    try { av.focus({ preventScroll: true }); } catch (e) { av.focus(); }
  };
  var avvia = function (dati) {
    chiudi();
    var passi = (dati.passi || []).filter(function (p) { return !p.sel || trova(p); });
    if (!passi.length) { return false; }
    var prima = document.activeElement;
    if (prima && prima.closest && prima.closest('.menu, .gruppo-comandi') && prima.blur) { prima.blur(); prima = null; }
    giro = { passi: passi, i: 0, titolo: dati.titolo || '', articolo: dati.articolo || '', prima: prima };
    giro.velo = document.createElement('div'); giro.velo.className = 'giro-velo';
    giro.luce = document.createElement('div'); giro.luce.className = 'giro-riflettore';
    giro.fumetto = document.createElement('div'); giro.fumetto.className = 'giro-fumetto';
    giro.fumetto.setAttribute('role', 'dialog');
    corpo.appendChild(giro.velo); corpo.appendChild(giro.luce); corpo.appendChild(giro.fumetto);
    corpo.classList.add('giro-in-corso');
    window.addEventListener('keydown', tasti, true);
    window.addEventListener('resize', posiziona);
    window.addEventListener('scroll', posiziona, true);
    vai(0);
    return true;
  };
  var carica = function (slug) {
    return fetch(radiceAiuto + '/' + encodeURIComponent(slug) + '/passi.json')
      .then(function (r) { if (!r.ok) { throw new Error(r.status); } return r.json(); });
  };
  var avviaGuida = function (slug) { return carica(slug).then(avvia).catch(function () { return false; }); };
  window.guidaSulloSchermo = { avvia: avviaGuida, chiudi: chiudi };

  /* ------------------------------------------- le guide di questa pagina */
  var voce = document.querySelector('[data-azione-guida="pagina"]');
  var disponibili = [];
  try { disponibili = JSON.parse(corpo.getAttribute('data-guide') || '[]'); } catch (e) { disponibili = []; }
  disponibili = disponibili.filter(function (g) { return !g.condizione || document.querySelector(g.condizione); });
  var scegli = function () {
    if (disponibili.length === 1) { avviaGuida(disponibili[0].slug); return; }
    // piu' guide per la stessa pagina: si sceglie dal fumetto
    avvia({ titolo: 'Guida di questa pagina', passi: [{ titolo: 'Quale guida?', testo: '' }] });
    var t = giro && giro.fumetto.querySelector('p');
    if (!t) { return; }
    t.textContent = '';
    disponibili.forEach(function (g) {
      var b = document.createElement('button');
      b.type = 'button'; b.className = 'bottone'; b.style.display = 'block'; b.style.margin = '0 0 6px'; b.style.width = '100%';
      b.textContent = g.titolo;
      b.addEventListener('click', function () { avviaGuida(g.slug); });
      t.appendChild(b);
    });
    var av = giro.fumetto.querySelector('.bottone.primario');
    if (av) { av.textContent = 'Chiudi'; }
  };
  if (voce && disponibili.length) {
    voce.hidden = false;
    voce.addEventListener('click', function (e) { e.preventDefault(); scegli(); });
  }
  document.querySelectorAll('[data-azione-guida="tasti"]').forEach(function (a) {
    a.addEventListener('click', function (e) {
      e.preventDefault();
      var box = document.getElementById('aiuto-tasti');
      if (box) { box.hidden = !box.hidden; }
    });
  });

  /* ------------------------------------------------------- videoguide */
  // "Guarda il video" apre il video grande, sopra la pagina, e parte subito;
  // Esc, Chiudi o un clic fuori lo chiudono. Senza questa parte il
  // collegamento apre il file nel lettore del browser.
  var finestraVideo = null;
  var apriVideo = function (indirizzo, titolo) {
    if (typeof HTMLDialogElement === 'undefined') { window.location.href = indirizzo; return; }
    if (!finestraVideo) {
      finestraVideo = document.createElement('dialog');
      finestraVideo.className = 'finestra-video';
      finestraVideo.setAttribute('aria-label', 'Videoguida');
      var testa = document.createElement('div'); testa.className = 'testa-video';
      var nome = document.createElement('b');
      var chiudiV = document.createElement('button'); chiudiV.type = 'button'; chiudiV.className = 'bottone piccolo'; chiudiV.textContent = 'Chiudi';
      chiudiV.addEventListener('click', function () { finestraVideo.close(); });
      testa.appendChild(nome); testa.appendChild(chiudiV);
      var v = document.createElement('video');
      v.controls = true; v.preload = 'auto'; v.setAttribute('playsinline', '');
      finestraVideo.appendChild(testa); finestraVideo.appendChild(v);
      finestraVideo.addEventListener('close', function () { v.pause(); });
      finestraVideo.addEventListener('click', function (e) { if (e.target === finestraVideo) { finestraVideo.close(); } });
      corpo.appendChild(finestraVideo);
    }
    var video = finestraVideo.querySelector('video');
    finestraVideo.querySelector('b').textContent = titolo || 'Videoguida';
    if (video.getAttribute('src') !== indirizzo) { video.setAttribute('src', indirizzo); }
    else { try { video.currentTime = 0; } catch (e) { /* non ancora caricato */ } }
    if (!finestraVideo.open) { finestraVideo.showModal(); }
    var parte = video.play();
    if (parte && parte.catch) { parte.catch(function () { /* il browser vuole un clic su Play: pazienza */ }); }
  };
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[data-video]');
    if (!a || e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) { return; }
    e.preventDefault();
    apriVideo(a.getAttribute('href'), a.getAttribute('data-video'));
  });
  window.videoGuida = { apri: apriVideo };

  /* ------------------------------------ avvio da un articolo (?guida=...) */
  var chiesta = null;
  try {
    var u = new URL(window.location.href);
    chiesta = u.searchParams.get('guida');
    if (chiesta) {
      u.searchParams.delete('guida');
      history.replaceState(null, '', u.pathname + (u.search || '') + u.hash);
    }
  } catch (e) { chiesta = null; }
  if (chiesta && /^[a-z0-9-]{1,40}$/.test(chiesta)) {
    setTimeout(function () { avviaGuida(chiesta); }, 350);
    return;
  }

  /* ------------------------------------------------- primo avvio e inviti */
  var invito = function (testo, etichetta, azione, chiave) {
    var box = document.createElement('div');
    box.className = 'giro-invito';
    box.setAttribute('role', 'status');
    var s = document.createElement('span'); s.textContent = testo;
    var b = document.createElement('button'); b.type = 'button'; b.className = 'bottone piccolo primario'; b.textContent = etichetta;
    var no = document.createElement('button'); no.type = 'button'; no.className = 'giro-no'; no.setAttribute('aria-label', 'Non ora'); no.textContent = '×';
    var togli = function () { if (box.parentNode) { box.parentNode.removeChild(box); } };
    b.addEventListener('click', function () { togli(); azione(); });
    no.addEventListener('click', function () { togli(); chiave(); });
    box.appendChild(s); box.appendChild(b); box.appendChild(no);
    corpo.appendChild(box);
  };
  if (!document.querySelector('nav.menu')) { return; }
  if (pagina === 'cruscotto.oggi' && !leggi('guida-benvenuto')) {
    invito('Prima volta qui? Un giro di un minuto mostra dove sono le cose.', 'Fai il giro', function () {
      scrivi('guida-benvenuto', 1);
      avviaGuida('come-e-fatto');
    }, function () { scrivi('guida-benvenuto', 1); });
    return;
  }
  var viste = leggi('guida-viste') || {};
  if (disponibili.length && !viste[pagina] && !viste['*'] && leggi('guida-benvenuto')) {
    invito('Prima volta su questa pagina?', 'Mostrami come funziona', scegli, function () {
      var v = leggi('guida-viste') || {}; v[pagina] = 1; scrivi('guida-viste', v);
    });
  }
})();
