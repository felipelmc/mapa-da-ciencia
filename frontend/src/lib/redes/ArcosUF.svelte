<script lang="ts" module>
	export interface Arco {
		/** Siglas dos dois lugares (`EX` para o exterior). */
		a: string;
		b: string;
		peso: number;
		documentos: number;
	}
</script>

<script lang="ts">
	/**
	 * A colaboração entre estados: arcos entre os centros das UFs, sobre a malha da Geografia, com a espessura pelo
	 * peso fracionário no recorte. O exterior é um ponto no oceano, à direita. As UFs com colaboração são botões:
	 * o clique (ou Enter) põe a UF no recorte, e os arcos dela ficam no acento.
	 */
	import { geoPath } from 'd3-geo';
	import { formatarDecimal, formatarInteiro } from '$lib/formato';
	import Dica from '$lib/graficos/Dica.svelte';
	import { NOME_UF } from '$lib/geografia/lugares';
	import { caminhos, projecaoBrasil, type PropsUF, type Regiao } from '$lib/geografia/malhas';
	import { EXTERIOR } from './calculo';

	let {
		regioes,
		arcos,
		ativas,
		selecionadas,
		aoEscolher
	}: {
		regioes: Regiao<PropsUF>[];
		/** Os pares do recorte. */
		arcos: Arco[];
		/** UFs com colaboração no recorte sem o filtro de UF (continuam clicáveis). */
		ativas: Set<string>;
		selecionadas: Set<string>;
		aoEscolher: (uf: string) => void;
	} = $props();

	const FAIXA_EXTERIOR = 84; // à direita do mapa, para o ponto do exterior
	let largura = $state(600);
	const altura = $derived(Math.round(Math.min(largura * 0.92, 640)));
	const projecao = $derived(projecaoBrasil(Math.max(120, largura - FAIXA_EXTERIOR), altura, regioes));
	const ds = $derived(caminhos(regioes, projecao));
	const siglas = $derived(regioes.map((r) => r.properties.sigla));
	const centros = $derived.by(() => {
		const caminho = geoPath(projecao);
		const saida = new Map<string, [number, number]>(regioes.map((r) => [r.properties.sigla, caminho.centroid(r) as [number, number]]));
		saida.set(EXTERIOR, [largura - FAIXA_EXTERIOR / 2, altura * 0.22]);
		return saida;
	});
	const nome = (k: string) => (k === EXTERIOR ? 'Exterior' : (NOME_UF[k] ?? k));

	const pesoMaximo = $derived(Math.max(1e-9, ...arcos.map((a) => a.peso)));
	const espessura = (peso: number) => 0.6 + 7 * Math.sqrt(peso / pesoMaximo);
	// do mais fino ao mais grosso, para os fortes ficarem por cima
	const desenho = $derived(
		[...arcos]
			.sort((p, q) => p.peso - q.peso)
			.map((a) => {
				const [p, q] = [centros.get(a.a), centros.get(a.b)];
				if (!p || !q) return null;
				const [mx, my] = [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2];
				// a curva se afasta da reta pela normal, sempre para o mesmo lado
				const [dx, dy] = [q[0] - p[0], q[1] - p[1]];
				const c = [mx - dy * 0.22, my + dx * 0.22];
				return {
					...a,
					d: `M${p[0].toFixed(1)},${p[1].toFixed(1)}Q${c[0].toFixed(1)},${c[1].toFixed(1)} ${q[0].toFixed(1)},${q[1].toFixed(1)}`,
					largura: espessura(a.peso),
					destaque: selecionadas.has(a.a) || selecionadas.has(a.b)
				};
			})
			.filter((a) => a !== null)
	);
	/** Peso de cada lugar somado em todos os pares dele (o tamanho do ponto). */
	const forca = $derived.by(() => {
		const saida = new Map<string, number>();
		for (const a of arcos) {
			saida.set(a.a, (saida.get(a.a) ?? 0) + a.peso);
			saida.set(a.b, (saida.get(a.b) ?? 0) + a.peso);
		}
		return saida;
	});
	const forcaMaxima = $derived(Math.max(1e-9, ...forca.values()));
	/** As UFs com as parcerias mais fortes ganham a sigla ao lado do ponto (as outras, na dica e na tabela). */
	const MAIS_ROTULADAS = 12;
	const rotuladas = $derived(
		new Set(
			[...forca.entries()]
				.filter(([k]) => k !== EXTERIOR)
				.sort((p, q) => q[1] - p[1])
				.slice(0, MAIS_ROTULADAS)
				.map(([k]) => k)
		)
	);
	const raio = (k: string) => 2 + 9 * Math.sqrt((forca.get(k) ?? 0) / forcaMaxima);

	// ---- dica
	let sobre = $state<string | null>(null);
	let dica = $state<{ x: number; y: number } | null>(null);
	function mover(evento: PointerEvent, k: string) {
		const caixa = (evento.currentTarget as SVGElement).ownerSVGElement!.getBoundingClientRect();
		sobre = k;
		dica = { x: evento.clientX - caixa.left, y: evento.clientY - caixa.top };
	}
	function focar(k: string) {
		const c = centros.get(k);
		sobre = k;
		dica = c ? { x: c[0], y: c[1] } : null;
	}
	const parceiros = (k: string) =>
		arcos
			.filter((a) => a.a === k || a.b === k)
			.sort((p, q) => q.peso - p.peso)
			.map((a) => [a.a === k ? a.b : a.a, a.peso] as const);
	const linhasDica = $derived.by(() => {
		if (!sobre) return [];
		const lista = parceiros(sobre);
		return [
			nome(sobre),
			`${formatarDecimal(forca.get(sobre) ?? 0)} de peso em ${formatarInteiro(lista.length)} parcerias no recorte`,
			...(lista.length ? [`Mais com: ${lista.slice(0, 3).map(([x, p]) => `${x === EXTERIOR ? 'Exterior' : x} (${formatarDecimal(p)})`).join(', ')}`] : [])
		];
	});
	const rotuloDe = (k: string) =>
		`${nome(k)}: ${formatarDecimal(forca.get(k) ?? 0)} de peso em parcerias com outros lugares. ` +
		(selecionadas.has(k) ? 'No recorte; Enter para tirar.' : 'Enter para filtrar.');
</script>

<div class="arcos" bind:clientWidth={largura}>
	<svg width={largura} height={altura} role="group" aria-label="Colaboração entre UFs; cada UF com parcerias é um botão que filtra o recorte">
		{#each regioes as _, i (i)}
			{@const k = siglas[i]}
			{#if ativas.has(k) || selecionadas.has(k)}
				<path
					d={ds[i]}
					class="uf ativa"
					class:selecionada={selecionadas.has(k)}
					role="button"
					tabindex="0"
					aria-pressed={selecionadas.has(k)}
					aria-label={rotuloDe(k)}
					data-testid="uf-rede"
					data-chave={k}
					onpointermove={(e) => mover(e, k)}
					onpointerleave={() => ((sobre = null), (dica = null))}
					onfocus={() => focar(k)}
					onblur={() => ((sobre = null), (dica = null))}
					onclick={() => aoEscolher(k)}
					onkeydown={(e) => {
						if (e.key === 'Enter' || e.key === ' ') {
							e.preventDefault();
							aoEscolher(k);
						}
					}}
				/>
			{:else}
				<path d={ds[i]} class="uf" aria-hidden="true" />
			{/if}
		{/each}
		<g class="desenho" aria-hidden="true">
			{#each desenho as a (`${a.a}|${a.b}`)}
				<path
					d={a.d}
					class="arco"
					class:destaque={a.destaque}
					style:stroke-width={a.largura}
					data-testid="arco"
					data-par="{a.a}|{a.b}"
					data-peso={a.peso.toFixed(6)}
				/>
			{/each}
			{#each [...forca.keys()] as k (k)}
				{@const c = centros.get(k)}
				{#if c}
					<circle cx={c[0]} cy={c[1]} r={raio(k)} class="ponto" class:destaque={selecionadas.has(k)} />
					{#if rotuladas.has(k)}
						<text x={c[0] + raio(k) + 3} y={c[1] + 4} class="sigla" data-testid="sigla-uf">{k}</text>
					{/if}
				{/if}
			{/each}
			{#if forca.has(EXTERIOR)}
				{@const c = centros.get(EXTERIOR)!}
				<text x={c[0]} y={c[1] - raio(EXTERIOR) - 7} text-anchor="middle" class="exterior">Exterior</text>
			{/if}
		</g>
	</svg>
	{#if dica && linhasDica.length}
		<Dica x={dica.x} y={dica.y} linhas={linhasDica} />
	{/if}
</div>

<style>
	.arcos {
		position: relative;
		width: 100%;
	}

	svg {
		display: block;
		overflow: visible;
	}

	.uf {
		fill: var(--seq-vazio);
		stroke: var(--fundo);
		stroke-width: 0.8;
	}

	.ativa {
		cursor: pointer;
	}

	.ativa:hover,
	.ativa:focus-visible {
		outline: none;
		stroke: var(--texto);
		stroke-width: 1.5;
	}

	.selecionada {
		fill: var(--acento-suave);
		stroke: var(--acento);
		stroke-width: 2;
	}

	.desenho {
		pointer-events: none;
	}

	.arco {
		fill: none;
		stroke: var(--texto);
		stroke-linecap: round;
		opacity: 0.4;
	}

	.arco.destaque {
		stroke: var(--acento);
		opacity: 0.75;
	}

	.ponto {
		fill: var(--texto);
		stroke: var(--fundo);
		stroke-width: 1;
		opacity: 0.85;
	}

	.ponto.destaque {
		fill: var(--acento);
	}

	.sigla {
		font-family: var(--fonte-mono);
		font-size: 0.66rem;
		fill: var(--texto);
		paint-order: stroke;
		stroke: var(--fundo);
		stroke-width: 3px;
	}

	.exterior {
		font-family: var(--fonte-mono);
		font-size: 0.7rem;
		fill: var(--texto);
		paint-order: stroke;
		stroke: var(--fundo);
		stroke-width: 3px;
	}
</style>
