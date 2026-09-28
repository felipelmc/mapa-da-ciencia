<script lang="ts">
	/**
	 * Eixo horizontal de anos (com marcas espaçadas para caber) ou vertical de números, em SVG. `x`/`y` convertem
	 * o valor em pixel; o eixo vertical formata em documentos ou em porcentagem.
	 */
	import { ticks } from 'd3-array';
	import { formatarInteiro, formatarPorcentagem } from '$lib/formato';

	let {
		orientacao,
		anos = [],
		posicao,
		escala,
		dominio = [0, 1],
		comprimento,
		porcentagem = false,
		pontas = false
	}: {
		orientacao: 'x' | 'y';
		/** Anos das colunas (eixo x). */
		anos?: number[];
		/** Posição do eixo: y do eixo x, ou x do eixo y, em pixels. */
		posicao: number;
		/** Valor (coluna no eixo x, número no eixo y) → pixel. */
		escala: (v: number) => number;
		dominio?: [number, number];
		/** Comprimento disponível em pixels, para decidir quantas marcas cabem. */
		comprimento: number;
		porcentagem?: boolean;
		/**
		 * Eixo x: a primeira marca começa no ponto e a última termina nele, em vez de centradas. Nos pequenos
		 * múltiplos, lado a lado, o "2025" de um não encosta no "2010" do vizinho.
		 */
		pontas?: boolean;
	} = $props();
	const ancora = (j: number) =>
		pontas && j === 0 ? 'start' : pontas && j === anos.length - 1 ? 'end' : 'middle';

	const marcasX = $derived.by(() => {
		const cabem = Math.max(2, Math.floor(comprimento / 48));
		const passo = Math.max(1, Math.ceil(anos.length / cabem));
		return anos.map((a, j) => ({ a, j })).filter(({ j }) => j % passo === 0 || j === anos.length - 1);
	});
	const marcasY = $derived(ticks(dominio[0], dominio[1], Math.max(2, Math.floor(comprimento / 40))));
</script>

{#if orientacao === 'x'}
	<g class="eixo" aria-hidden="true">
		{#each marcasX as { a, j } (a)}
			<text x={escala(j)} y={posicao + 16} text-anchor={ancora(j)}>{a}</text>
		{/each}
	</g>
{:else}
	<g class="eixo" aria-hidden="true">
		{#each marcasY as v (v)}
			<line x1={posicao} x2={posicao - 4} y1={escala(v)} y2={escala(v)} />
			<text x={posicao - 7} y={escala(v) + 4} text-anchor="end">
				{porcentagem ? formatarPorcentagem(v) : formatarInteiro(v)}
			</text>
		{/each}
	</g>
{/if}

<style>
	.eixo text {
		font-family: var(--fonte-mono);
		font-size: 0.68rem;
		fill: var(--texto-suave);
	}

	.eixo line {
		stroke: var(--linha-forte);
	}
</style>
