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
		/** Posição no desenho (as mesmas coordenadas dos nós). */
		x: number;
		y: number;
	}
</script>

<script lang="ts">
	/**
	 * Um grafo em canvas 2D: a rede de coautoria ou a de instituições, com o desenho que o Python calculou para o
	 * corpus inteiro. O recorte não move nada: quem sai dele fica esmaecido, e as arestas do recorte ganham a faixa de
	 * opacidade do peso que têm nele. Canvas, e não SVG, porque o piloto tem milhares de nós e arestas.
	 *
	 * O componente é controlado (o nó aberto vem da URL, em `VistaRedes`); o zoom e o arrasto são só daqui. A roda
	 * aproxima em torno do mouse, o arrasto move, dois dedos fazem a pinça; o clique num nó chama `aoEscolher`, e o
	 * nó mais perto do mouse sai de um `d3-quadtree`. Nada anima: cada mudança redesenha um quadro só.
	 *
	 * Os rótulos das comunidades ficam num SVG por cima, que deixa passar o mouse (`pointer-events: none`).
	 */
	import { quadtree, type Quadtree } from 'd3-quadtree';
	import { onMount, untrack } from 'svelte';
	import { tema } from '$lib/estado/tema.svelte';
	import Dica from '$lib/graficos/Dica.svelte';

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
		/** Faixa de cada aresta no recorte (0 = fora dele). */
		faixas: Uint8Array;
		selecionado: number | null;
		rotulos: RotuloGrafo[];
		nomeDo: (i: number) => string;
		dica: (i: number) => string[];
		aoEscolher: (i: number | null) => void;
		/** Descrição para leitores de tela. */
		rotulo: string;
		/** Chamado depois do primeiro desenho, com o tempo desde a montagem. */
		aoDesenhar?: (ms: number) => void;
	}

	let { x, y, raio, cor, ativo, arestas, faixas, selecionado, rotulos, nomeDo, dica, aoEscolher, rotulo, aoDesenhar }: Props =
		$props();

	const MARGEM = 28;
	const ZOOM = { min: 0.5, max: 40, passo: 1.6 };

	let canvas: HTMLCanvasElement;
	let largura = $state(0);
	let altura = $state(0);
	/** Zoom e deslocamento: tela = base × k + (dx, dy). */
	let vista = $state({ k: 1, dx: 0, dy: 0 });
	let sobre = $state<number | null>(null);
	let posMouse = $state<{ x: number; y: number } | null>(null);
	let arrastando = $state(false);
	const t0 = performance.now();
	let desenhouUmaVez = false;

	// ---- do desenho (coordenadas do Python) para a base em pixels, com a mesma escala nos dois eixos
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
	const bx = $derived(Float64Array.from(x, baseX));
	const by = $derived(Float64Array.from(y, baseY));
	const telaX = (i: number) => bx[i] * vista.k + vista.dx;
	const telaY = (i: number) => by[i] * vista.k + vista.dy;

	const arvore = $derived.by((): Quadtree<number> => {
		const indices: number[] = [];
		for (let i = 0; i < bx.length; i += 1) if (Number.isFinite(bx[i]) && Number.isFinite(by[i])) indices.push(i);
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

	/** Posição de um nó na tela (px, relativa ao canvas), para os testes clicarem nele. */
	export function posicaoNaTela(i: number): [number, number] | undefined {
		if (!Number.isFinite(bx[i]) || !Number.isFinite(by[i])) return undefined;
		return [telaX(i), telaY(i)];
	}

	// ---- zoom
	function zoomEm(px: number, py: number, fator: number) {
		const k = Math.min(ZOOM.max, Math.max(ZOOM.min, vista.k * fator));
		const f = k / vista.k;
		vista = { k, dx: px - (px - vista.dx) * f, dy: py - (py - vista.dy) * f };
	}
	const aproximar = () => zoomEm(largura / 2, altura / 2, ZOOM.passo);
	const afastar = () => zoomEm(largura / 2, altura / 2, 1 / ZOOM.passo);
	const reiniciar = () => (vista = { k: 1, dx: 0, dy: 0 });

	// um nó aberto pela busca ou pelo link que esteja fora da tela vem para o centro
	$effect(() => {
		const i = selecionado;
		if (i === null || !largura || !altura) return;
		// só quando o nó aberto muda: arrastar a tela depois não o traz de volta
		untrack(() => {
			const [px, py] = [bx[i] * vista.k + vista.dx, by[i] * vista.k + vista.dy];
			if (!Number.isFinite(px) || (px > 0 && px < largura && py > 0 && py < altura)) return;
			vista = { ...vista, dx: largura / 2 - bx[i] * vista.k, dy: altura / 2 - by[i] * vista.k };
		});
	});

	// ---- mouse, dedos e roda
	onMount(() => {
		const ponteiros = new Map<number, { x: number; y: number }>();
		let arrasto: { x: number; y: number; dx: number; dy: number; moveu: boolean } | null = null;
		let pinca: { distancia: number; k: number } | null = null;
		const local = (e: { clientX: number; clientY: number }) => {
			const caixa = canvas.getBoundingClientRect();
			return { x: e.clientX - caixa.left, y: e.clientY - caixa.top };
		};
		const distancia = () => {
			const [p, q] = [...ponteiros.values()];
			return Math.hypot(p.x - q.x, p.y - q.y);
		};
		const baixar = (e: PointerEvent) => {
			canvas.setPointerCapture(e.pointerId);
			ponteiros.set(e.pointerId, local(e));
			if (ponteiros.size === 1) {
				const p = local(e);
				arrasto = { x: p.x, y: p.y, dx: vista.dx, dy: vista.dy, moveu: false };
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
					sobre = null;
				}
				if (arrasto.moveu) vista = { ...vista, dx: arrasto.dx + dx, dy: arrasto.dy + dy };
				return;
			}
			sobre = achar(p.x, p.y);
			posMouse = p;
		};
		const soltar = (e: PointerEvent) => {
			const p = local(e);
			ponteiros.delete(e.pointerId);
			if (ponteiros.size < 2) pinca = null;
			if (arrasto && !arrasto.moveu && ponteiros.size === 0) aoEscolher(achar(p.x, p.y));
			if (ponteiros.size === 0) {
				arrasto = null;
				arrastando = false;
			}
		};
		const sair = () => {
			if (!arrasto) sobre = null;
		};
		const roda = (e: WheelEvent) => {
			e.preventDefault();
			const p = local(e);
			const passo = e.deltaMode === 1 ? 0.05 : 0.0015; // linhas ou pixels
			zoomEm(p.x, p.y, Math.exp(-e.deltaY * passo));
		};
		// a exportação acha a função pelo elemento (`exportar/figura.ts`)
		(canvas as HTMLCanvasElement & { rasterizar?: () => string }).rasterizar = rasterizar;
		canvas.addEventListener('pointerdown', baixar);
		canvas.addEventListener('pointermove', mover);
		canvas.addEventListener('pointerup', soltar);
		canvas.addEventListener('pointercancel', soltar);
		canvas.addEventListener('pointerleave', sair);
		// passiva não pode impedir a rolagem da página
		canvas.addEventListener('wheel', roda, { passive: false });
		return () => {
			canvas.removeEventListener('pointerdown', baixar);
			canvas.removeEventListener('pointermove', mover);
			canvas.removeEventListener('pointerup', soltar);
			canvas.removeEventListener('pointercancel', soltar);
			canvas.removeEventListener('pointerleave', sair);
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

	/** Desenha o grafo em `ctx` (a tela ou a imagem da exportação), com as cores do tema dado. */
	function pintar(ctx: CanvasRenderingContext2D, cores: ReturnType<typeof lerCores>) {
		const valido = (i: number) => Number.isFinite(bx[i]) && Number.isFinite(by[i]);
		ctx.clearRect(0, 0, largura, altura);
		ctx.lineCap = 'round';
		// arestas: uma passada por faixa, das esmaecidas às mais fortes
		for (let f = 0; f < TRACO_DAS_FAIXAS.length; f += 1) {
			ctx.beginPath();
			let alguma = false;
			for (let k = 0; k < arestas.n; k += 1) {
				if (faixas[k] !== f) continue;
				const [a, b] = [arestas.a[k], arestas.b[k]];
				if (!valido(a) || !valido(b)) continue;
				ctx.moveTo(telaX(a), telaY(a));
				ctx.lineTo(telaX(b), telaY(b));
				alguma = true;
			}
			if (!alguma) continue;
			ctx.globalAlpha = TRACO_DAS_FAIXAS[f].alfa;
			ctx.lineWidth = TRACO_DAS_FAIXAS[f].largura;
			ctx.strokeStyle = f === 0 ? cores.fraco : cores.texto;
			ctx.stroke();
		}
		// as arestas do nó aberto, no acento
		if (selecionado !== null && valido(selecionado)) {
			ctx.beginPath();
			for (let k = 0; k < arestas.n; k += 1) {
				const [a, b] = [arestas.a[k], arestas.b[k]];
				if ((a !== selecionado && b !== selecionado) || !valido(a) || !valido(b)) continue;
				ctx.moveTo(telaX(a), telaY(a));
				ctx.lineTo(telaX(b), telaY(b));
			}
			ctx.globalAlpha = 0.85;
			ctx.lineWidth = 1.4;
			ctx.strokeStyle = cores.acento;
			ctx.stroke();
		}
		// nós: os de fora do recorte, apagados; os de dentro, agrupados por cor (um preenchimento por cor)
		const circulo = (i: number, r = raio[i]) => {
			ctx.moveTo(telaX(i) + r, telaY(i));
			ctx.arc(telaX(i), telaY(i), r, 0, 2 * Math.PI);
		};
		ctx.beginPath();
		for (let i = 0; i < bx.length; i += 1) if (!ativo[i] && valido(i)) circulo(i);
		ctx.globalAlpha = 0.3;
		ctx.fillStyle = cores.fraco;
		ctx.fill();
		const porCor = new Map<string, number[]>();
		for (let i = 0; i < bx.length; i += 1) {
			if (!ativo[i] || !valido(i)) continue;
			const c = cor[i] ?? cores.fraco;
			const lista = porCor.get(c);
			if (lista) lista.push(i);
			else porCor.set(c, [i]);
		}
		ctx.globalAlpha = 1;
		ctx.lineWidth = 0.8;
		ctx.strokeStyle = cores.fundo;
		for (const [c, lista] of porCor) {
			ctx.beginPath();
			for (const i of lista) circulo(i);
			ctx.fillStyle = c;
			ctx.fill();
			ctx.stroke();
		}
		// o nó aberto e o nó sob o mouse, com um anel
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

	// ---- rótulos por cima
	// na ordem recebida (as maiores comunidades primeiro); um rótulo que cobriria outro já posto fica de fora
	const rotulosNaTela = $derived.by(() => {
		const postos: { x0: number; x1: number; y0: number; y1: number }[] = [];
		const saida: (RotuloGrafo & { px: number; py: number })[] = [];
		for (const r of rotulos) {
			const [px, py] = [baseX(r.x) * vista.k + vista.dx, baseY(r.y) * vista.k + vista.dy];
			const meia = r.texto.length * 3.4 + 6;
			const caixa = { x0: px - meia, x1: px + meia, y0: py - 11, y1: py + 5 };
			if (caixa.x0 < 0 || caixa.x1 > largura || caixa.y0 < 0 || caixa.y1 > altura) continue;
			if (postos.some((o) => caixa.x0 < o.x1 && o.x0 < caixa.x1 && caixa.y0 < o.y1 && o.y0 < caixa.y1)) continue;
			postos.push(caixa);
			saida.push({ ...r, px, py });
		}
		return saida;
	});
	const nomeAberto = $derived(
		selecionado !== null && Number.isFinite(bx[selecionado])
			? { texto: nomeDo(selecionado), px: telaX(selecionado), py: telaY(selecionado) - raio[selecionado] - 8 }
			: null
	);
	const linhasDica = $derived(sobre !== null ? dica(sobre) : []);
</script>

<div class="grafo">
	<div class="ferramentas">
		<button type="button" class="botao" aria-label="Aproximar" title="Aproximar" onclick={aproximar} data-testid="zoom-mais">+</button>
		<button type="button" class="botao" aria-label="Afastar" title="Afastar" onclick={afastar} data-testid="zoom-menos">−</button>
		<button type="button" class="botao" onclick={reiniciar} disabled={vista.k === 1 && !vista.dx && !vista.dy} data-testid="zoom-reiniciar">
			Reiniciar
		</button>
	</div>
	<div class="area" bind:clientWidth={largura} bind:clientHeight={altura}>
		<!-- o canvas não aceita o papel de imagem; a descrição fica no invólucro -->
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
			{#each rotulosNaTela as r (r.id)}
				<text x={r.px} y={r.py} class="comunidade" text-anchor="middle" data-testid="rotulo-comunidade">{r.texto}</text>
			{/each}
			{#if nomeAberto}
				<text x={nomeAberto.px} y={nomeAberto.py} class="aberto" text-anchor="middle">{nomeAberto.texto}</text>
			{/if}
		</svg>
		{#if sobre !== null && posMouse && linhasDica.length}
			<Dica x={posMouse.x} y={posMouse.y} linhas={linhasDica} />
		{/if}
	</div>
</div>

<style>
	.grafo {
		display: grid;
		gap: 0.4rem;
	}

	.ferramentas {
		display: flex;
		justify-content: flex-end;
		gap: 0.3rem;
	}

	.ferramentas .botao {
		min-width: 2rem;
	}

	.ferramentas .botao:disabled {
		color: var(--texto-fraco);
		cursor: default;
	}

	.area {
		position: relative;
		height: min(70vh, 36rem);
		overflow: hidden;
		border: 1px solid var(--linha);
		border-radius: var(--raio);
		background: color-mix(in oklab, var(--superficie) 60%, transparent);
	}

	canvas {
		display: block;
		cursor: grab;
		/* o arrasto e a pinça são do grafo, não da página */
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

	.aberto {
		font-family: var(--fonte-interface);
		font-size: 0.8rem;
		font-weight: 600;
	}

	@media (max-width: 820px) {
		.area {
			height: 22rem;
		}
	}
</style>
