<script lang="ts">
	/**
	 * A nuvem de pontos do mapa, com o regl-scatterplot (WebGL, ADR 0002).
	 *
	 * O componente é controlado: recebe cores, visíveis e selecionados, e avisa cliques, laços e movimentos da
	 * câmera. O estado vive na URL (em `VistaMapa`), nunca aqui. As chamadas ao gráfico são assíncronas e ficam
	 * numa fila, para um filtro não atropelar outro durante o play da linha do tempo.
	 */
	import { onMount } from 'svelte';
	import type criarGrafico from 'regl-scatterplot';

	type Grafico = ReturnType<typeof criarGrafico>;
	type Vista = { x: number; y: number; zoom: number };

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
		aoClicar: (i: number | null) => void;
		aoLaco: (vertices: [number, number][]) => void;
		aoMoverCamera: (v: Vista) => void;
		/** Chamado a cada quadro em que a câmera muda, para camadas sobre o mapa (rótulos). */
		aoVer?: (grafico: Grafico) => void;
		aoPronto?: (grafico: Grafico) => void;
	}

	let {
		x, y, valores, tipo, cores, visiveis, selecionados, destaque, fundo, corLaco, modoLaco, vista,
		aoClicar, aoLaco, aoMoverCamera, aoVer, aoPronto
	}: Props = $props();

	let canvas: HTMLCanvasElement;
	let grafico: Grafico | null = null; // fora do $state: o Svelte não deve observar o objeto do WebGL
	let pronto = $state(false);
	let fila: Promise<unknown> = Promise.resolve();
	let aplicandoSelecao = false;

	function emFila(tarefa: () => unknown) {
		fila = fila.then(tarefa).catch((e) => console.error('[mapa]', e));
		return fila;
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
				const r = canvas.getBoundingClientRect();
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
					const vertices: [number, number][] = [];
					for (let i = 0; i + 1 < coordinates.length; i += 2) vertices.push([coordinates[i], coordinates[i + 1]]);
					if (vertices.length >= 3) aoLaco(vertices);
				});
				grafico.subscribe('view', () => {
					if (grafico && aoVer) aoVer(grafico);
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
				pronto = true;
				aoPronto?.(grafico);
				aoVer?.(grafico);

				observador = new ResizeObserver(() => {
					const caixa = canvas.getBoundingClientRect();
					if (caixa.width && caixa.height) grafico?.set({ width: caixa.width, height: caixa.height });
				});
				observador.observe(canvas);
			} catch (e) {
				debug().erro = e instanceof Error ? `${e.name}: ${e.message}` : String(e);
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
</style>
