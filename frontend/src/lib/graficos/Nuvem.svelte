<script lang="ts">
	/**
	 * A nuvem de pontos do mapa, com o regl-scatterplot (WebGL, ADR 0002).
	 *
	 * O componente é controlado: recebe cores, visíveis e selecionados, e avisa cliques, laços e movimentos da
	 * câmera. O estado vive na URL (em `VistaMapa`), nunca aqui. As chamadas ao gráfico são assíncronas e ficam
	 * numa fila, para um filtro não atropelar outro durante o play da linha do tempo.
	 */
	import { onMount } from 'svelte';
	import { rota } from '$lib/estado/url';
	import type criarGrafico from 'regl-scatterplot';
	import { escalaLinear } from './escala';

	type Grafico = ReturnType<typeof criarGrafico>;
	type Vista = { x: number; y: number; zoom: number };
	export type Camera = { projetar: (x: number, y: number) => [number, number]; zoom: number; largura: number; altura: number };
	export type Anotacao = { vertices: [number, number][]; cor: string; largura: number };

	interface Props {
		x: Float32Array;
		y: Float32Array;
		valores: Float32Array;
		tipo: 'categorical' | 'continuous';
		cores: string[];
		/** `null` = todos visíveis. */
		visiveis: number[] | null;
		selecionados: number[];
		destaque: number | null;
		fundo: string;
		corLaco: string;
		modoLaco: boolean;
		/** Câmera inicial (só na montagem). */
		vista: Vista | null;
		/** Polígonos desenhados pelo próprio gráfico (acompanham a câmera sem custo): os contornos. */
		anotacoes?: Anotacao[];
		aoClicar: (i: number | null) => void;
		aoLaco: (vertices: [number, number][]) => void;
		aoMoverCamera: (v: Vista) => void;
		/** Chamado a cada quadro em que a câmera muda, para camadas sobre o mapa (rótulos). */
		aoVer?: (camera: Camera) => void;
	}

	let {
		x, y, valores, tipo, cores, visiveis, selecionados, destaque, fundo, corLaco, modoLaco, vista,
		anotacoes = [], aoClicar, aoLaco, aoMoverCamera, aoVer
	}: Props = $props();

	// O gráfico atualiza estas escalas a cada movimento: dados (NDC) → pixels do canvas
	const escalaX = escalaLinear();
	const escalaY = escalaLinear();

	function avisarCamera() {
		if (!grafico || !aoVer) return;
		const [largura, altura] = [escalaX.range()[1], escalaY.range()[0]];
		debug().zoom = 1 / grafico.get('cameraDistance');
		aoVer({ projetar: (px, py) => [escalaX(px), escalaY(py)], zoom: 1 / grafico.get('cameraDistance'), largura, altura });
	}

	let canvas: HTMLCanvasElement;
	let grafico: Grafico | null = null; // fora do $state: o Svelte não deve observar o objeto do WebGL
	let pronto = $state(false);
	/** O motivo, quando o mapa não consegue desenhar (sem WebGL, por exemplo): aparece um aviso no lugar dele. */
	let falha = $state<string | null>(null);
	let fila: Promise<unknown> = Promise.resolve();
	let aplicandoSelecao = false;

	function emFila(tarefa: () => unknown) {
		fila = fila.then(tarefa).catch((e) => console.error('[mapa]', e));
		return fila;
	}

	/** Espera o elemento ter largura e altura maiores que zero. */
	function tamanhoPositivo(el: HTMLElement): Promise<DOMRect> {
		return new Promise((resolver) => {
			const agora = el.getBoundingClientRect();
			if (agora.width > 0 && agora.height > 0) return resolver(agora);
			const observador = new ResizeObserver(() => {
				const caixa = el.getBoundingClientRect();
				if (caixa.width > 0 && caixa.height > 0) {
					observador.disconnect();
					resolver(caixa);
				}
			});
			observador.observe(el);
		});
	}

	function debug(): MapaDebug {
		return window.__mapaDebug!;
	}

	function aplicarSelecao() {
		if (!grafico) return;
		const pontos = destaque !== null && !selecionados.includes(destaque) ? [...selecionados, destaque] : selecionados;
		aplicandoSelecao = true;
		if (pontos.length) grafico.select(pontos, { preventEvent: true });
		else grafico.deselect({ preventEvent: true });
		aplicandoSelecao = false;
		debug().selecionados = selecionados;
		debug().destaque = destaque;
	}

	onMount(() => {
		const t0 = performance.now();
		window.__mapaDebug = {
			pontos: x.length,
			desenhado: false,
			msAtePrimeiroDesenho: null,
			visiveis: visiveis?.length ?? x.length,
			selecionados: [],
			destaque: null,
			modoLaco,
			renderer: null,
			erro: null
		};
		let observador: ResizeObserver | null = null;
		let temporizador: ReturnType<typeof setTimeout> | undefined;
		let desmontado = false;

		(async () => {
			try {
				const { default: criar } = await import('regl-scatterplot');
				if (desmontado) return;
				debug().etapasMs = { importar: performance.now() - t0 };
				// Com o canvas ainda sem tamanho (a casca aplica a tela cheia um instante depois), a projeção da
				// câmera fica singular e o regl-scatterplot quebra ao iniciar ("reading '0'" em getScatterGlPos).
				const r = await tamanhoPositivo(canvas);
				if (desmontado) return;
				grafico = criar({
					canvas,
					width: r.width,
					height: r.height,
					syncEvents: true,
					backgroundColor: fundo,
					pointSize: 3,
					pointSizeSelected: 3,
					pointOutlineWidth: 2,
					opacity: 0.9,
					opacityInactiveMax: 0.9,
					pointColor: cores,
					colorBy: 'valueA',
					lassoColor: corLaco,
					lassoOnLongPress: false,
					mouseMode: modoLaco ? 'lasso' : 'panZoom',
					deselectOnDblClick: false,
					deselectOnEscape: false,
					// a interface do regl-scatterplot é a do d3-scale; ele só usa domain() e range()
					xScale: escalaX as never,
					yScale: escalaY as never,
					...(vista ? { cameraTarget: [vista.x, vista.y], cameraDistance: 1 / vista.zoom } : {})
				});
				try {
					const gl = (grafico.get('regl') as unknown as { _gl: WebGLRenderingContext })._gl;
					const info = gl.getExtension('WEBGL_debug_renderer_info');
					debug().renderer = String(info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER));
				} catch {
					debug().renderer = 'desconhecido';
				}

				grafico.subscribe('select', ({ points }) => {
					if (aplicandoSelecao) return;
					if (points.length === 1) aoClicar(points[0]);
					aplicarSelecao(); // a seleção de verdade é a do laço (na URL), não a do clique
				});
				grafico.subscribe('deselect', () => {
					if (aplicandoSelecao) return;
					aoClicar(null);
					aplicarSelecao();
				});
				grafico.subscribe('lassoEnd', ({ coordinates }) => {
					// os tipos dizem número[] plano, mas o regl-scatterplot 1.16 manda pares [x, y]
					const brutos = coordinates as unknown as (number | [number, number])[];
					const vertices: [number, number][] = Array.isArray(brutos[0])
						? (brutos as [number, number][]).map(([px, py]) => [px, py])
						: Array.from({ length: Math.floor(brutos.length / 2) }, (_, k) => [brutos[2 * k] as number, brutos[2 * k + 1] as number]);
					debug().lacos = (debug().lacos ?? 0) + 1;
					if (vertices.length >= 3) aoLaco(vertices);
				});
				grafico.subscribe('view', () => {
					avisarCamera();
					clearTimeout(temporizador);
					temporizador = setTimeout(() => {
						if (!grafico) return;
						const [cx, cy] = grafico.get('cameraTarget');
						aoMoverCamera({ x: cx, y: cy, zoom: 1 / grafico.get('cameraDistance') });
					}, 250);
				});

				debug().etapasMs!.criar = performance.now() - t0;
				await grafico.draw({ x, y, valueA: valores }, { zDataType: tipo });
				if (desmontado || !grafico) return; // a pessoa saiu do mapa antes do primeiro desenho
				debug().etapasMs!.desenhar = performance.now() - t0;
				if (visiveis) await grafico.filter(visiveis, { preventEvent: true });
				aplicarSelecao();
				await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
				debug().msAtePrimeiroDesenho = performance.now() - t0;
				debug().desenhado = true;
				debug().posicaoNaTela = (i) => grafico?.getScreenPosition(i);
				pronto = true;
				avisarCamera();

				// Com largura e altura em números, o regl-scatterplot fixa o tamanho do canvas em pixels no `style`:
				// a caixa do canvas não muda mais, e observá-la não adianta. Quem muda é o pai (a `.tela`, que ocupa
				// a área do mapa): janela redimensionada, modo apresentação, painel recolhido, celular girado.
				const pai = canvas.parentElement ?? canvas;
				observador = new ResizeObserver(() => {
					const caixa = pai.getBoundingClientRect();
					if (!caixa.width || !caixa.height) return;
					emFila(() => grafico?.set({ width: caixa.width, height: caixa.height })).then(avisarCamera);
				});
				observador.observe(pai);
			} catch (e) {
				debug().erro = e instanceof Error ? `${e.name}: ${e.message}` : String(e);
				falha = debug().erro;
				console.error('[mapa] falha ao desenhar', e);
			}
		})();

		return () => {
			desmontado = true;
			clearTimeout(temporizador);
			observador?.disconnect();
			grafico?.destroy();
			grafico = null;
		};
	});

	// Cores, tipo ou valores mudaram: redesenha sem perder o filtro
	$effect(() => {
		const [c, v, t] = [cores, valores, tipo];
		if (!pronto) return;
		emFila(async () => {
			await grafico?.set({ pointColor: c });
			await grafico?.draw({ x, y, valueA: v }, { zDataType: t, preventFilterReset: true });
			aplicarSelecao();
		});
	});

	$effect(() => {
		const v = visiveis;
		if (!pronto) return;
		debug().visiveis = v?.length ?? x.length;
		emFila(() => (v ? grafico?.filter(v, { preventEvent: true }) : grafico?.unfilter({ preventEvent: true })));
	});

	$effect(() => {
		void selecionados;
		void destaque;
		if (pronto) emFila(aplicarSelecao);
	});

	$effect(() => {
		const a = anotacoes;
		if (!pronto) return;
		debug().anotacoes = a.length;
		emFila(() =>
			a.length
				? grafico?.drawAnnotations(a.map((p) => ({ vertices: p.vertices, lineColor: p.cor, lineWidth: p.largura })))
				: grafico?.clearAnnotations()
		);
	});

	$effect(() => {
		const f = fundo;
		if (pronto) emFila(() => grafico?.set({ backgroundColor: f }));
	});

	$effect(() => {
		const m = modoLaco;
		if (!pronto) return;
		debug().modoLaco = m;
		emFila(() => grafico?.set({ mouseMode: m ? 'lasso' : 'panZoom' }));
	});
</script>

<canvas bind:this={canvas} class="nuvem" class:laco={modoLaco} data-testid="canvas-mapa" aria-hidden="true"></canvas>
{#if falha}
	<div class="falha" role="alert" data-testid="mapa-sem-webgl">
		<p><strong>O mapa não conseguiu desenhar neste navegador.</strong></p>
		<p>
			Ele usa WebGL, que parece desligado ou indisponível (numa máquina virtual, num navegador antigo ou com a
			aceleração gráfica desativada). As outras vistas funcionam sem ele: <a href={rota('/topicos')}>Tópicos</a>,
			<a href={rota('/classificacao')}>Classificação</a>, <a href={rota('/geografia')}>Geografia</a> e
			<a href={rota('/redes')}>Redes</a>.
		</p>
		<p class="detalhe">Detalhe: {falha}</p>
	</div>
{/if}

<style>
	.nuvem {
		display: block;
		width: 100%;
		height: 100%;
		cursor: grab;
	}

	.nuvem:active {
		cursor: grabbing;
	}

	.nuvem.laco {
		cursor: crosshair;
	}

	.falha {
		position: absolute;
		inset: 0;
		display: grid;
		align-content: center;
		justify-items: start;
		gap: 0.4rem;
		max-width: 36rem;
		margin: auto;
		padding: 1.5rem;
		color: var(--texto-suave);
	}

	.falha p {
		margin: 0;
	}

	.falha .detalhe {
		font-family: var(--fonte-mono);
		font-size: 0.75rem;
		color: var(--texto-fraco);
	}
</style>
