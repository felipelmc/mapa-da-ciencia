<script lang="ts" module>
	export interface ObraDesenhada {
		id: string;
		/** "Autor (ano)" e o título, numa linha. */
		rotulo: string;
		n: number;
		/** Documentos citantes por fatia (na ordem de `cores`). */
		fatias: number[];
	}
</script>

<script lang="ts">
	/**
	 * O cânone em barras horizontais: cada obra, com o número de documentos do recorte que a citam, empilhado pelo
	 * macrotema de quem cita. Numa tela larga, o rótulo fica à esquerda da barra; numa estreita, em cima dela. Passar o
	 * mouse numa obra mostra a referência inteira e os citantes por macrotema.
	 */
	import { formatarInteiro } from '$lib/formato';
	import Dica from '$lib/graficos/Dica.svelte';

	let {
		obras,
		cores,
		nomes
	}: {
		obras: ObraDesenhada[];
		/** Cor de cada fatia (os macrotemas e, por último, "sem tópico"). */
		cores: string[];
		nomes: string[];
	} = $props();

	let largura = $state(700);
	const larga = $derived(largura >= 640);
	const LINHA = $derived(larga ? 24 : 40);
	const rotuloL = $derived(larga ? Math.round(largura * 0.44) : 0);
	const VALOR = 36;
	const barraL = $derived(Math.max(40, largura - rotuloL - VALOR - (larga ? 12 : 0)));
	const maximo = $derived(Math.max(1, ...obras.map((o) => o.n)));
	const altura = $derived(obras.length * LINHA + 4);
	const caracteres = $derived(Math.max(12, Math.floor((larga ? rotuloL - 8 : largura) / 6.4)));
	const cortar = (texto: string) => (texto.length > caracteres ? `${texto.slice(0, caracteres - 1)}…` : texto);
	const segmentos = (o: ObraDesenhada) => {
		let x = 0;
		return o.fatias
			.map((v, k) => {
				const w = (v / maximo) * barraL;
				const s = { k, x, w, v };
				x += w;
				return s;
			})
			.filter((s) => s.v > 0);
	};
	let sobre = $state<{ i: number; x: number; y: number } | null>(null);
	const linhasDica = $derived.by(() => {
		if (!sobre) return [];
		const o = obras[sobre.i];
		const partes = o.fatias
			.map((v, k) => [nomes[k], v] as const)
			.filter(([, v]) => v > 0)
			.sort((a, b) => b[1] - a[1])
			.slice(0, 3)
			.map(([nome, v]) => `${nome}: ${formatarInteiro(v)}`);
		return [o.rotulo, `Citada por ${formatarInteiro(o.n)} ${o.n === 1 ? 'documento' : 'documentos'} do recorte`, ...partes];
	});
	function mover(e: PointerEvent, i: number) {
		const caixa = (e.currentTarget as SVGElement).ownerSVGElement!.getBoundingClientRect();
		sobre = { i, x: e.clientX - caixa.left, y: e.clientY - caixa.top };
	}
	const descricao = $derived(
		`Barras horizontais: as ${formatarInteiro(obras.length)} obras mais citadas no recorte, cada uma com os documentos que a citam, divididos pelo macrotema de quem cita. A tabela tem os mesmos números.`
	);
</script>

<div class="canone" bind:clientWidth={largura}>
	<svg width={largura} height={altura} role="img" aria-label={descricao}>
		{#each obras as o, i (o.id)}
			{@const y = i * LINHA}
			{@const yBarra = larga ? y + 5 : y + 20}
			<g
				data-testid="obra"
				data-n={o.n}
				class:apagada={sobre !== null && sobre.i !== i}
				role="presentation"
				onpointermove={(e) => mover(e, i)}
				onpointerleave={() => (sobre = null)}
			>
				<rect class="alvo" x="0" y={y} width={largura} height={LINHA} />
				<text class="rotulo" x="0" y={larga ? y + 16 : y + 13}>{cortar(o.rotulo)}</text>
				{#each segmentos(o) as s (s.k)}
					<rect x={rotuloL + (larga ? 12 : 0) + s.x} y={yBarra} width={Math.max(0.5, s.w - 0.5)} height="14" style:fill={cores[s.k]}>
						<title>{nomes[s.k]}: {formatarInteiro(s.v)}</title>
					</rect>
				{/each}
				<text class="valor" x={rotuloL + (larga ? 12 : 0) + (o.n / maximo) * barraL + 5} y={yBarra + 11}>{formatarInteiro(o.n)}</text>
			</g>
		{/each}
	</svg>
	{#if sobre && linhasDica.length}
		<Dica x={sobre.x} y={sobre.y} linhas={linhasDica} limites={{ largura, altura }} />
	{/if}
</div>

<style>
	.canone {
		position: relative;
		width: 100%;
	}

	.alvo {
		fill: transparent;
	}

	.apagada {
		opacity: 0.45;
	}

	svg {
		display: block;
		overflow: visible;
	}

	.rotulo {
		font-family: var(--fonte-interface);
		font-size: 0.78rem;
		fill: var(--texto);
	}

	.valor {
		font-family: var(--fonte-mono);
		font-size: 0.7rem;
		fill: var(--texto-suave);
	}
</style>
