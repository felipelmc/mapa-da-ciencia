/* A abertura do site, "Céu que se forma" (overrides/home.html). Sem dependências.
 *
 * Os artigos do piloto acendem como estrelas, ano a ano, de 2010 a 2025, e depois se juntam nas constelações dos
 * macrotemas: linhas finas ligam os tópicos de cada um (a árvore geradora mínima entre eles), e os rótulos aparecem.
 * Com movimento reduzido, o céu aparece já formado. Os dados vêm de dados.json (scripts/gerar_pagina.py).
 *
 * `window.__ceu` expõe o estado para os testes: fase, estrelas desenhadas, idioma, histórias.
 */
(function () {
  'use strict';

  var raiz = document.getElementById('ceu-pagina');
  if (!raiz) return;

  var DEMO = raiz.dataset.demo || 'demo/';
  var DOCS = (raiz.dataset.docs || '.').replace(/\/?$/, '/');
  var REDUZIDO = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var CHAVE_LINGUA = 'mapa.pagina.lingua';
  var MS_ANO = 380;
  var MS_FORMA = 2200;

  var estado = { fase: 'carregando', pontos: 0, estrelas: 0, historias: 0, lingua: 'pt', erro: null };
  window.__ceu = estado;

  var lingua = lerLingua();
  var dados = null;

  // ------------------------------------------------------------------ textos em inglês

  var EN = {
    sobretitulo: 'Political science in SciELO Brazil, 2010–2025',
    titulo: 'What does <em>Brazilian</em> political science write about?',
    lide: 'Four thousand articles from ten journals, read by language models running on a laptop: the topics, how they change over time, how research is done and where it is produced. Each point in the sky is an article.',
    chamada_demo: 'Explore the pilot <span aria-hidden="true">→</span>',
    chamada_docs: 'Read the documentation (in Portuguese)',
    ceu_aria: 'The pilot articles as stars, lighting up year by year from 2010 to 2025 and forming the constellations of the macro-themes.',
    artigos: 'articles',
    de_novo: 'Watch again',
    numeros_titulo: 'The pilot in numbers',
    historias_titulo: 'Stories from the pilot',
    historias_lide: 'What the map shows about the political science published in SciELO Brazil. Each story leads to the demo view behind it. Topic labels are in Portuguese, as written by the model.',
    metodo_titulo: 'How it was made',
    metodo_lide: 'Six steps, all with open models running locally. The whole method, with its parameters, is in <a href="' + DOCS + 'explicacoes/metodologia/">Metodologia em uma página</a> (in Portuguese).',
    busca_titulo: 'Look for a subject',
    busca_lide: 'In the labels and keywords of the topics (in Portuguese). The demo also searches the article titles.',
    busca_rotulo: 'Subject',
    busca_placeholder: 'eleições, saúde, China, gênero…',
    citar_titulo: 'How to cite',
    citar_lide: 'If you use mapa-da-ciencia in your research, cite it by its Zenodo DOI, which covers all versions. The Zenodo page also has the DOI of each version.',
    citar_copiar: 'Copy BibTeX',
    creditos_titulo: 'Credits',
    creditos_dados: 'Data',
    creditos_dados_texto: '<a href="https://scielo.org">SciELO</a> (ArticleMeta), <a href="https://openalex.org">OpenAlex</a> (CC0), <a href="https://www.ibge.gov.br">IBGE</a> and <a href="https://www.naturalearthdata.com">Natural Earth</a>. Abstracts appear in the demo only when the article has a Creative Commons license.',
    creditos_modelos: 'Models',
    creditos_modelos_texto: '<code>qwen3-embedding:0.6b</code> and <code>qwen3.5:9b</code>, open models running on <a href="https://ollama.com">Ollama</a>. Validation used a reference coder (Claude), not a person.',
    creditos_projeto: 'Project',
    creditos_projeto_texto: 'Made by Felipe Lamarca, successor to <a href="https://github.com/felipelmc/SciELO-Summarizer">SciELO-Summarizer</a> (SICSS Brazil 2024). Open source, MIT license, at <a href="https://github.com/felipelmc/mapa-da-ciencia">github.com/felipelmc/mapa-da-ciencia</a>. Independent, not affiliated with SciELO, OpenAlex or IBGE.',
    versao: 'Version'
  };

  var CATEGORIAS_EN = {
    quantitativa: 'Quantitative',
    qualitativa: 'Qualitative',
    mista: 'Mixed',
    teorica_ensaistica: 'Theoretical or essay',
    revisao: 'Review'
  };
  var VARIAVEIS_CURTAS = {
    abordagem: ['Abordagem', 'Approach'],
    tecnica_principal: ['Técnica', 'Technique'],
    recorte_geografico: ['Recorte geográfico', 'Geographic scope'],
    brasil_como_caso: ['Brasil como caso', 'Brazil as a case'],
    subarea: ['Subárea', 'Subfield']
  };
  var VARIAVEIS_EN = {
    abordagem: 'Approach',
    tecnica_principal: 'Main technique or data',
    recorte_geografico: 'Geographic scope',
    brasil_como_caso: 'Brazil as a case',
    subarea: 'Subfield'
  };

  function t(pt, en) {
    return lingua === 'en' ? en : pt;
  }

  function num(n, casas) {
    casas = casas || 0;
    return new Intl.NumberFormat(lingua === 'en' ? 'en-US' : 'pt-BR', {
      minimumFractionDigits: casas,
      maximumFractionDigits: casas
    }).format(n);
  }

  function esc(texto) {
    return String(texto).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /** Um ano (ou outro valor curto) dos dados, escapado e sem separador de milhar. */
  function ano(v) {
    return esc(String(v));
  }

  /** Um número, ou um traço quando o dado não existe. */
  function numOuTraco(v, casas) {
    return v === null || v === undefined ? '—' : num(v, casas);
  }

  function demo(rota) {
    return DEMO + '#' + rota;
  }

  function lerLingua() {
    try {
      return window.localStorage.getItem(CHAVE_LINGUA) === 'en' ? 'en' : 'pt';
    } catch (e) {
      return 'pt';
    }
  }

  // ------------------------------------------------------------------ idioma

  var originais = new Map();

  function aplicarLingua() {
    estado.lingua = lingua;
    raiz.setAttribute('lang', lingua === 'en' ? 'en' : 'pt-BR');
    raiz.querySelectorAll('[data-t]').forEach(function (el) {
      if (!originais.has(el)) originais.set(el, el.innerHTML);
      var chave = el.getAttribute('data-t');
      el.innerHTML = lingua === 'en' && EN[chave] ? EN[chave] : originais.get(el);
    });
    raiz.querySelectorAll('[data-t-aria]').forEach(function (el) {
      var chave = 'aria:' + el.getAttribute('data-t-aria');
      if (!originais.has(chave)) originais.set(chave, el.getAttribute('aria-label'));
      el.setAttribute('aria-label', lingua === 'en' ? EN[el.getAttribute('data-t-aria')] : originais.get(chave));
    });
    raiz.querySelectorAll('[data-t-placeholder]').forEach(function (el) {
      var chave = 'ph:' + el.getAttribute('data-t-placeholder');
      if (!originais.has(chave)) originais.set(chave, el.getAttribute('placeholder'));
      el.setAttribute('placeholder', lingua === 'en' ? EN[el.getAttribute('data-t-placeholder')] : originais.get(chave));
    });
    raiz.querySelectorAll('.lingua button').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.lingua === lingua));
    });
    if (dados) {
      mostrarNumeros(false);
      mostrarHistorias();
      mostrarMetodo();
      buscar();
      legendaDoCeu(anoAtual);
    }
  }

  raiz.querySelectorAll('.lingua button').forEach(function (b) {
    b.addEventListener('click', function () {
      lingua = b.dataset.lingua;
      try {
        window.localStorage.setItem(CHAVE_LINGUA, lingua);
      } catch (e) {
        /* sem localStorage: vale só nesta visita */
      }
      aplicarLingua();
    });
  });

  // ------------------------------------------------------------------ o céu

  var canvas = document.getElementById('ceu-canvas');
  var caixa = document.getElementById('ceu');
  var camadaRotulos = document.getElementById('ceu-rotulos');
  var dica = document.getElementById('ceu-dica');
  var replay = document.getElementById('ceu-replay');
  var ctx = canvas.getContext('2d');
  var estrelas = null; // um artigo por estrela: x, y (0..1), ano (índice), macro, tamanho, brilho
  var topicos = []; // as estrelas grandes
  var largura = 0;
  var altura = 0;
  var dpr = 1;
  var margem = 0;
  var inicio = 0;
  var quadro = 0;
  var tempo = 0;
  var fim = 0;
  var anoAtual = 0;
  var sobre = null;
  var cores = null;

  function aleatorio(semente) {
    return function () {
      semente = (semente * 1664525 + 1013904223) >>> 0;
      return semente / 4294967296;
    };
  }

  function prepararCeu() {
    var c = dados.ceu;
    var bin = atob(c.pontos);
    var n = bin.length / 5;
    var sorteio = aleatorio(2010);
    var limites = [];
    var soma = 0;
    c.por_ano.forEach(function (k) {
      soma += k;
      limites.push(soma);
    });
    estrelas = new Array(n);
    var ano = 0;
    for (var i = 0; i < n; i++) {
      var o = i * 5;
      while (i >= limites[ano]) ano++;
      estrelas[i] = {
        x: (bin.charCodeAt(o) | (bin.charCodeAt(o + 1) << 8)) / 65535,
        y: (bin.charCodeAt(o + 2) | (bin.charCodeAt(o + 3) << 8)) / 65535,
        macro: bin.charCodeAt(o + 4) - 1,
        ano: ano,
        raio: 0.55 + Math.pow(sorteio(), 2.2) * 1.1,
        brilho: 0.45 + sorteio() * 0.5,
        atraso: sorteio() * 0.6
      };
    }
    topicos = c.estrelas;
    fim = c.anos.length * MS_ANO + MS_FORMA;
    caixa.style.setProperty('--proporcao', String(c.proporcao));
    estado.estrelas = topicos.length;
  }

  function lerCores() {
    var estilo = getComputedStyle(raiz);
    cores = {
      estrela: estilo.getPropertyValue('--ceu-estrela').trim() || '246, 238, 220',
      brilho: parseFloat(estilo.getPropertyValue('--ceu-brilho')) || 0,
      texto: estilo.getPropertyValue('--ceu-texto').trim(),
      acento: estilo.getPropertyValue('--ceu-acento').trim(),
      macros: dados.ceu.constelacoes.map(function (m) {
        return rgb(m.cor);
      })
    };
  }

  function rgb(hex) {
    var h = hex.replace('#', '');
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
  }

  function medir() {
    var r = caixa.getBoundingClientRect();
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    largura = r.width;
    altura = r.height;
    margem = Math.min(largura, altura) * 0.05;
    canvas.width = Math.round(largura * dpr);
    canvas.height = Math.round(altura * dpr);
  }

  function tela(x, y) {
    var escala = Math.min((largura - 2 * margem), (altura - 2 * margem) / dados.ceu.proporcao);
    var ox = (largura - escala) / 2;
    var oy = (altura - escala * dados.ceu.proporcao) / 2;
    return [ox + x * escala, oy + (y - (1 - dados.ceu.proporcao)) * escala];
  }

  function misturar(a, b, f) {
    return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
  }

  function desenhar(ms) {
    var anos = dados.ceu.anos.length;
    var progressoAnos = Math.min(anos, ms / MS_ANO);
    var forma = Math.max(0, Math.min(1, (ms - anos * MS_ANO) / MS_FORMA));
    var base = cores.estrela.split(',').map(Number);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, largura, altura);

    var desenhadas = 0;
    for (var i = 0; i < estrelas.length; i++) {
      var e = estrelas[i];
      var a = Math.max(0, Math.min(1, (progressoAnos - e.ano - e.atraso * 0.5) * 1.6));
      if (a <= 0) continue;
      desenhadas++;
      var cor = e.macro >= 0 ? misturar(base, cores.macros[e.macro], forma * 0.6) : base;
      var novo = 1 - a;
      var p = tela(e.x, e.y);
      ctx.fillStyle = 'rgba(' + cor[0] + ',' + cor[1] + ',' + cor[2] + ',' + (a * e.brilho * (e.macro >= 0 ? 1 : 1 - forma * 0.45)) + ')';
      ctx.beginPath();
      ctx.arc(p[0], p[1], e.raio * (1 + novo * 1.6), 0, 6.2832);
      ctx.fill();
    }
    estado.pontos = desenhadas;

    if (forma > 0) {
      ctx.lineWidth = 1;
      dados.ceu.constelacoes.forEach(function (m, k) {
        var c = cores.macros[k];
        m.linhas.forEach(function (par, j) {
          var g = Math.max(0, Math.min(1, forma * 1.6 - (j / Math.max(1, m.linhas.length)) * 0.6));
          if (g <= 0) return;
          var a = tela(topicos[par[0]].x, topicos[par[0]].y);
          var b = tela(topicos[par[1]].x, topicos[par[1]].y);
          ctx.strokeStyle = 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + (0.35 + 0.35 * cores.brilho) + ')';
          ctx.beginPath();
          ctx.moveTo(a[0], a[1]);
          ctx.lineTo(a[0] + (b[0] - a[0]) * g, a[1] + (b[1] - a[1]) * g);
          ctx.stroke();
        });
      });
      topicos.forEach(function (tp) {
        var c = cores.macros[tp.macro];
        var p = tela(tp.x, tp.y);
        var r = 1.6 + Math.sqrt(tp.n) * 0.22;
        if (cores.brilho) {
          var halo = ctx.createRadialGradient(p[0], p[1], 0, p[0], p[1], r * 3.2);
          halo.addColorStop(0, 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + 0.35 * forma + ')');
          halo.addColorStop(1, 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',0)');
          ctx.fillStyle = halo;
          ctx.beginPath();
          ctx.arc(p[0], p[1], r * 3.2, 0, 6.2832);
          ctx.fill();
        }
        ctx.fillStyle = 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + forma + ')';
        ctx.beginPath();
        ctx.arc(p[0], p[1], r, 0, 6.2832);
        ctx.fill();
        if (sobre === tp) {
          ctx.strokeStyle = cores.acento;
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.arc(p[0], p[1], r + 4, 0, 6.2832);
          ctx.stroke();
        }
      });
    }

    var ano = Math.min(anos - 1, Math.floor(progressoAnos));
    if (ano !== anoAtual || ms === 0) legendaDoCeu(ano);
  }

  function legendaDoCeu(ano) {
    anoAtual = ano;
    var soma = 0;
    for (var k = 0; k <= ano; k++) soma += dados.ceu.por_ano[k];
    document.getElementById('ceu-ano').textContent = dados.ceu.anos[ano];
    document.getElementById('ceu-contagem').textContent = num(soma);
  }

  function animar(agora) {
    if (!inicio) inicio = agora;
    tempo = agora - inicio;
    desenhar(Math.min(tempo, fim));
    if (tempo < fim) {
      quadro = requestAnimationFrame(animar);
      return;
    }
    formado();
  }

  function formado() {
    tempo = fim;
    estado.fase = 'formado';
    caixa.classList.add('ceu--formado');
    replay.hidden = REDUZIDO;
    replay.disabled = false;
  }

  function comecar() {
    cancelAnimationFrame(quadro);
    caixa.classList.remove('ceu--formado');
    replay.disabled = true; // o botão fica no lugar (e com o foco, se estava), só desabilitado
    if (REDUZIDO) {
      desenhar(fim);
      formado();
      return;
    }
    estado.fase = 'animando';
    inicio = 0;
    quadro = requestAnimationFrame(animar);
  }

  /** Começa quando o céu aparece na tela (no celular, ele fica abaixo do texto). */
  function comecarQuandoVisivel() {
    if (REDUZIDO || !('IntersectionObserver' in window)) {
      comecar();
      return;
    }
    estado.fase = 'esperando';
    desenhar(0);
    var obs = new IntersectionObserver(function (entradas) {
      if (!entradas.some(function (e) { return e.isIntersecting; })) return;
      obs.disconnect();
      comecar();
    }, { threshold: 0.3 });
    obs.observe(caixa);
  }

  function redesenhar() {
    desenhar(estado.fase === 'formado' ? fim : Math.min(tempo, fim));
  }

  function montarRotulos() {
    camadaRotulos.innerHTML = '';
    dados.ceu.constelacoes.forEach(function (m) {
      var a = document.createElement('a');
      a.className = 'ceu__rotulo';
      a.href = demo('/topicos?macro=' + m.id);
      a.textContent = m.rotulo;
      a.style.setProperty('--cor', m.cor);
      a.dataset.x = m.x;
      a.dataset.y = m.y;
      camadaRotulos.appendChild(a);
    });
    posicionarRotulos();
  }

  function posicionarRotulos() {
    var rotulos = Array.prototype.slice.call(camadaRotulos.children);
    rotulos.forEach(function (el) {
      var p = tela(+el.dataset.x, +el.dataset.y);
      // o rótulo fica inteiro dentro do céu, mesmo perto da borda
      var meia = el.offsetWidth / 2;
      el.style.left = Math.min(Math.max(p[0], meia + 2), largura - meia - 2) + 'px';
      el.style.top = Math.min(Math.max(p[1], el.offsetHeight / 2), altura - el.offsetHeight / 2) + 'px';
    });
    // afasta os rótulos que se sobrepõem, de cima para baixo
    rotulos.sort(function (a, b) {
      return parseFloat(a.style.top) - parseFloat(b.style.top);
    });
    for (var i = 0; i < rotulos.length; i++) {
      for (var j = 0; j < i; j++) {
        var ri = rotulos[i].getBoundingClientRect();
        var rj = rotulos[j].getBoundingClientRect();
        var sobrepoe = ri.left < rj.right && rj.left < ri.right && ri.top < rj.bottom && rj.top < ri.bottom;
        if (sobrepoe) rotulos[i].style.top = parseFloat(rotulos[i].style.top) + (rj.bottom - ri.top) + 2 + 'px';
      }
    }
  }

  function topicoPerto(x, y) {
    var melhor = null;
    var menor = 18 * 18;
    topicos.forEach(function (tp) {
      var p = tela(tp.x, tp.y);
      var d = (p[0] - x) * (p[0] - x) + (p[1] - y) * (p[1] - y);
      if (d < menor) {
        menor = d;
        melhor = tp;
      }
    });
    return melhor;
  }

  canvas.addEventListener('pointermove', function (ev) {
    if (estado.fase !== 'formado') return;
    var r = canvas.getBoundingClientRect();
    var tp = topicoPerto(ev.clientX - r.left, ev.clientY - r.top);
    if (tp !== sobre) {
      sobre = tp;
      redesenhar();
    }
    canvas.style.cursor = tp ? 'pointer' : 'default';
    if (!tp) {
      dica.hidden = true;
      return;
    }
    var p = tela(tp.x, tp.y);
    dica.innerHTML =
      '<strong>' + esc(tp.rotulo) + '</strong><span>' + num(tp.n) + ' ' + t('artigos', 'articles') + ' · ' + esc(tp.palavras.slice(0, 3).join(', ')) + '</span>';
    dica.hidden = false;
    var x = Math.min(Math.max(8, p[0] + 12), largura - dica.offsetWidth - 8);
    var y = p[1] + 14 + dica.offsetHeight > altura ? p[1] - dica.offsetHeight - 10 : p[1] + 14;
    dica.style.left = x + 'px';
    dica.style.top = y + 'px';
  });

  canvas.addEventListener('pointerleave', function () {
    sobre = null;
    dica.hidden = true;
    if (estado.fase === 'formado') redesenhar();
  });

  canvas.addEventListener('click', function (ev) {
    if (estado.fase !== 'formado') return;
    // no toque não há "pointermove": o clique procura a estrela no próprio ponto
    var r = canvas.getBoundingClientRect();
    var tp = topicoPerto(ev.clientX - r.left, ev.clientY - r.top);
    if (tp) window.location.href = demo('/topicos?topico=' + encodeURIComponent(tp.id));
  });

  replay.addEventListener('click', comecar);

  // ------------------------------------------------------------------ números

  var numerosAnimados = false;

  function mostrarNumeros(animar) {
    var n = dados.numeros;
    var itens = [
      [n.artigos, 0, t('artigos', 'articles')],
      [n.revistas, 0, t('revistas de ciência política e relações internacionais', 'political science and IR journals')],
      [n.anos, 0, t('anos, de ' + n.periodo[0] + ' a ' + n.periodo[1], 'years, ' + n.periodo[0] + ' to ' + n.periodo[1])],
      [n.topicos, 0, t('tópicos em ' + n.macrotemas + ' macrotemas', 'topics in ' + n.macrotemas + ' macro-themes')],
      [n.instituicoes, 0, t('instituições dos autores', 'author institutions')],
      [n.kappa_mediano, 2, t('kappa mediano entre o modelo e a leitura de referência', 'median kappa between the model and the reference reading')]
    ];
    var lista = document.getElementById('numeros');
    lista.innerHTML = itens
      .filter(function (it) { return it[0] !== null && it[0] !== undefined; })
      .map(function (it) {
        // o número final fica para os leitores de tela; a contagem animada é só visual
        return '<div><dt>' + esc(it[2]) + '</dt><dd><span class="visualmente-oculto">' + num(it[0], it[1]) + '</span><span aria-hidden="true" data-alvo="' + Number(it[0]) + '" data-casas="' + it[1] + '">' + num(it[0], it[1]) + '</span></dd></div>';
      })
      .join('');
    if (animar && !REDUZIDO && !numerosAnimados && 'IntersectionObserver' in window) {
      lista.querySelectorAll('[data-alvo]').forEach(function (dd) {
        dd.textContent = num(0, +dd.dataset.casas);
      });
      var obs = new IntersectionObserver(function (entradas) {
        if (!entradas.some(function (e) { return e.isIntersecting; })) return;
        obs.disconnect();
        numerosAnimados = true;
        contar(lista);
      }, { threshold: 0.4 });
      obs.observe(lista);
    }
  }

  function contar(lista) {
    var t0 = 0;
    var dds = lista.querySelectorAll('[data-alvo]');
    function passo(agora) {
      if (!t0) t0 = agora;
      var f = Math.min(1, (agora - t0) / 1300);
      var e = 1 - Math.pow(1 - f, 3);
      dds.forEach(function (dd) {
        dd.textContent = num(+dd.dataset.alvo * e, +dd.dataset.casas);
      });
      if (f < 1) requestAnimationFrame(passo);
    }
    requestAnimationFrame(passo);
  }

  // ------------------------------------------------------------------ mini-gráficos (SVG)

  function svg(largura, altura, corpo, rotulo) {
    return '<svg viewBox="0 0 ' + largura + ' ' + altura + '" role="img" aria-label="' + esc(rotulo) + '">' + corpo + '</svg>';
  }

  /** O caminho da linha; um valor que falta (null) interrompe o traço. */
  function linha(valores, x, y) {
    var novo = true;
    return valores
      .map(function (v, i) {
        if (v === null || v === undefined) {
          novo = true;
          return '';
        }
        var ponto = (novo ? 'M' : 'L') + x(i).toFixed(1) + ',' + y(v).toFixed(1);
        novo = false;
        return ponto;
      })
      .join('');
  }

  function sparkline(valores, anos, unidade, rotulo) {
    var L = 320, A = 96, m = { e: 4, d: 40, c: 10, b: 18 };
    var max = Math.max.apply(null, valores) * 1.1 || 1;
    var x = function (i) { return m.e + (i / (valores.length - 1)) * (L - m.e - m.d); };
    var y = function (v) { return A - m.b - (v / max) * (A - m.c - m.b); };
    var ultimo = valores[valores.length - 1];
    var caminho = linha(valores, x, y);
    return svg(
      L, A,
      '<path class="grafico-area" d="' + caminho + 'L' + x(valores.length - 1) + ',' + (A - m.b) + 'L' + x(0) + ',' + (A - m.b) + 'Z"/>' +
        '<line class="grafico-eixo" x1="' + m.e + '" x2="' + (L - m.d) + '" y1="' + (A - m.b) + '" y2="' + (A - m.b) + '"/>' +
        '<path class="grafico-linha" d="' + caminho + '"/>' +
        '<circle cx="' + x(valores.length - 1) + '" cy="' + y(ultimo) + '" r="3.5" fill="var(--ceu-acento)"/>' +
        '<text class="grafico-texto grafico-texto--forte" x="' + (x(valores.length - 1) + 7) + '" y="' + (y(ultimo) + 4) + '">' + num(ultimo, 1) + unidade + '</text>' +
        '<text class="grafico-texto" x="' + m.e + '" y="' + (A - 3) + '">' + ano(anos[0]) + '</text>' +
        '<text class="grafico-texto" x="' + (L - m.d) + '" y="' + (A - 3) + '" text-anchor="end">' + ano(anos[anos.length - 1]) + '</text>',
      rotulo
    );
  }

  function colunas(valores, anos, marco, rotulo) {
    var L = 320, A = 96, m = { e: 4, d: 4, c: 8, b: 18 };
    var max = Math.max.apply(null, valores) || 1;
    var passo = (L - m.e - m.d) / valores.length;
    var corpo = valores
      .map(function (v, i) {
        var h = (v / max) * (A - m.c - m.b);
        return '<rect class="grafico-barra' + (anos[i] < marco ? ' grafico-barra--apagada' : '') + '" x="' + (m.e + i * passo + 1).toFixed(1) + '" y="' + (A - m.b - h).toFixed(1) + '" width="' + (passo - 2).toFixed(1) + '" height="' + h.toFixed(1) + '" rx="1.5"/>';
      })
      .join('');
    var xm = m.e + anos.indexOf(marco) * passo;
    return svg(
      L, A,
      corpo +
        '<line class="grafico-limiar" x1="' + xm + '" x2="' + xm + '" y1="' + (m.c - 4) + '" y2="' + (A - m.b + 3) + '"/>' +
        '<text class="grafico-texto" x="' + m.e + '" y="' + (A - 3) + '">' + ano(anos[0]) + '</text>' +
        '<text class="grafico-texto grafico-texto--forte" x="' + (xm + 3) + '" y="' + (A - 3) + '">' + ano(marco) + '</text>' +
        '<text class="grafico-texto" x="' + (L - m.d) + '" y="' + (A - 3) + '" text-anchor="end">' + ano(anos[anos.length - 1]) + '</text>',
      rotulo
    );
  }

  var GRADE_UF = {
    RR: [1, 0], AP: [2, 0],
    AM: [0, 1], PA: [1, 1], MA: [2, 1], CE: [3, 1], RN: [4, 1],
    AC: [0, 2], RO: [1, 2], TO: [2, 2], PI: [3, 2], PB: [4, 2], PE: [5, 2],
    MT: [1, 3], GO: [2, 3], BA: [3, 3], SE: [4, 3], AL: [5, 3],
    MS: [1, 4], DF: [2, 4], MG: [3, 4], ES: [4, 4],
    PR: [1, 5], SP: [2, 5], RJ: [3, 5],
    SC: [1, 6],
    RS: [1, 7]
  };

  function grade(uf, destaques, rotulo) {
    var lado = 26, folga = 3;
    var max = Math.max.apply(null, Object.keys(uf).map(function (k) { return uf[k]; })) || 1;
    var corpo = Object.keys(GRADE_UF)
      .map(function (sigla) {
        var p = GRADE_UF[sigla];
        var v = uf[sigla] || 0;
        var x = 90 + p[0] * (lado + folga), y = p[1] * (lado + folga);
        var forte = destaques.indexOf(sigla) >= 0;
        var opacidade = 0.08 + 0.92 * Math.sqrt(v / max);
        return '<rect x="' + x + '" y="' + y + '" width="' + lado + '" height="' + lado + '" rx="3" fill="var(--ceu-acento)" fill-opacity="' + opacidade.toFixed(2) + '"/>' +
          '<text class="grafico-texto' + (forte ? ' grafico-texto--forte' : '') + '" x="' + (x + lado / 2) + '" y="' + (y + lado / 2 + 3.5) + '" text-anchor="middle"' + (opacidade > 0.5 ? ' style="fill:var(--ceu-sobre-acento)"' : '') + '>' + sigla + '</text>';
      })
      .join('');
    return svg(360, 8 * (lado + folga), corpo, rotulo);
  }

  /** Duas séries em porcentagem (0 a 100); `direita` é a margem para os nomes no fim das linhas. */
  function duasLinhas(a, b, anos, rotulo, nomes, direita) {
    var L = 320, A = 104, m = { e: 4, d: direita || 44, c: 8, b: 18 };
    var x = function (i) { return m.e + (i / (anos.length - 1)) * (L - m.e - m.d); };
    var y = function (v) { return A - m.b - (v / 100) * (A - m.c - m.b); };
    return svg(
      L, A,
      '<line class="grafico-eixo" x1="' + m.e + '" x2="' + (L - m.d) + '" y1="' + (A - m.b) + '" y2="' + (A - m.b) + '"/>' +
        '<path class="grafico-linha grafico-linha--suave" d="' + linha(b, x, y) + '"/>' +
        '<path class="grafico-linha" d="' + linha(a, x, y) + '"/>' +
        '<text class="grafico-texto grafico-texto--forte" x="' + (L - m.d + 6) + '" y="' + (y(a[a.length - 1]) + 4) + '">' + nomes[0] + '</text>' +
        '<text class="grafico-texto" x="' + (L - m.d + 6) + '" y="' + (y(b[b.length - 1]) + 4) + '">' + nomes[1] + '</text>' +
        '<text class="grafico-texto" x="' + m.e + '" y="' + (A - 3) + '">' + ano(anos[0]) + '</text>' +
        '<text class="grafico-texto" x="' + (L - m.d) + '" y="' + (A - 3) + '" text-anchor="end">' + ano(anos[anos.length - 1]) + '</text>',
      rotulo
    );
  }

  function empilhadas(ab, rotulo) {
    var L = 320, alturaBarra = 16, passo = 26, m = 72;
    var cores = ['var(--cat-1)', 'var(--cat-2)', 'var(--cat-3)', 'var(--cat-4)'];
    var corpo = ab.partes
      .map(function (partes, i) {
        var x = m, soma = 0;
        ab.categorias.forEach(function (c) { soma += partes[c.valor]; });
        var barras = ab.categorias
          .map(function (c, k) {
            var w = ((partes[c.valor] / (soma || 1)) * (L - m)).toFixed(1);
            var r = '<rect x="' + x.toFixed(1) + '" y="' + i * passo + '" width="' + w + '" height="' + alturaBarra + '" fill="' + cores[k] + '"/>';
            x += +w;
            return r;
          })
          .join('');
        return '<text class="grafico-texto" x="0" y="' + (i * passo + 12) + '">' + esc(ab.periodos[i]) + '</text>' + barras;
      })
      .join('');
    return svg(L, ab.partes.length * passo - (passo - alturaBarra), corpo, rotulo);
  }

  function legendaCategorias(ab) {
    var cores = ['var(--cat-1)', 'var(--cat-2)', 'var(--cat-3)', 'var(--cat-4)'];
    return '<ul class="grafico-legenda">' + ab.categorias.map(function (c, k) {
      return '<li><i style="background:' + cores[k] + '"></i>' + esc(t(c.rotulo, CATEGORIAS_EN[c.valor] || c.rotulo)) + '</li>';
    }).join('') + '</ul>';
  }

  function barrasKappa(kappas, rotulo) {
    var L = 320, passo = 22, m = 128, h = 13;
    var x = function (k) { return m + Math.max(0, k) * (L - m - 30); };
    var corpo =
      '<defs><pattern id="hachura-kappa" class="grafico-hachura" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="5"/></pattern></defs>' +
      kappas
        .map(function (k, i) {
          var curta = VARIAVEIS_CURTAS[k.variavel];
          var nome = curta ? t(curta[0], curta[1]) : k.rotulo;
          if (nome.length > 20) nome = nome.slice(0, 19) + '…';
          return '<text class="grafico-texto" x="0" y="' + (i * passo + 10) + '">' + esc(nome) + '</text>' +
            '<rect x="' + m + '" y="' + i * passo + '" width="' + (x(k.kappa) - m).toFixed(1) + '" height="' + h + '" fill="' + (k.kappa < 0.6 ? 'url(#hachura-kappa)' : 'var(--ceu-acento)') + '" stroke="var(--ceu-acento)" stroke-width="1"/>' +
            '<text class="grafico-texto grafico-texto--forte" x="' + (x(k.kappa) + 5).toFixed(1) + '" y="' + (i * passo + 10) + '">' + num(k.kappa, 2) + '</text>';
        })
        .join('') +
      '<line class="grafico-limiar" x1="' + x(0.6) + '" x2="' + x(0.6) + '" y1="-4" y2="' + (kappas.length * passo - 4) + '"/>' +
      '<text class="grafico-texto" x="' + (x(0.6) + 3) + '" y="' + (kappas.length * passo + 8) + '">' + num(0.6, 1) + '</text>';
    return svg(L, kappas.length * passo + 10, corpo, rotulo);
  }

  // ------------------------------------------------------------------ histórias

  function cartao(h) {
    return '<article class="historia">' +
      '<p class="historia__tema">' + esc(h.tema) + '</p>' +
      '<p class="historia__numero">' + h.numero + '</p>' +
      '<h3>' + esc(h.titulo) + '</h3>' +
      '<p class="historia__texto">' + h.texto + '</p>' +
      '<div class="historia__grafico">' + h.grafico + '</div>' +
      (h.nota ? '<p class="historia__nota">' + h.nota + '</p>' : '') +
      '<a class="historia__link" href="' + esc(h.link) + '">' + esc(h.chamada) + ' <span aria-hidden="true">→</span></a>' +
      '</article>';
  }

  function mostrarHistorias() {
    var h = dados.historias;
    var anos = dados.ceu.anos;
    var cartoes = [];
    var alta = h.alta;
    if (alta) cartoes.push({
      tema: t('Em alta', 'Rising'),
      numero: '+' + num(alta.pp_periodo, 1) + ' <small>p.p.</small>',
      titulo: alta.rotulo,
      texto: t(
        'O tópico que mais cresceu entre os ' + num(alta.topicos) + ': na tendência ajustada, a participação dele no corpus subiu ' + num(alta.pp_periodo, 1) + ' pontos percentuais de ' + ano(anos[0]) + ' a ' + ano(anos[anos.length - 1]) + ' (' + num(alta.pp_por_ano, 2) + ' por ano); o gráfico mostra a participação observada em cada ano. Outros ' + num(alta.em_alta - 1) + ' estão em alta, e ' + num(alta.em_queda) + ' em queda.',
        'The fastest-growing of the ' + num(alta.topicos) + ' topics: on the fitted trend, its share of the corpus rose ' + num(alta.pp_periodo, 1) + ' percentage points from ' + ano(anos[0]) + ' to ' + ano(anos[anos.length - 1]) + ' (' + num(alta.pp_por_ano, 2) + ' a year); the chart shows the observed share each year. ' + num(alta.em_alta - 1) + ' others are rising, and ' + num(alta.em_queda) + ' falling.'
      ),
      grafico: sparkline(alta.serie, anos, '%', t('Participação observada do tópico no corpus, ano a ano', 'Observed yearly share of the topic in the corpus')),
      link: demo('/topicos?topico=' + encodeURIComponent(alta.topico)),
      chamada: t('Ver nos Tópicos', 'See it in Topics')
    });
    var rec = h.recente;
    if (rec) cartoes.push({
      tema: t('Recente', 'Recent'),
      numero: num(Math.round((100 * rec.depois) / rec.total)) + '<small>%</small>',
      titulo: rec.rotulo,
      texto: t(
        num(rec.depois) + ' dos ' + num(rec.total) + ' artigos deste tópico saíram de ' + ano(rec.desde) + ' em diante: é o assunto mais novo do corpus, entre os tópicos com ao menos 40 artigos.',
        num(rec.depois) + ' of the ' + num(rec.total) + ' articles in this topic came out in ' + ano(rec.desde) + ' or later: the newest subject in the corpus, among topics with at least 40 articles.'
      ),
      grafico: colunas(rec.serie, anos, rec.desde, t('Artigos do tópico por ano', 'Articles in the topic per year')),
      link: demo('/topicos?topico=' + encodeURIComponent(rec.topico)),
      chamada: t('Ver nos Tópicos', 'See it in Topics')
    });
    var geo = h.geografia;
    if (geo) cartoes.push({
      tema: t('Onde se produz', 'Where'),
      numero: num(geo.pct_tres) + '<small>%</small>',
      titulo: t(geo.tres.join(', ').replace(/, ([^,]*)$/, ' e $1'), geo.tres.join(', ').replace(/, ([^,]*)$/, ' and $1')),
      texto: t(
        'Três unidades da federação respondem por ' + num(geo.pct_tres) + '% da produção brasileira do corpus, em contagem fracionária pelas afiliações dos autores. Autores no Brasil somam ' + num(geo.pct_brasil) + '% da produção com país conhecido.',
        'Three Brazilian states account for ' + num(geo.pct_tres) + '% of the Brazilian output in the corpus, counted fractionally by author affiliation. Authors in Brazil account for ' + num(geo.pct_brasil) + '% of the output with a known country.'
      ),
      grafico: grade(geo.uf, geo.tres, t('Participação de cada UF na produção brasileira, num cartograma em grade', 'Share of each state in Brazilian output, as a tile grid')),
      link: demo('/geografia'),
      chamada: t('Ver na Geografia', 'See it in Geography')
    });
    var col = h.colaboracao;
    if (col) {
      var p0 = esc(col.periodos[0]), p1 = esc(col.periodos[1]);
      var comUfs = col.ufs !== null && col.ufs !== undefined;
      var pct = function (v) { return numOuTraco(v) + '%'; };
      var exterior = !comUfs ? '' : col.exterior_difere
        ? t(', e os com autores no Brasil e no exterior, de ' + pct(col.exterior[0]) + ' para ' + pct(col.exterior[1]),
          ', and those with authors both in Brazil and abroad, from ' + pct(col.exterior[0]) + ' to ' + pct(col.exterior[1]))
        : t('; os com autores no Brasil e no exterior mudaram pouco, de ' + pct(col.exterior[0]) + ' para ' + pct(col.exterior[1]),
          '; those with authors both in Brazil and abroad changed little, from ' + pct(col.exterior[0]) + ' to ' + pct(col.exterior[1]));
      var sv = col.serie_varios, su = col.serie_ufs || [];
      var anoIni = ano(col.anos[0]), anoFim = ano(col.anos[col.anos.length - 1]);
      var rotuloCol = t(
        'Artigos com mais de um autor, por ano: ' + pct(sv[0]) + ' em ' + anoIni + ' e ' + pct(sv[sv.length - 1]) + ' em ' + anoFim + (comUfs ? '. Com autores de mais de uma UF: ' + pct(su[0]) + ' e ' + pct(su[su.length - 1]) : '') + '.',
        'Articles with more than one author, per year: ' + pct(sv[0]) + ' in ' + anoIni + ' and ' + pct(sv[sv.length - 1]) + ' in ' + anoFim + (comUfs ? '. With authors in more than one state: ' + pct(su[0]) + ' and ' + pct(su[su.length - 1]) : '') + '.'
      );
      cartoes.push({
        tema: t('Colaboração', 'Collaboration'),
        numero: num(col.varios[0]) + '% → ' + num(col.varios[1]) + '<small>%</small>',
        titulo: t('Mais artigos em coautoria', 'More co-authored articles'),
        texto: t(
          'Em ' + p0 + ', ' + pct(col.varios[0]) + ' dos artigos tinham mais de um autor; em ' + p1 + ', ' + pct(col.varios[1]) + '.' + (comUfs ? ' Os com autores de mais de uma UF foram de ' + pct(col.ufs[0]) + ' para ' + pct(col.ufs[1]) + exterior + '.' : ''),
          'In ' + p0 + ', ' + pct(col.varios[0]) + ' of articles had more than one author; in ' + p1 + ', ' + pct(col.varios[1]) + '.' + (comUfs ? ' Those with authors in more than one Brazilian state went from ' + pct(col.ufs[0]) + ' to ' + pct(col.ufs[1]) + exterior + '.' : '')
        ),
        grafico: comUfs
          ? duasLinhas(sv, su, col.anos, rotuloCol, [t('2+ autores', '2+ authors'), t('2+ UFs', '2+ states')], 72)
          : sparkline(sv, col.anos, '%', rotuloCol),
        // os denominadores: a autoria conhecida e, nas UFs, a afiliação localizada (menos artigos nos primeiros anos)
        nota: t(
          'Entram na conta os artigos com autoria conhecida (' + num(col.autoria[0]) + ' em ' + p0 + ' e ' + num(col.autoria[1]) + ' em ' + p1 + ')' + (comUfs ? ' e, nas UFs e no exterior, os com afiliação localizada, numa UF ou fora do Brasil (' + num(col.localizados[0]) + ' e ' + num(col.localizados[1]) + ')' : '') + '.',
          'Counted: articles with known authorship (' + num(col.autoria[0]) + ' in ' + p0 + ' and ' + num(col.autoria[1]) + ' in ' + p1 + ')' + (comUfs ? ' and, for states and abroad, those with a located affiliation, in a state or outside Brazil (' + num(col.localizados[0]) + ' and ' + num(col.localizados[1]) + ')' : '') + '.'
        ),
        link: demo('/redes?rede=' + (comUfs ? 'estados' : 'coautoria')),
        chamada: t('Ver nas Redes', 'See it in Networks')
      });
    }
    var en = h.ingles;
    // nas outras oito, a faixa dos últimos sete anos: o último ano sozinho parece uma alta
    var recentes = en ? en.outras.slice(-7) : [];
    var desdeOutras = anos[anos.length - recentes.length];
    var faixaMin = Math.min.apply(null, recentes), faixaMax = Math.max.apply(null, recentes);
    if (en) cartoes.push({
      tema: t('Idioma', 'Language'),
      numero: '100<small>%</small>',
      titulo: t('Relações internacionais em inglês', 'International relations in English'),
      texto: t(
        'Desde ' + ano(en.desde) + ', a <em>Contexto Internacional</em> e a <em>RBPI</em> publicam todos os artigos em inglês; antes, eram ' + num(en.pct_antes) + '%. Nas outras oito revistas, entre elas a <em>BPSR</em>, que publica só em inglês, o inglês ficou entre ' + num(faixaMin) + '% e ' + num(faixaMax) + '% de ' + ano(desdeOutras) + ' a ' + ano(anos[anos.length - 1]) + '.',
        'Since ' + ano(en.desde) + ', <em>Contexto Internacional</em> and <em>RBPI</em> have published every article in English, up from ' + num(en.pct_antes) + '% before. In the other eight journals, which include the English-only <em>BPSR</em>, English stayed between ' + num(faixaMin) + '% and ' + num(faixaMax) + '% from ' + ano(desdeOutras) + ' to ' + ano(anos[anos.length - 1]) + '.'
      ),
      grafico: duasLinhas(en.ri, en.outras, anos, t('Artigos em inglês por ano, em porcentagem', 'Articles in English per year, in percent'), [t('RI', 'IR'), t('outras', 'others')]),
      link: demo('/topicos?revistas=cint,rbpi'),
      chamada: t('Ver as duas revistas', 'See both journals')
    });
    if (h.abordagem) {
      var ab = h.abordagem;
      var d = ab.destaque;
      var nomeD = t(d.rotulo, CATEGORIAS_EN[d.valor] || d.rotulo);
      var nomeMinusculo = esc(nomeD.toLowerCase());
      var primeiro = esc(ab.periodos[0]), ultimo = esc(ab.periodos[ab.periodos.length - 1]);
      var soma = ab.n.reduce(function (a, b) { return a + b; }, 0);
      // a mudança, mais do que os níveis: o modelo erra os níveis de algumas categorias (veja o viés abaixo)
      var caiu = d.para < d.de, razao = d.de ? d.para / d.de : 1;
      // "pela metade" só perto da metade: 47% a 53% do valor inicial; "quase", de 53% a 56% (uma queda de 44% a 47%)
      var mudanca = !caiu ? t('subiu', 'rose')
        : razao >= 0.47 && razao <= 0.53 ? t('caiu pela metade', 'halved')
        : razao > 0.53 && razao <= 0.56 ? t('caiu quase pela metade', 'almost halved')
        : razao >= 0.4 && razao < 0.47 ? t('caiu mais da metade', 'fell by more than half')
        : t('caiu', 'fell');
      // o viés medido na validação do piloto (claude-opus × qwen3.5:9b, amostra de 200): o modelo marca "teórica" em
      // 40% dos resumos, e a referência em 27%; por período, a queda aparece nas duas leituras
      var vies = d.valor === 'teorica_ensaistica' && caiu ? t(
        ' Na amostra de validação, o modelo marca “teórica” em 40% dos resumos, e a referência em 27%; a queda aparece nas duas leituras.',
        ' In the validation sample, the model labels 40% of the abstracts “theoretical”, and the reference 27%; the fall shows up in both readings.'
      ) : '';
      cartoes.push({
        tema: t('Como se pesquisa', 'How research is done'),
        numero: num(d.de) + '% → ' + num(d.para) + '<small>%</small>',
        titulo: nomeD,
        texto: t(
          'A abordagem que mais mudou: ' + nomeMinusculo + ', que ' + mudanca + ', de ' + num(d.de) + '% dos artigos em ' + primeiro + ' para ' + num(d.para) + '% em ' + ultimo + ', segundo o modelo local, nos ' + num(soma) + ' resumos com a abordagem informada.' + vies,
          'The approach that changed the most: ' + nomeMinusculo + ', which ' + mudanca + ', from ' + num(d.de) + '% of articles in ' + primeiro + ' to ' + num(d.para) + '% in ' + ultimo + ', according to the local model, in the ' + num(soma) + ' abstracts with an approach recorded.' + vies
        ),
        grafico: empilhadas(ab, t('Abordagem dos artigos por período', 'Approach of the articles by period')) + legendaCategorias(ab),
        link: demo('/classificacao?variavel=abordagem'),
        chamada: t('Ver na Classificação', 'See it in Classification')
      });
    }
    var val = h.validacao;
    if (val && val.kappas.length) {
      var ordenados = val.kappas.slice().sort(function (a, b) { return a.kappa - b.kappa; });
      var menor = ordenados[0], maior = ordenados[ordenados.length - 1];
      cartoes.push({
        tema: t('Validação', 'Validation'),
        numero: '<small>κ</small> ' + num(val.mediana, 2),
        titulo: t('O modelo contra uma leitura de referência', 'The model against a reference reading'),
        texto: t(
          'Em ' + num(val.n) + ' artigos codificados às cegas por um codificador de referência (' + esc(val.referencia) + '), o kappa vai de ' + num(menor.kappa, 2) + ' em “' + esc(menor.rotulo) + '” a ' + num(maior.kappa, 2) + ' em “' + esc(maior.rotulo) + '”. Com hachura, abaixo de 0,6: a variável pede cuidado.',
          'On ' + num(val.n) + ' articles coded blind by a reference coder (' + esc(val.referencia) + '), kappa ranges from ' + num(menor.kappa, 2) + ' for “' + esc(VARIAVEIS_EN[menor.variavel] || menor.rotulo) + '” to ' + num(maior.kappa, 2) + ' for “' + esc(VARIAVEIS_EN[maior.variavel] || maior.rotulo) + '”. Hatched, below 0.6: handle with care.'
        ),
        grafico: barrasKappa(val.kappas, t('Kappa de Cohen por variável', "Cohen's kappa by variable")),
        link: demo('/validacao'),
        chamada: t('Ver a Validação', 'See the Validation')
      });
    }
    document.getElementById('historias').innerHTML = cartoes.map(cartao).join('');
    estado.historias = cartoes.length;
  }

  // ------------------------------------------------------------------ método

  function mostrarMetodo() {
    var n = dados.numeros;
    var passos = [
      [t('Coleta', 'Collection'), num(n.artigos), t('artigos de ' + n.revistas + ' revistas', 'articles from ' + n.revistas + ' journals'),
        t('Listados na ArticleMeta do SciELO e casados com o OpenAlex pelo DOI; os e-mails dos autores ficam de fora.', "Listed in SciELO's ArticleMeta and matched with OpenAlex by DOI; author e-mails are left out."), 'explicacoes/fontes/'],
      [t('Embeddings', 'Embeddings'), num(1024), t('números por resumo', 'numbers per abstract'),
        t('Título e resumo viram um vetor no qwen3-embedding, rodando no Ollama: artigos parecidos ficam perto.', 'Title and abstract become a vector in qwen3-embedding, running on Ollama: similar articles end up close.'), 'explicacoes/topicos/#2-embeddings'],
      [t('Tópicos', 'Topics'), num(n.topicos), n.ari === null || n.ari === undefined ? t('tópicos', 'topics') : t('tópicos, ARI ' + num(n.ari, 2), 'topics, ARI ' + num(n.ari, 2)),
        t('UMAP e HDBSCAN agrupam os vizinhos; os grupos se mantêm entre sementes diferentes.', 'UMAP and HDBSCAN group the neighbours; the groups hold across different seeds.'), 'explicacoes/topicos/'],
      [t('Rótulos', 'Labels'), num(n.macrotemas), t('macrotemas', 'macro-themes'),
        t('Um modelo local lê as palavras-chave e os títulos de cada tópico e escreve rótulo e descrição em português.', 'A local model reads the keywords and titles of each topic and writes a label and description in Portuguese.'), 'explicacoes/topicos/#11-rotulos'],
      [t('Classificação', 'Classification'), numOuTraco(n.evidencia_literal, 1) + (n.evidencia_literal === null || n.evidencia_literal === undefined ? '' : '%'), t('das evidências, literais', 'of the evidence, verbatim'),
        t('Cada resumo responde ao codebook, e cada resposta cita o trecho que a justifica, conferido no texto.', 'Each abstract answers the codebook, and each answer quotes the passage that supports it, checked against the text.'), 'explicacoes/classificacao/'],
      [t('Validação', 'Validation'), 'κ ' + numOuTraco(n.kappa_mediano, 2), t('mediano', 'median'),
        t('Uma amostra codificada às cegas mede a concordância, variável por variável.', 'A sample coded blind measures agreement, variable by variable.'), 'explicacoes/validacao/']
    ];
    document.getElementById('metodo').innerHTML = passos
      .map(function (p) {
        return '<li><h3>' + esc(p[0]) + '</h3><span class="metodo__numero">' + p[1] + ' <small>' + esc(p[2]) + '</small></span><p>' + esc(p[3]) + '</p><a href="' + DOCS + p[4] + '">' + t('Como funciona', 'How it works') + '</a></li>';
      })
      .join('');
  }

  // ------------------------------------------------------------------ busca

  var campo = document.getElementById('busca-campo');
  var resultados = document.getElementById('busca-resultados');

  function dobrar(texto) {
    return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  }

  function marcar(texto, termo) {
    var i = dobrar(texto).indexOf(termo);
    if (i < 0 || !termo) return esc(texto);
    return esc(texto.slice(0, i)) + '<mark>' + esc(texto.slice(i, i + termo.length)) + '</mark>' + esc(texto.slice(i + termo.length));
  }

  function buscar() {
    if (!dados) return;
    var q = campo.value.trim();
    var termo = dobrar(q);
    if (!termo) {
      resultados.innerHTML = '';
      return;
    }
    // a raiz (sem as duas últimas letras) acha o plural e o feminino: "eleição" acha "eleições"
    var raizTermo = termo.length >= 5 ? termo.slice(0, termo.length - 2) : termo;
    var macros = dados.ceu.constelacoes;
    var achados = topicos
      .map(function (tp) {
        var r = dobrar(tp.rotulo);
        var p = dobrar(tp.palavras.join(' '));
        var nota = r.indexOf(termo) === 0 ? 5 : r.indexOf(termo) > 0 ? 4 : p.indexOf(termo) >= 0 ? 3 : r.indexOf(raizTermo) >= 0 ? 2 : p.indexOf(raizTermo) >= 0 ? 1 : 0;
        return { tp: tp, nota: nota };
      })
      .filter(function (a) { return a.nota > 0; })
      .sort(function (a, b) { return b.nota - a.nota || b.tp.n - a.tp.n; })
      .slice(0, 6);
    var itens = achados.map(function (a) {
      var tp = a.tp;
      var m = a.nota >= 3 ? termo : raizTermo;
      return '<li><a href="' + demo('/topicos?topico=' + tp.id) + '">' + marcar(tp.rotulo, m) + '</a><small>' + esc(macros[tp.macro].rotulo) + ' · ' + num(tp.n) + ' ' + t('artigos', 'articles') + ' · ' + marcar(tp.palavras.slice(0, 4).join(', '), m) + '</small></li>';
    });
    if (!achados.length) itens.push('<li><small>' + t('Nenhum tópico com esse termo.', 'No topic with that term.') + '</small></li>');
    itens.push('<li><a href="' + demo('/mapa?busca=' + encodeURIComponent(q)) + '">' + t('Procurar «' + esc(q) + '» nos títulos, na demo', 'Search the titles for “' + esc(q) + '” in the demo') + ' <span aria-hidden="true">→</span></a></li>');
    resultados.innerHTML = itens.join('');
  }

  campo.addEventListener('input', buscar);

  // ------------------------------------------------------------------ citação

  var copiar = document.getElementById('citar-copiar');
  if (copiar) {
    var bibtex = document.getElementById('citar-bibtex');
    var aviso = document.getElementById('citar-aviso');
    var selecionar = function () {
      var faixa = document.createRange();
      faixa.selectNodeContents(bibtex);
      var sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(faixa);
      aviso.textContent = t('Texto selecionado: copie com Ctrl+C (⌘C no Mac).', 'Text selected: copy it with Ctrl+C (⌘C on a Mac).');
    };
    copiar.addEventListener('click', function () {
      if (!navigator.clipboard) return selecionar();
      navigator.clipboard.writeText(bibtex.textContent).then(function () {
        aviso.textContent = t('BibTeX copiado.', 'BibTeX copied.');
      }, selecionar);
    });
  }

  // ------------------------------------------------------------------ começo

  function iniciar(d) {
    dados = d;
    prepararCeu();
    lerCores();
    medir();
    montarRotulos();
    aplicarLingua();
    mostrarNumeros(true);
    comecarQuandoVisivel();

    if ('ResizeObserver' in window) {
      var espera = 0;
      new ResizeObserver(function () {
        clearTimeout(espera);
        espera = setTimeout(function () {
          medir();
          posicionarRotulos();
          redesenhar();
        }, 80);
      }).observe(caixa);
    }
    // o tema do Material (claro/escuro) muda as cores do céu
    new MutationObserver(function () {
      lerCores();
      redesenhar();
    }).observe(document.body, { attributes: true, attributeFilter: ['data-md-color-scheme'] });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(posicionarRotulos);
  }

  fetch(raiz.dataset.dados)
    .then(function (r) {
      if (!r.ok) throw new Error(r.status + ' ' + r.statusText);
      return r.json();
    })
    .then(iniciar)
    .catch(function (e) {
      estado.fase = 'erro';
      estado.erro = String(e);
      aplicarLingua();
      document.getElementById('historias').textContent = t(
        'Não foi possível carregar os dados desta página. A demo e a documentação continuam nos links acima.',
        'The data for this page could not be loaded. The demo and the documentation are still at the links above.'
      );
    });
})();
