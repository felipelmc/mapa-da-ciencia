<script lang="ts">
	/**
	 * Uma série pequena por ano (a colaboração ao lado do grafo): linha, pontos e o intervalo de anos do recorte em
	 * destaque. Anos sem documentos ficam sem ponto e interrompem a linha. O eixo vertical começa no zero.
	 */
	import { formatarDecimal, formatarPorcentagem } from '$lib/formato';

	let {
		titulo,
		anos,
		valores,
		formato,
		janela = null,
		id
	}: {
		titulo: string;
		anos: number[];
		valores: (number | null)[];
		formato: 'porcentagem' | 'decimal';
		/** Anos do recorte (índices em `anos`), destacados. */
		janela?: [number, number] | null;
		id: string;
	} = $props();

	const ALTURA = 72;
	const M = { cima: 8, baixo: 18, esq: 34, dir: 6 };
	let largura = $state(260);
	const w = $derived(Math.max(60, largura - M.esq - M.dir));
	const h = ALTURA - M.cima - M.baixo;
	const maximo = $derived(
		Math.max(formato === 'porcentagem' ? 0.1 : 1, ...valores.filter((v): v is number => v !== null)) * 1.05
	);
	const px = (j: number) => M.esq + (anos.length > 1 ? (j * w) / (anos.length - 1) : w / 2);
	const py = (v: number) => M.cima + h - (v / maximo) * h;
	const texto = (v: number) => (formato === 'porcentagem' ? formatarPorcentagem(v) : formatarDecimal(v));
	// a janela do recorte dentro do eixo: um recorte fora do período (anos=2030-2031) não desenha faixa nenhuma
	const faixa = $derived.by((): [number, number] | null => {
		if (!janela || anos.length < 2) return null;
		const [a, b] = [Math.max(0, janela[0]), Math.min(anos.length - 1, janela[1])];
		return a <= b ? [a, b] : null;
	});

	const trechos = $derived.by(() => {
		const saida: string[] = [];
		let atual = '';
		valores.forEach((v, j) => {
			if (v === null) {
				if (atual) saida.push(atual);
				atual = '';
				return;
			}
			atual += `${atual ? 'L' : 'M'}${px(j).toFixed(1)},${py(v).toFixed(1)}`;
		});
		if (atual) saida.push(atual);
		return saida;
	});
	const validos = $derived(valores.map((v, j) => [v, j] as const).filter(([v]) => v !== null) as [number, number][]);
	const ultimo = $derived(validos.at(-1) ?? null);
	const descricao = $derived(
		validos.length
			? `${titulo}: de ${texto(validos[0][0])} em ${anos[validos[0][1]]} a ${texto(ultimo![0])} em ${anos[ultimo![1]]}.`
			: `${titulo}: sem documentos no recorte.`
	);
</script>

<div class="serie" bind:clientWidth={largura} data-testid="serie-{id}">
	<h3>{titulo}</h3>
	<svg width={largura} height={ALTURA} role="img" aria-label={descricao}>
		{#if faixa}
			<rect class="janela" x={px(faixa[0]) - 3} y={M.cima - 2} width={px(faixa[1]) - px(faixa[0]) + 6} height={h + 4} />
		{/if}
		<line class="base" x1={M.esq} x2={M.esq + w} y1={M.cima + h} y2={M.cima + h} />
		<text class="eixo" x={M.esq - 5} y={M.cima + h} text-anchor="end">{texto(0)}</text>
		<text class="eixo" x={M.esq - 5} y={M.cima + 8} text-anchor="end">{texto(maximo / 1.05)}</text>
		{#if anos.length}
			<text class="eixo" x={px(0)} y={ALTURA - 3} text-anchor="start">{anos[0]}</text>
			<text class="eixo" x={px(anos.length - 1)} y={ALTURA - 3} text-anchor="end">{anos.at(-1)}</text>
		{/if}
		{#each trechos as d, k (k)}<path class="linha" {d} />{/each}
		{#each validos as [v, j] (j)}<circle class="ponto" cx={px(j)} cy={py(v)} r="2" />{/each}
	</svg>
</div>

<style>
	.serie {
		min-width: 0;
	}

	h3 {
		margin: 0 0 0.2rem;
		font-family: var(--fonte-interface);
		font-size: 0.8rem;
		font-weight: 500;
		color: var(--texto-suave);
	}

	svg {
		display: block;
		overflow: visible;
	}

	.janela {
		fill: var(--acento-suave);
	}

	.base {
		stroke: var(--linha-forte);
	}

	.eixo {
		font-family: var(--fonte-mono);
		font-size: 0.62rem;
		fill: var(--texto-suave);
	}

	.linha {
		fill: none;
		stroke: var(--acento);
		stroke-width: 1.5;
	}

	.ponto {
		fill: var(--acento);
	}
</style>
