<script lang="ts" module>
	/** Uma aresta do desenho por faixa de peso: opacidade e espessura (a faixa 0 é a de quem saiu do recorte). */
	export const TRACO_DAS_FAIXAS = [
		{ alfa: 0.07, largura: 0.5 },
		{ alfa: 0.16, largura: 0.6 },
		{ alfa: 0.28, largura: 0.9 },
		{ alfa: 0.45, largura: 1.3 },
		{ alfa: 0.7, largura: 1.9 }
	] as const;

	export interface RotuloGrafo {
		id: string;
		texto: string;
		/** Posição no desenho (as mesmas coordenadas dos nós): o meio da comunidade e o nó mais alto dela; o rótulo fica
		 * logo acima. */
		x: number;
		y: number;
		/** A comunidade do rótulo: clicar nele a escolhe. */
		comunidade: number;
	}

	/** O estado da interação, para a depuração e os testes (`__redesDebug.estadoDoGrafo`). */
	export interface EstadoGrafo {
		vista: { k: number; dx: number; dy: number };
		/** Nós acesos pelo destaque (vizinhança ou comunidade); 0 sem destaque. */
		destacados: number;
		/** Nós arrastados para fora do lugar. */
		movidos: number;
		/** Os nomes de nós escritos no desenho agora. */
		nomes: string[];
		telaCheia: boolean;
	}
</script>

<script lang="ts">
	/**
	 * Um grafo em canvas 2D: a rede de coautoria ou a de instituições, com o desenho que o Python calculou para o
	 * corpus inteiro. O recorte não move nada: quem sai dele fica esmaecido, e as arestas do recorte ganham a faixa de
	 * opacidade do peso que têm nele. Canvas, e não SVG, porque o piloto tem milhares de nós e arestas.
	 *
	 * O componente é controlado (o nó aberto e a comunidade em destaque vêm da URL, em `ModoGrafo`); o zoom, o arrasto
	 * e os nós movidos são só daqui. A interação:
	 * - passar o mouse num nó acende ele, os vizinhos e as arestas entre eles, e escreve o nome dos vizinhos;
	 * - o clique abre o cartão (`aoEscolher`); o nó aberto fica aceso, e "Enquadrar" leva o zoom até a vizinhança;
	 * - uma comunidade escolhida (no seletor da barra do grafo ou na legenda) fica acesa e enquadrada;
	 * - arrastar um nó o move (só na tela: "Reiniciar" devolve o desenho); arrastar o fundo move a tela;
	 * - Ctrl/⌘ + roda, a pinça do trackpad ou de dois dedos, os botões e o clique duplo aproximam (a roda sozinha rola a
	 *   página, a não ser em tela cheia); com o grafo em foco, `+`, `−` e `0`, as setas movem e Esc solta o destaque;
	 * - com zoom, aparecem os nomes dos nós maiores, sem se cobrirem.
	 *
	 * Os rótulos ficam num SVG por cima, que deixa passar o mouse e o toque.
	 */
	import { quadtree, type Quadtree } from 'd3-quadtree';
	import { onMount, untrack } from 'svelte';
	import { tema } from '$lib/estado/tema.svelte';
	import Dica from '$lib/graficos/Dica.svelte';
	import { adjacencia, enquadrar, nomesNoZoom, paraDesenho, semColisao, vizinhanca, type Vista } from './interacao';

	interface Props {
		/** Posição de cada nó no desenho; `NaN` fica fora. */
		x: Float64Array;
		y: Float64Array;
		/** Raio de cada nó, em pixels. */
		raio: Float32Array;
		/** Cor de cada nó (`null` = a neutra das comunidades pequenas). */
		cor: (string | null)[];
		/** 1 para os nós com documentos no recorte. */
		ativo: Uint8Array;
		arestas: { n: number; a: Int32Array; b: Int32Array };
		/** Faixa de cada aresta no recorte (0 = fora dela). */
		faixas: Uint8Array;
		/** A comunidade de cada nó (−1 nas pequenas). */
		comunidade: Int32Array;
		selecionado: number | null;
		/** A comunidade em destaque, ou `null`. */
		comunidadeEscolhida: number | null;
		rotulos: RotuloGrafo[];
		nomeDo: (i: number) => string;
		dica: (i: number) => string[];
		aoEscolher: (i: number | null) => void;
		aoEscolherComunidade: (c: number | null) => void;
		/** As comunidades do seletor na barra do grafo (as maiores, com o rótulo inteiro). */
		opcoesComunidade?: { id: number; rotulo: string }[];
		/** O elemento que vai para a tela cheia (o grafo com o cartão ao lado); sem ele, só o grafo. */
		alvoTelaCheia?: HTMLElement | null;
		/** Descrição para leitores de tela. */
		rotulo: string;
		/** Chamado depois do primeiro desenho, com o tempo desde a montagem. */
		aoDesenhar?: (ms: number) => void;
	}

	let {
		x,
		y,
		raio,
		cor,
		ativo,
		arestas,
		faixas,
		comunidade,
		selecionado,
		comunidadeEscolhida,
		rotulos,
		nomeDo,
		dica,
		aoEscolher,
		aoEscolherComunidade,
		opcoesComunidade = [],
		alvoTelaCheia = null,
		rotulo,
		aoDesenhar
	}: Props = $props();

	const MARGEM = 28;
	const ZOOM = { min: 0.5, max: 40, passo: 1.6 };
	const MOVER = 60; // px por toque nas setas

	let grafo: HTMLDivElement;
	let canvas: HTMLCanvasElement;
	let largura = $state(0);
	let altura = $state(0);
	let vista = $state<Vista>({ k: 1, dx: 0, dy: 0 });
	let sobre = $state<number | null>(null);
	let posMouse = $state<{ x: number; y: number } | null>(null);
	let arrastando = $state(false);
	let telaCheia = $state(false);
	let podeTelaCheia = $state(false);
	/** Aviso de "Ctrl + roda para aproximar", depois de uma roda sozinha sobre o grafo. */
	let avisoRoda = $state(false);
	/** Nós arrastados: posição no desenho (as coordenadas do Python), por índice. */
	let movidos = $state.raw(new Map<number, [number, number]>());
	/** O nó escolhido por um clique no grafo (e não pela busca ou pelo link): o zoom não pula para ele. */
	let escolhidoPeloGrafo: number | null = null;
	/** O nó aberto antes de a área ter tamanho (um link aberto direto): enquadrado assim que ela for medida. */
	let enquadrarQuandoMedir: number | null = null;
	/** O nó aberto que ainda não está no desenho (numa dupla escondida): enquadrado quando aparecer. */
	let enquadrarQuandoAparecer: number | null = null;
	/** Como veio a última interação com o grafo: o cartão só recebe o foco quando foi pelo teclado. */
	let origem = $state<'ponteiro' | 'teclado'>('ponteiro');
	const t0 = performance.now();
	let desenhouUmaVez = false;

	// ---- do desenho (coordenadas do Python) para a base em pixels, com a mesma escala nos dois eixos
	// (o enquadramento é o do desenho original: mover um nó não reenquadra)
	const ajuste = $derived.by(() => {
		let [x0, x1, y0, y1] = [Infinity, -Infinity, Infinity, -Infinity];
		for (let i = 0; i < x.length; i += 1) {
			if (!Number.isFinite(x[i]) || !Number.isFinite(y[i])) continue;
			x0 = Math.min(x0, x[i]);
			x1 = Math.max(x1, x[i]);
			y0 = Math.min(y0, y[i]);
			y1 = Math.max(y1, y[i]);
		}
		if (!Number.isFinite(x0)) return { s: 1, cx: 0, cy: 0 };
		const s = Math.min((largura - 2 * MARGEM) / (x1 - x0 || 1), (altura - 2 * MARGEM) / (y1 - y0 || 1));
		return { s: Math.max(s, 1e-6), cx: (x0 + x1) / 2, cy: (y0 + y1) / 2 };
	});
	// o y do desenho cresce para cima; o da tela, para baixo
	const baseX = (v: number) => largura / 2 + (v - ajuste.cx) * ajuste.s;
	const baseY = (v: number) => altura / 2 - (v - ajuste.cy) * ajuste.s;
	const bx = $derived.by(() => {
		const b = Float64Array.from(x, baseX);
		for (const [i, [px]] of movidos) if (Number.isFinite(b[i])) b[i] = baseX(px);
		return b;
	});
	const by = $derived.by(() => {
		const b = Float64Array.from(y, baseY);
		for (const [i, [, py]] of movidos) if (Number.isFinite(b[i])) b[i] = baseY(py);
		return b;
	});
	const telaX = (i: number) => bx[i] * vista.k + vista.dx;
	const telaY = (i: number) => by[i] * vista.k + vista.dy;
	const valido = (i: number) => Number.isFinite(bx[i]) && Number.isFinite(by[i]);

	const arvore = $derived.by((): Quadtree<number> => {
		const indices: number[] = [];
		for (let i = 0; i < bx.length; i += 1) if (valido(i)) indices.push(i);
		return quadtree<number>()
			.x((i) => bx[i])
			.y((i) => by[i])
			.addAll(indices);
	});
	const raioMaximo = $derived(raio.reduce((m, r) => Math.max(m, r), 0));

	/** O nó sob o ponto (pixels do canvas), ou `null`. */
	function achar(px: number, py: number): number | null {
		const folga = 4;
		const i = arvore.find((px - vista.dx) / vista.k, (py - vista.dy) / vista.k, (raioMaximo + folga) / vista.k);
		if (i === undefined) return null;
		return Math.hypot(telaX(i) - px, telaY(i) - py) <= Math.max(raio[i], 3) + folga ? i : null;
	}

	/** O nó mais perto do centro da área (a até 40 px): o que o Enter abre quando o mouse não está sobre um nó. */
	function maisPertoDoCentro(): number | null {
		const i = arvore.find((largura / 2 - vista.dx) / vista.k, (altura / 2 - vista.dy) / vista.k, 40 / vista.k);
		return i === undefined ? null : i;
	}

	/** Posição de um nó na tela (px, relativa ao canvas), para os testes clicarem nele. */
	export function posicaoNaTela(i: number): [number, number] | undefined {
		if (!valido(i)) return undefined;
		return [telaX(i), telaY(i)];
	}

	// ---- destaque: a vizinhança do nó sob o mouse (ou do aberto), ou a comunidade escolhida
	const adj = $derived(adjacencia(x.length, arestas));
	const foco = $derived(sobre ?? selecionado);
	const aceso = $derived.by((): Uint8Array | null => {
		if (foco !== null && valido(foco)) {
			const a = new Uint8Array(x.length);
			for (const i of vizinhanca(adj, foco)) a[i] = 1;
			return a;
		}
		if (comunidadeEscolhida !== null) return Uint8Array.from(comunidade, (c) => (c === comunidadeEscolhida ? 1 : 0));
		return null;
	});
	const nosDaComunidade = (c: number) => {
		const saida: number[] = [];
		for (let i = 0; i < comunidade.length; i += 1) if (comunidade[i] === c && valido(i)) saida.push(i);
		return saida;
	};

	// ---- zoom, com transição curta (instantânea com movimento reduzido)
	let animacao = 0;
	const reduzido = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
	function irPara(alvo: Vista) {
		cancelAnimationFrame(animacao);
		if (reduzido()) {
			vista = alvo;
			return;
		}
		const [de, inicio] = [vista, performance.now()];
		const passo = (agora: number) => {
			const t = Math.min(1, (agora - inicio) / 320);
			const e = 1 - (1 - t) ** 3;
			// o zoom interpola em log, e o deslocamento acompanha o ponto que fica no centro
			const k = de.k * (alvo.k / de.k) ** e;
			const [cx0, cy0] = [(largura / 2 - de.dx) / de.k, (altura / 2 - de.dy) / de.k];
			const [cx1, cy1] = [(largura / 2 - alvo.dx) / alvo.k, (altura / 2 - alvo.dy) / alvo.k];
			const [cx, cy] = [cx0 + (cx1 - cx0) * e, cy0 + (cy1 - cy0) * e];
			vista = { k, dx: largura / 2 - cx * k, dy: altura / 2 - cy * k };
			if (t < 1) animacao = requestAnimationFrame(passo);
		};
		animacao = requestAnimationFrame(passo);
	}
	function zoomEm(px: number, py: number, fator: number) {
		cancelAnimationFrame(animacao);
		const k = Math.min(ZOOM.max, Math.max(ZOOM.min, vista.k * fator));
		const f = k / vista.k;
		vista = { k, dx: px - (px - vista.dx) * f, dy: py - (py - vista.dy) * f };
	}
	const aproximar = () => zoomEm(largura / 2, altura / 2, ZOOM.passo);
	const afastar = () => zoomEm(largura / 2, altura / 2, 1 / ZOOM.passo);
	function reiniciar() {
		movidos = new Map();
		irPara({ k: 1, dx: 0, dy: 0 });
	}
	const mexido = $derived(vista.k !== 1 || !!vista.dx || !!vista.dy || movidos.size > 0);
	const enquadravel = $derived(selecionado !== null || comunidadeEscolhida !== null);
	/** Leva o zoom até a vizinhança do nó aberto, ou até a comunidade escolhida. */
	function enquadrarDestaque() {
		const nos =
			selecionado !== null
				? vizinhanca(adj, selecionado)
				: comunidadeEscolhida !== null
					? nosDaComunidade(comunidadeEscolhida)
					: [];
		const alvo = enquadrar(nos, bx, by, largura, altura, { kMin: ZOOM.min, kMax: 8 });
		if (alvo) irPara(alvo);
	}

	// o nó aberto pela busca ou pelo link: o zoom vai até ele e os vizinhos; pelo clique no grafo, nada se move. O
	// efeito depende só do nó aberto: redimensionar a janela (ou entrar na tela cheia) não refaz o enquadramento
	function enquadrarNo(i: number) {
		if (!valido(i)) {
			enquadrarQuandoAparecer = i; // a vista vai mostrar as duplas e os trios, e o nó entra no desenho
			return;
		}
		const alvo = enquadrar(vizinhanca(adj, i), bx, by, largura, altura, { kMin: ZOOM.min, kMax: 8 });
		if (alvo) irPara(alvo);
	}
	$effect(() => {
		const i = selecionado;
		untrack(() => {
			const doGrafo = escolhidoPeloGrafo !== null && escolhidoPeloGrafo === i;
			escolhidoPeloGrafo = null;
			enquadrarQuandoMedir = enquadrarQuandoAparecer = null;
			if (i === null || doGrafo) return;
			if (!largura || !altura) enquadrarQuandoMedir = i;
			else enquadrarNo(i);
		});
	});
	$effect(() => {
		if (!largura || !altura) return;
		untrack(() => {
			const i = enquadrarQuandoMedir;
			enquadrarQuandoMedir = null;
			if (i !== null && i === selecionado) enquadrarNo(i);
		});
	});
	$effect(() => {
		void bx;
		void by;
		untrack(() => {
			const i = enquadrarQuandoAparecer;
			if (i === null || i !== selecionado || !largura || !altura || !valido(i)) return;
			enquadrarQuandoAparecer = null;
			enquadrarNo(i);
		});
	});
	// a comunidade escolhida é enquadrada; soltá-la volta à vista inteira
	let comunidadeAnterior: number | null = null;
	$effect(() => {
		const c = comunidadeEscolhida;
		if (!largura || !altura) return;
		untrack(() => {
			if (c === comunidadeAnterior) return;
			const antes = comunidadeAnterior;
			comunidadeAnterior = c;
			if (c !== null) {
				const alvo = enquadrar(nosDaComunidade(c), bx, by, largura, altura, { kMin: ZOOM.min, kMax: 8 });
				if (alvo) irPara(alvo);
			} else if (antes !== null && selecionado === null) {
				irPara({ k: 1, dx: 0, dy: 0 });
			}
		});
	});

	function escolher(i: number | null) {
		// só uma mudança de nó passa pelo efeito do nó aberto (um clique no nó já aberto não muda nada)
		escolhidoPeloGrafo = i !== null && i !== selecionado ? i : null;
		aoEscolher(i);
	}

	// ---- tela cheia (a figura inteira do grafo, com os botões)
	async function alternarTelaCheia() {
		if (document.fullscreenElement) await document.exitFullscreen();
		else await (alvoTelaCheia ?? grafo).requestFullscreen?.();
	}

	// ---- teclado (com a área do grafo em foco)
	function tecla(e: KeyboardEvent) {
		if (e.metaKey || e.ctrlKey || e.altKey) return;
		origem = 'teclado';
		const acoes: Record<string, () => void> = {
			'+': aproximar,
			'=': aproximar,
			'-': afastar,
			_: afastar,
			'0': reiniciar,
			ArrowLeft: () => (vista = { ...vista, dx: vista.dx + MOVER }),
			ArrowRight: () => (vista = { ...vista, dx: vista.dx - MOVER }),
			ArrowUp: () => (vista = { ...vista, dy: vista.dy + MOVER }),
			ArrowDown: () => (vista = { ...vista, dy: vista.dy - MOVER }),
			Enter: () => {
				const i = sobre ?? maisPertoDoCentro();
				if (i !== null) aoEscolher(i);
			}
		};
		const acao = acoes[e.key];
		if (!acao) return;
		e.preventDefault();
		acao();
	}

	// ---- mouse, dedos e roda
	onMount(() => {
		podeTelaCheia = !!document.fullscreenEnabled && typeof grafo.requestFullscreen === 'function';
		const aoMudarTelaCheia = () => (telaCheia = !!document.fullscreenElement && document.fullscreenElement.contains(grafo));
		document.addEventListener('fullscreenchange', aoMudarTelaCheia);

		const ponteiros = new Map<number, { x: number; y: number }>();
		type Arrasto = { x: number; y: number; dx: number; dy: number; moveu: boolean; no: number | null };
		let arrasto: Arrasto | null = null;
		let pinca: { distancia: number; k: number } | null = null;
		let temporizador = 0;
		const local = (e: { clientX: number; clientY: number }) => {
			const caixa = canvas.getBoundingClientRect();
			return { x: e.clientX - caixa.left, y: e.clientY - caixa.top };
		};
		const distancia = () => {
			const [p, q] = [...ponteiros.values()];
			return Math.hypot(p.x - q.x, p.y - q.y);
		};
		const baixar = (e: PointerEvent) => {
			if (e.button > 0) return;
			origem = 'ponteiro';
			try {
				canvas.setPointerCapture(e.pointerId);
			} catch {
				/* um ponteiro que o navegador não conhece (sintético): segue sem a captura */
			}
			ponteiros.set(e.pointerId, local(e));
			if (ponteiros.size === 1) {
				const p = local(e);
				arrasto = { x: p.x, y: p.y, dx: vista.dx, dy: vista.dy, moveu: false, no: achar(p.x, p.y) };
				cancelAnimationFrame(animacao);
			} else if (ponteiros.size === 2) {
				pinca = { distancia: distancia(), k: vista.k };
				if (arrasto) arrasto.moveu = true; // uma pinça nunca vira clique
			}
		};
		const mover = (e: PointerEvent) => {
			const p = local(e);
			if (ponteiros.has(e.pointerId)) ponteiros.set(e.pointerId, p);
			if (pinca && ponteiros.size === 2) {
				const [a, b] = [...ponteiros.values()];
				zoomEm((a.x + b.x) / 2, (a.y + b.y) / 2, (pinca.k * (distancia() / (pinca.distancia || 1))) / vista.k);
				return;
			}
			if (arrasto) {
				const [dx, dy] = [p.x - arrasto.x, p.y - arrasto.y];
				if (!arrasto.moveu && Math.hypot(dx, dy) > 3) {
					arrasto.moveu = true;
					arrastando = true;
				}
				if (!arrasto.moveu) return;
				if (arrasto.no !== null) {
					// arrastar um nó: ele vai para baixo do ponteiro (no desenho, e só na tela); o destaque acompanha
					const i = arrasto.no;
					const novo = new Map(movidos);
					novo.set(i, paraDesenho((p.x - vista.dx) / vista.k, (p.y - vista.dy) / vista.k, ajuste, largura, altura));
					movidos = novo;
					sobre = i;
					posMouse = null;
				} else {
					sobre = null;
					vista = { ...vista, dx: arrasto.dx + dx, dy: arrasto.dy + dy };
				}
				return;
			}
			sobre = achar(p.x, p.y);
			posMouse = p;
		};
		/** Terminada a pinça com um dedo ainda na tela, o arrasto recomeça dele (senão a vista pularia). */
		const retomarArrasto = () => {
			const resto = [...ponteiros.values()][0];
			arrasto = resto ? { x: resto.x, y: resto.y, dx: vista.dx, dy: vista.dy, moveu: true, no: null } : null;
		};
		const soltar = (e: PointerEvent) => {
			const p = local(e);
			ponteiros.delete(e.pointerId);
			if (pinca && ponteiros.size < 2) {
				pinca = null;
				retomarArrasto();
			}
			if (arrasto && !arrasto.moveu && ponteiros.size === 0) escolher(achar(p.x, p.y));
			if (ponteiros.size === 0) {
				arrasto = null;
				arrastando = false;
			}
		};
		// o navegador tomou o gesto (a rolagem da página, com um dedo): nada de clique
		const cancelar = (e: PointerEvent) => {
			ponteiros.delete(e.pointerId);
			pinca = null;
			if (ponteiros.size) retomarArrasto();
			else {
				arrasto = null;
				arrastando = false;
			}
		};
		const sair = () => {
			if (!arrasto) sobre = null;
		};
		const roda = (e: WheelEvent) => {
			// a roda sozinha é da página (rolar até o fim dela passa pelo grafo); Ctrl/⌘ + roda e a pinça do trackpad
			// (que chega como roda com Ctrl) aproximam; em tela cheia, a roda sozinha também
			if (!(e.ctrlKey || e.metaKey || telaCheia)) {
				avisoRoda = true;
				clearTimeout(temporizador);
				temporizador = window.setTimeout(() => (avisoRoda = false), 1600);
				return;
			}
			e.preventDefault();
			avisoRoda = false;
			const p = local(e);
			const passo = e.deltaMode === 1 ? 0.05 : 0.0025; // linhas ou pixels
			zoomEm(p.x, p.y, Math.exp(-e.deltaY * passo));
		};
		const duplo = (e: MouseEvent) => {
			const p = local(e);
			zoomEm(p.x, p.y, ZOOM.passo);
		};
		// a exportação acha a função pelo elemento (`exportar/figura.ts`)
		(canvas as HTMLCanvasElement & { rasterizar?: () => string }).rasterizar = rasterizar;
		canvas.addEventListener('pointerdown', baixar);
		canvas.addEventListener('pointermove', mover);
		canvas.addEventListener('pointerup', soltar);
		canvas.addEventListener('pointercancel', cancelar);
		canvas.addEventListener('pointerleave', sair);
		canvas.addEventListener('dblclick', duplo);
		// passiva não pode impedir a rolagem da página (quando o gesto é de zoom)
		canvas.addEventListener('wheel', roda, { passive: false });
		return () => {
			cancelAnimationFrame(animacao);
			clearTimeout(temporizador);
			document.removeEventListener('fullscreenchange', aoMudarTelaCheia);
			canvas.removeEventListener('pointerdown', baixar);
			canvas.removeEventListener('pointermove', mover);
			canvas.removeEventListener('pointerup', soltar);
			canvas.removeEventListener('pointercancel', cancelar);
			canvas.removeEventListener('pointerleave', sair);
			canvas.removeEventListener('dblclick', duplo);
			canvas.removeEventListener('wheel', roda);
		};
	});

	// ---- desenho
	function lerCores() {
		const s = getComputedStyle(canvas);
		const v = (nome: string, padrao: string) => s.getPropertyValue(nome).trim() || padrao;
		return {
			texto: v('--texto', '#eceaf4'),
			fraco: v('--texto-fraco', '#7e82a6'),
			fundo: v('--fundo', '#0a0e1f'),
			acento: v('--acento', '#ffb547')
		};
	}

	/**
	 * Desenha o grafo em `ctx` (a tela ou a imagem da exportação), com as cores do tema dado. Com um destaque, o resto
	 * fica esmaecido; sem ele, as arestas entre comunidades ficam mais fracas que as de dentro delas.
	 */
	function pintar(ctx: CanvasRenderingContext2D, cores: ReturnType<typeof lerCores>) {
		const acesos = aceso;
		ctx.clearRect(0, 0, largura, altura);
		ctx.lineCap = 'round';
		// arestas: uma passada por faixa e por grupo: esmaecida (fora do destaque), entre comunidades, dentro de uma,
		// acesa (dentro do destaque)
		const [ESMAECIDA, ACESA] = [0, 3];
		const grupo = (a: number, b: number) => {
			if (acesos) return acesos[a] && acesos[b] ? ACESA : ESMAECIDA;
			return comunidade[a] >= 0 && comunidade[a] === comunidade[b] ? 2 : 1;
		};
		const ALFA = [0.22, 0.6, 1, 1];
		for (let f = 0; f < TRACO_DAS_FAIXAS.length; f += 1) {
			for (let g = ESMAECIDA; g <= ACESA; g += 1) {
				ctx.beginPath();
				let alguma = false;
				for (let k = 0; k < arestas.n; k += 1) {
					if (faixas[k] !== f) continue;
					const [a, b] = [arestas.a[k], arestas.b[k]];
					if (!valido(a) || !valido(b) || grupo(a, b) !== g) continue;
					ctx.moveTo(telaX(a), telaY(a));
					ctx.lineTo(telaX(b), telaY(b));
					alguma = true;
				}
				if (!alguma) continue;
				const traco = TRACO_DAS_FAIXAS[f];
				ctx.globalAlpha = g === ACESA ? Math.min(1, traco.alfa * 1.8 + 0.2) : traco.alfa * ALFA[g];
				ctx.lineWidth = g === ACESA ? traco.largura + 0.4 : traco.largura;
				ctx.strokeStyle = f === 0 && g !== ACESA ? cores.fraco : cores.texto;
				ctx.stroke();
			}
		}
		// as arestas do nó aberto, no acento
		if (selecionado !== null && valido(selecionado)) {
			ctx.beginPath();
			for (let k = adj.inicio[selecionado]; k < adj.inicio[selecionado + 1]; k += 1) {
				const j = adj.vizinho[k];
				if (!valido(j)) continue;
				ctx.moveTo(telaX(selecionado), telaY(selecionado));
				ctx.lineTo(telaX(j), telaY(j));
			}
			ctx.globalAlpha = 0.85;
			ctx.lineWidth = 1.4;
			ctx.strokeStyle = cores.acento;
			ctx.stroke();
		}
		// nós: os de fora do recorte, apagados; os de dentro, agrupados por cor (um preenchimento por cor); com um
		// destaque, os de fora dele quase somem
		const circulo = (i: number, r = raio[i]) => {
			ctx.moveTo(telaX(i) + r, telaY(i));
			ctx.arc(telaX(i), telaY(i), r, 0, 2 * Math.PI);
		};
		ctx.beginPath();
		for (let i = 0; i < bx.length; i += 1) if (!ativo[i] && valido(i)) circulo(i);
		ctx.globalAlpha = acesos ? 0.12 : 0.3;
		ctx.fillStyle = cores.fraco;
		ctx.fill();
		for (const vez of acesos ? [0, 1] : [1]) {
			const porCor = new Map<string, number[]>();
			for (let i = 0; i < bx.length; i += 1) {
				if (!ativo[i] || !valido(i) || (acesos && acesos[i] !== vez)) continue;
				const c = cor[i] ?? cores.fraco;
				const lista = porCor.get(c);
				if (lista) lista.push(i);
				else porCor.set(c, [i]);
			}
			ctx.globalAlpha = vez ? 1 : 0.2;
			ctx.lineWidth = 0.8;
			ctx.strokeStyle = cores.fundo;
			for (const [c, lista] of porCor) {
				ctx.beginPath();
				for (const i of lista) circulo(i);
				ctx.fillStyle = c;
				ctx.fill();
				ctx.stroke();
			}
		}
		// o nó aberto e o nó sob o mouse, com um anel
		ctx.globalAlpha = 1;
		for (const [i, c, espessura] of [
			[selecionado, cores.acento, 2.5],
			[sobre, cores.texto, 1.5]
		] as [number | null, string, number][]) {
			if (i === null || !valido(i)) continue;
			ctx.beginPath();
			ctx.arc(telaX(i), telaY(i), raio[i] + 3, 0, 2 * Math.PI);
			ctx.lineWidth = espessura;
			ctx.strokeStyle = c;
			ctx.stroke();
		}
		ctx.globalAlpha = 1;
	}

	$effect(() => {
		void tema.atual; // as cores vêm das variáveis do tema
		if (!largura || !altura) return;
		const dpr = window.devicePixelRatio || 1;
		const [w, h] = [Math.round(largura * dpr), Math.round(altura * dpr)];
		if (canvas.width !== w || canvas.height !== h) [canvas.width, canvas.height] = [w, h];
		const ctx = canvas.getContext('2d');
		if (!ctx) return;
		ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
		pintar(ctx, lerCores());
		if (!desenhouUmaVez) {
			desenhouUmaVez = true;
			aoDesenhar?.(performance.now() - t0);
		}
	});

	/**
	 * A imagem do grafo para a exportação (`exportar/figura.ts`), com as cores do tema que estiver aplicado no
	 * documento no momento da chamada (a exportação troca o tema antes, sem mudar a tela), em dobro da resolução.
	 */
	export function rasterizar(): string {
		const imagem = document.createElement('canvas');
		[imagem.width, imagem.height] = [Math.round(largura * 2), Math.round(altura * 2)];
		const ctx = imagem.getContext('2d')!;
		ctx.setTransform(2, 0, 0, 2, 0, 0);
		pintar(ctx, lerCores());
		return imagem.toDataURL('image/png');
	}

	// ---- rótulos por cima: o nome do nó aberto, os das comunidades e os dos nós (vizinhos acesos, ou pelo zoom)
	const nomeAberto = $derived.by(() => {
		if (selecionado === null || !valido(selecionado)) return null;
		const [px, py] = [telaX(selecionado), telaY(selecionado) - raio[selecionado] - 8];
		const texto = nomeDo(selecionado);
		return semColisao([{ id: 'aberto', texto, px, py, prioridade: 1 }], largura, altura, {
			larguraDe: (t) => t.length * 7.2 + 8
		})[0] ?? null;
	});
	const rotulosNaTela = $derived.by(() => {
		const candidatos = rotulos
			.filter((r) => comunidadeEscolhida === null || r.comunidade === comunidadeEscolhida)
			.map((r, k) => ({ ...r, px: baseX(r.x) * vista.k + vista.dx, py: baseY(r.y) * vista.k + vista.dy - 12, prioridade: -k }));
		const postos = semColisao(candidatos, largura, altura, {
			larguraDe: (t) => t.length * 6.8 + 12,
			alturaTexto: 18,
			ocupadas: nomeAberto ? [nomeAberto.caixa] : []
		});
		return postos.map((r) => ({ ...r, comunidade: candidatos.find((c) => c.id === r.id)!.comunidade }));
	});
	/** Os nós por tamanho (os maiores ganham nome primeiro). */
	const porTamanho = $derived(Array.from({ length: x.length }, (_, i) => i).sort((a, b) => raio[b] - raio[a] || a - b));
	const nomesNaTela = $derived.by(() => {
		const ocupadas = [...(nomeAberto ? [nomeAberto.caixa] : []), ...rotulosNaTela.map((r) => r.caixa)];
		let quais: number[];
		let maximo: number;
		if (foco !== null && aceso) {
			// a vizinhança acesa: os nomes dos vizinhos (os maiores, se forem muitos)
			quais = porTamanho.filter((i) => aceso[i] && i !== selecionado && valido(i));
			maximo = 24;
		} else {
			maximo = nomesNoZoom(vista.k);
			if (!maximo) return [];
			quais = porTamanho.filter((i) => valido(i) && ativo[i] && i !== selecionado && (!aceso || aceso[i]));
		}
		const larguraDe = (t: string) => t.length * 6.2 + 6;
		const candidatos = [];
		for (const i of quais) {
			const [px, py] = [telaX(i), telaY(i)];
			if (px < 0 || px > largura || py < 0 || py > altura) continue;
			const texto = nomeDo(i);
			candidatos.push({ id: String(i), texto, px: px + raio[i] + 3 + larguraDe(texto) / 2, py: py + 4, prioridade: raio[i] });
			if (candidatos.length > maximo * 4) break;
		}
		return semColisao(candidatos, largura, altura, { larguraDe, alturaTexto: 14, ocupadas, maximo });
	});
	const linhasDica = $derived(sobre !== null && posMouse ? dica(sobre) : []);

	/** O estado da interação, para a depuração. */
	export function estado(): EstadoGrafo {
		return {
			vista: { ...vista },
			destacados: aceso ? aceso.reduce((s, v) => s + v, 0) : 0,
			movidos: movidos.size,
			nomes: nomesNaTela.map((r) => r.texto),
			telaCheia
		};
	}
</script>

<div
	class="grafo"
	class:tela-cheia={telaCheia}
	bind:this={grafo}
	data-grafo-raiz
	data-origem={origem}
	onpointerdowncapture={() => (origem = 'ponteiro')}
	onkeydowncapture={() => (origem = 'teclado')}
	role="presentation"
>
	<div class="ferramentas" role="toolbar" aria-label="Controles do grafo">
		{#if opcoesComunidade.length}
			<select
				class="botao"
				aria-label="Comunidade em destaque"
				value={comunidadeEscolhida === null ? '' : String(comunidadeEscolhida)}
				onchange={(e) => aoEscolherComunidade(e.currentTarget.value === '' ? null : Number(e.currentTarget.value))}
				data-testid="escolher-comunidade"
			>
				<option value="">Todas as comunidades</option>
				{#each opcoesComunidade as c (c.id)}<option value={String(c.id)}>{c.rotulo}</option>{/each}
			</select>
		{/if}
		{#if enquadravel}
			<button type="button" class="botao" onclick={enquadrarDestaque} data-testid="zoom-enquadrar">
				{selecionado !== null ? 'Enquadrar o nó' : 'Enquadrar a comunidade'}
			</button>
		{/if}
		<button type="button" class="botao" aria-label="Aproximar" title="Aproximar (+)" onclick={aproximar} data-testid="zoom-mais">+</button>
		<button type="button" class="botao" aria-label="Afastar" title="Afastar (−)" onclick={afastar} data-testid="zoom-menos">−</button>
		<button
			type="button"
			class="botao"
			title="O desenho inteiro, sem os nós movidos (0)"
			onclick={reiniciar}
			disabled={!mexido}
			data-testid="zoom-reiniciar"
		>
			Reiniciar
		</button>
		{#if podeTelaCheia}
			<button type="button" class="botao" aria-pressed={telaCheia} onclick={alternarTelaCheia} data-testid="tela-cheia">
				{telaCheia ? 'Sair da tela cheia' : 'Tela cheia'}
			</button>
		{/if}
	</div>
	<!-- a área recebe o foco (pelo clique ou pelo Tab) para os atalhos do teclado; a descrição fica no invólucro do
	     canvas, que não aceita o papel de imagem. O papel `application` é o de um widget com teclado próprio, que o
	     Svelte não conta como interativo -->
	<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
	<div
		class="area"
		role="application"
		aria-roledescription="grafo"
		tabindex="0"
		aria-label="Grafo: + e − aproximam, 0 volta ao desenho inteiro, as setas movem, Enter abre o nó do centro e Esc solta a comunidade"
		data-grafo
		onkeydown={tecla}
		bind:clientWidth={largura}
		bind:clientHeight={altura}
	>
		<div role="img" aria-label={rotulo}>
			<canvas
				bind:this={canvas}
				class:arrastando
				class:sobre-no={sobre !== null}
				data-testid="canvas-rede"
				data-rasterizavel
				style:width="{largura}px"
				style:height="{altura}px"
			></canvas>
		</div>
		<svg class="camada" width={largura} height={altura} aria-hidden="true" data-desenho-rede>
			{#each nomesNaTela as r (r.id)}
				<text x={r.px} y={r.py} class="nome" text-anchor="middle" data-testid="nome-no">{r.texto}</text>
			{/each}
			{#each rotulosNaTela as r (r.id)}
				<!-- os rótulos não recebem o clique (no celular, tomavam o toque dos nós embaixo deles): a comunidade se
				     escolhe no seletor da barra do grafo ou na legenda -->
				<text
					x={r.px}
					y={r.py}
					class="comunidade"
					class:escolhida={r.comunidade === comunidadeEscolhida}
					text-anchor="middle"
					data-testid="rotulo-comunidade">{r.texto}</text
				>
			{/each}
			{#if nomeAberto}
				<text x={nomeAberto.px} y={nomeAberto.py} class="aberto" text-anchor="middle">{nomeAberto.texto}</text>
			{/if}
		</svg>
		{#if linhasDica.length && posMouse}
			<Dica x={posMouse.x} y={posMouse.y} linhas={linhasDica} limites={{ largura, altura }} />
		{/if}
		{#if avisoRoda}
			<p class="aviso-roda" role="status" data-testid="aviso-roda">Para aproximar, use Ctrl (⌘ no Mac) + roda, a pinça ou os botões</p>
		{/if}
	</div>
</div>

<style>
	.grafo {
		position: relative;
		display: grid;
	}

	/* por cima do canto de cima do grafo: continua à vista quando a página rola até ele */
	.ferramentas {
		position: absolute;
		z-index: 6;
		top: 0.45rem;
		right: 0.45rem;
		left: 0.45rem;
		display: flex;
		flex-wrap: wrap;
		justify-content: flex-end;
		gap: 0.3rem;
		pointer-events: none;
	}

	.ferramentas > * {
		pointer-events: auto;
	}

	/* especificidade zero: o botão pressionado (Tela cheia) mantém o fundo dele */
	:where(.ferramentas > *) {
		background: color-mix(in oklab, var(--superficie) 88%, transparent);
	}

	.ferramentas .botao {
		min-width: 2rem;
	}

	.ferramentas select {
		max-width: min(22rem, 100%);
		text-overflow: ellipsis;
	}

	@media (max-width: 820px) {
		.ferramentas {
			position: static;
			padding-bottom: 0.4rem;
		}

		.ferramentas select {
			flex: 1 1 100%;
			max-width: none;
		}
	}

	/* no toque, botões maiores */
	@media (pointer: coarse) {
		.ferramentas .botao {
			min-width: 2.6rem;
			min-height: 2.6rem;
		}
	}

	.ferramentas .botao:disabled {
		color: var(--texto-fraco);
		cursor: default;
	}

	.area {
		position: relative;
		/* a janela manda: o grafo ocupa quase a altura da tela, entre um mínimo e um máximo */
		height: clamp(26rem, calc(100dvh - 15rem), 60rem);
		overflow: hidden;
		border: 1px solid var(--linha);
		border-radius: var(--raio);
		background: color-mix(in oklab, var(--superficie) 60%, transparent);
	}

	.area:focus-visible {
		outline: 2px solid var(--foco);
		outline-offset: 2px;
	}

	.grafo.tela-cheia .area {
		height: calc(100dvh - 2rem);
	}

	canvas {
		display: block;
		cursor: grab;
		/* um dedo na vertical rola a página; na horizontal, move o grafo; dois dedos fazem a pinça */
		touch-action: pan-y;
	}

	.grafo.tela-cheia canvas {
		touch-action: none;
	}

	canvas.sobre-no {
		cursor: pointer;
	}

	canvas.arrastando {
		cursor: grabbing;
	}

	.camada {
		position: absolute;
		inset: 0;
		pointer-events: none;
		overflow: hidden;
	}

	.camada text {
		paint-order: stroke;
		stroke: var(--fundo);
		stroke-width: 4px;
		stroke-linejoin: round;
		fill: var(--texto);
	}

	.comunidade {
		font-family: var(--fonte-titulo);
		font-size: 0.85rem;
		font-style: italic;
		opacity: 0.85;
	}

	.comunidade.escolhida {
		opacity: 1;
		text-decoration: underline;
	}

	.nome {
		font-family: var(--fonte-interface);
		font-size: 0.72rem;
	}

	.aberto {
		font-family: var(--fonte-interface);
		font-size: 0.8rem;
		font-weight: 600;
	}

	.aviso-roda {
		position: absolute;
		left: 50%;
		bottom: 0.8rem;
		margin: 0;
		padding: 0.35rem 0.7rem;
		transform: translateX(-50%);
		border-radius: var(--raio);
		background: var(--superficie-alta);
		color: var(--texto);
		font-size: 0.8rem;
		pointer-events: none;
	}

	@media (max-width: 820px) {
		.area {
			height: clamp(20rem, 60dvh, 28rem);
		}
	}
</style>
