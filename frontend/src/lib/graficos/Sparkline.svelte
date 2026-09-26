<script lang="ts">
	/**
	 * Série pequena: a participação observada em cada ano (pontos) e a curva ajustada pela tendência (tracejada).
	 * Anos sem documentos no recorte ficam sem ponto.
	 */
	let {
		observado,
		ajustado = null,
		largura = 120,
		altura = 30,
		cor = 'currentColor',
		rotulo
	}: {
		observado: (number | null)[];
		ajustado?: number[] | null;
		largura?: number;
		altura?: number;
		cor?: string;
		rotulo: string;
	} = $props();

	const n = $derived(observado.length);
	const maximo = $derived(
		Math.max(1e-9, ...observado.filter((v): v is number => v !== null), ...(ajustado ?? []))
	);
	const x = (j: number) => 2 + (j * (largura - 4)) / Math.max(1, n - 1);
	const y = (v: number) => altura - 2 - (v / maximo) * (altura - 4);
	const curva = $derived(ajustado ? ajustado.map((v, j) => `${j ? 'L' : 'M'}${x(j).toFixed(1)},${y(v).toFixed(1)}`).join('') : '');
</script>

<svg width={largura} height={altura} viewBox="0 0 {largura} {altura}" role="img" aria-label={rotulo}>
	{#if curva}<path d={curva} class="ajuste" style:stroke={cor} />{/if}
	{#each observado as v, j (j)}
		{#if v !== null}<circle cx={x(j)} cy={y(v)} r="1.8" style:fill={cor} />{/if}
	{/each}
</svg>

<style>
	svg {
		display: block;
		overflow: visible;
	}

	.ajuste {
		fill: none;
		stroke-width: 1.4;
		stroke-dasharray: 3 2;
		opacity: 0.9;
	}
</style>
