<script lang="ts">
	import { onMount } from 'svelte';
	import createScatterplot from 'regl-scatterplot';
	import { gerarPontos, paletaCategorica } from '$lib/pontos';

	const N_PONTOS = 10_000;
	const N_CLUSTERS = 40;
	const FUNDO = '#0A0E1F';

	let canvas: HTMLCanvasElement;
	let status = $state('iniciando');

	const proximoQuadro = () => new Promise<void>((r) => requestAnimationFrame(() => r()));

	onMount(() => {
		const montagensAnteriores = window.__mapaDebug?.montagens ?? 0;
		const { linhas, clusterDoPonto, nClusters } = gerarPontos(N_PONTOS, N_CLUSTERS);
		const debug: MapaDebug = {
			montagens: montagensAnteriores + 1,
			pontos: linhas.length,
			clusters: nClusters,
			clusterDoPonto,
			desenhado: false,
			msAtePrimeiroDesenho: null,
			msDesdeNavegacao: null,
			eventosDraw: 0,
			eventosSelect: 0,
			eventosFilter: 0,
			eventosLassoEnd: 0,
			ultimaSelecao: [],
			renderer: null,
			erro: null,
			scatterplot: null
		};
		window.__mapaDebug = debug;

		let scatterplot: ReturnType<typeof createScatterplot> | null = null;
		let observador: ResizeObserver | null = null;
		const t0 = performance.now();

		(async () => {
			try {
				const { width, height } = canvas.getBoundingClientRect();
				scatterplot = createScatterplot({
					canvas,
					width,
					height,
					backgroundColor: FUNDO,
					pointSize: 3,
					opacity: 0.85,
					pointColor: paletaCategorica(nClusters),
					colorBy: 'valueA',
					lassoColor: [1, 1, 1, 1]
				});
				debug.scatterplot = scatterplot;

				try {
					const gl = (scatterplot.get('regl') as unknown as { _gl: WebGLRenderingContext })._gl;
					const info = gl.getExtension('WEBGL_debug_renderer_info');
					debug.renderer = String(
						info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)
					);
				} catch {
					debug.renderer = 'desconhecido';
				}

				scatterplot.subscribe('draw', () => (debug.eventosDraw += 1));
				scatterplot.subscribe('select', ({ points }) => {
					debug.eventosSelect += 1;
					debug.ultimaSelecao = Array.from(points);
				});
				// O evento 'filter' é publicado pela lib, mas falta na união de tipos de `subscribe`
				// (regl-scatterplot 1.16.0); daí o cast.
				(scatterplot.subscribe as (evento: string, fn: () => void) => unknown)(
					'filter',
					() => (debug.eventosFilter += 1)
				);
				scatterplot.subscribe('lassoEnd', () => (debug.eventosLassoEnd += 1));

				await scatterplot.draw(linhas, { zDataType: 'categorical' });
				await proximoQuadro();
				await proximoQuadro();

				debug.msAtePrimeiroDesenho = performance.now() - t0;
				debug.msDesdeNavegacao = performance.now();
				debug.desenhado = true;
				status = `desenhado: ${linhas.length} pontos em ${debug.msAtePrimeiroDesenho.toFixed(0)} ms`;

				observador = new ResizeObserver(() => {
					const r = canvas.getBoundingClientRect();
					scatterplot?.set({ width: r.width, height: r.height });
				});
				observador.observe(canvas);
			} catch (e) {
				debug.erro = e instanceof Error ? `${e.name}: ${e.message}` : String(e);
				status = `erro: ${debug.erro}`;
				console.error('[mapa] falha ao desenhar', e);
			}
		})();

		return () => {
			observador?.disconnect();
			scatterplot?.destroy();
			debug.scatterplot = null;
		};
	});
</script>

<canvas data-testid="canvas-mapa" bind:this={canvas}></canvas>
<p class="status" data-testid="status-mapa">{status}</p>

<style>
	canvas {
		position: fixed;
		inset: 0;
		width: 100vw;
		height: 100vh;
		display: block;
	}
	.status {
		position: fixed;
		right: 8px;
		bottom: 8px;
		z-index: 2;
		margin: 0;
		padding: 4px 8px;
		background: rgb(10 14 31 / 0.85);
		color: #9aa3c7;
	}
</style>
