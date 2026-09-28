<script lang="ts">
	/**
	 * O fluxo de citações entre macrotemas: a linha é o macrotema de quem cita, a coluna o de quem é citado, e cada
	 * célula traz a contagem. A cor segue as classes logarítmicas dos mapas (`geografia/escala.ts`), e o número usa a
	 * cor de texto própria de cada tom (`--sobre-seq-*`, com contraste AA conferido nos dois temas). Passar o mouse numa
	 * célula acende a linha e a coluna dela. Os rótulos das linhas usam a largura que sobra das células.
	 */
	import { formatarInteiro } from '$lib/formato';
	import { classe, corDaClasse, quebras, textoSobreClasse } from '$lib/geografia/escala';

	let {
		rotulos,
		cores,
		matriz
	}: {
		rotulos: string[];
		cores: string[];
		/** `matriz[linha][coluna]`: citações do macrotema da linha ao da coluna. */
		matriz: number[][];
	} = $props();

	let largura = $state(640);
	const n = $derived(rotulos.length);
	const TOPO = 26;
	// as células ficam entre 22 e 56 px; o rótulo leva o resto (no mínimo 110 px, no máximo 420)
	const lado = $derived(Math.max(22, Math.min(56, Math.floor((largura - 110 - 4) / Math.max(1, n)))));
	const ROTULO = $derived(Math.max(110, Math.min(420, largura - n * lado - 4)));
	const fonteDoValor = $derived(lado < 30 ? '0.56rem' : lado < 40 ? '0.62rem' : '0.7rem');
	let sobre = $state<[number, number] | null>(null);
	const acesa = (i: number, j: number) => !sobre || sobre[0] === i || sobre[1] === j;
	const altura = $derived(TOPO + n * lado + 4);
	const limites = $derived(quebras(matriz.flat()));
	const cor = (v: number) => corDaClasse(classe(v, limites), limites.length + 1);
	const corDoTexto = (v: number) => textoSobreClasse(classe(v, limites), limites.length + 1);
	const caracteres = $derived(Math.max(10, Math.floor((ROTULO - 26) / 6.4)));
	const cortar = (texto: string) => (texto.length > caracteres ? `${texto.slice(0, caracteres - 1)}…` : texto);
	const descricao = $derived(
		`Matriz de ${n} por ${n}: nas linhas, o macrotema de quem cita; nas colunas, o de quem é citado; em cada célula, o número de citações. A tabela tem os mesmos números.`
	);
</script>

<div class="matriz" bind:clientWidth={largura}>
	<svg width={largura} height={altura} role="img" aria-label={descricao}>
		{#each rotulos as r, j (j)}
			<g transform="translate({ROTULO + j * lado + lado / 2}, {TOPO - 8})">
				<circle cx="-7" cy="-4" r="4" style:fill={cores[j]} />
				<text class="coluna" class:forte={sobre?.[1] === j} x="0" y="0">{j + 1}</text>
				<title>{j + 1}. {r}</title>
			</g>
		{/each}
		{#each matriz as linha, i (i)}
			{@const y = TOPO + i * lado}
			<circle cx="6" cy={y + lado / 2} r="4" style:fill={cores[i]} />
			<text class="linha" class:forte={sobre?.[0] === i} x="16" y={y + lado / 2 + 4} data-testid="linha-fluxo" data-rotulo={rotulos[i]}>{i + 1}. {cortar(rotulos[i])}<title>{rotulos[i]}</title></text>
			{#each linha as v, j (j)}
				<g
					data-testid="celula-fluxo"
					data-de={i}
					data-para={j}
					data-n={v}
					class:apagada={!acesa(i, j)}
					role="presentation"
					onpointerenter={() => (sobre = [i, j])}
					onpointerleave={() => (sobre = null)}
				>
					<rect x={ROTULO + j * lado + 1} y={y + 1} width={lado - 2} height={lado - 2} rx="2" style:fill={cor(v)} class:diagonal={i === j} />
					<text class="valor" style:fill={corDoTexto(v)} style:font-size={fonteDoValor} x={ROTULO + j * lado + lado / 2} y={y + lado / 2 + 4}>{formatarInteiro(v)}</text>
					<title>{rotulos[i]} → {rotulos[j]}: {formatarInteiro(v)} citações</title>
				</g>
			{/each}
		{/each}
	</svg>
</div>

<style>
	.matriz {
		width: 100%;
	}

	svg {
		display: block;
	}

	.coluna,
	.valor {
		font-family: var(--fonte-mono);
		font-size: 0.7rem;
		text-anchor: middle;
	}

	.coluna {
		fill: var(--texto-suave);
	}

	.linha {
		font-family: var(--fonte-interface);
		font-size: 0.78rem;
		fill: var(--texto);
	}

	.diagonal {
		stroke: var(--linha-forte);
		stroke-width: 1;
	}

	.valor {
		font-weight: 600;
	}

	.forte {
		font-weight: 700;
		fill: var(--texto);
	}

	.apagada {
		opacity: 0.35;
	}
</style>
