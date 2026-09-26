<script lang="ts" generics="P extends { [k: string]: unknown }">
	/**
	 * Mapa coroplético de regiões (UFs ou países): a cor é a classe do peso fracionário no recorte (escala
	 * logarítmica com limites redondos, `escala.ts`). Regiões com documentos são botões: o mouse ou o foco mostram a
	 * dica, e o clique (ou Enter) põe ou tira a região do recorte. Regiões em `fora` (o Brasil no mapa-múndi) ficam
	 * hachuradas e fora da escala, para não achatar as outras.
	 */
	import type { GeoProjection } from 'd3-geo';
	import { formatarDecimal, formatarInteiro } from '$lib/formato';
	import Dica from '$lib/graficos/Dica.svelte';
	import { classe, corDaClasse, quebras } from './escala';
	import { caminhos, type Regiao } from './malhas';

	let {
		id,
		regioes,
		chave,
		projetar,
		valores,
		documentos,
		selecionados,
		fora = new Set<string>(),
		nome,
		aoEscolher,
		proporcao = 1,
		rotulo
	}: {
		/** Prefixo dos testids e do id da hachura. */
		id: string;
		regioes: Regiao<P>[];
		chave: (r: Regiao<P>) => string | null;
		projetar: (largura: number, altura: number, regioes: Regiao<P>[]) => GeoProjection;
		/** Peso fracionário por chave. */
		valores: Map<string, number>;
		/** Documentos (contagem inteira) por chave. */
		documentos: Map<string, number>;
		selecionados: Set<string>;
		fora?: Set<string>;
		nome: (chave: string) => string;
		aoEscolher: (chave: string) => void;
		/** Altura ÷ largura. */
		proporcao?: number;
		rotulo: string;
	} = $props();

	let largura = $state(600);
	const altura = $derived(Math.round(largura * proporcao));
	const projecao = $derived(projetar(largura, altura, regioes));
	const ds = $derived(caminhos(regioes, projecao));
	const chaves = $derived(regioes.map(chave));

	const limites = $derived(quebras([...valores].filter(([k]) => !fora.has(k)).map(([, v]) => v)));
	const nClasses = $derived(limites.length + 1);
	const cor = (k: string | null) => {
		if (k && fora.has(k)) return `url(#hachura-${id})`;
		return corDaClasse(classe(k ? (valores.get(k) ?? 0) : 0, limites), nClasses);
	};
	const ativa = (k: string | null): k is string => !!k && (valores.get(k) ?? 0) > 0;

	let sobre = $state<string | null>(null);
	let dica = $state<{ x: number; y: number } | null>(null);
	function mover(evento: PointerEvent, k: string) {
		const caixa = (evento.currentTarget as SVGElement).ownerSVGElement!.getBoundingClientRect();
		sobre = k;
		dica = { x: evento.clientX - caixa.left, y: evento.clientY - caixa.top };
	}
	function focar(evento: FocusEvent, k: string) {
		const alvo = evento.currentTarget as SVGGraphicsElement;
		const caixa = alvo.getBBox();
		sobre = k;
		dica = { x: caixa.x + caixa.width / 2, y: caixa.y };
	}
	const linhasDica = $derived.by(() => {
		if (!sobre) return [];
		const v = valores.get(sobre) ?? 0;
		const n = documentos.get(sobre) ?? 0;
		return [nome(sobre), `${formatarDecimal(v)} de peso fracionário`, `${formatarInteiro(n)} documentos com afiliação aqui`];
	});
	const rotuloDe = (k: string) =>
		`${nome(k)}: ${formatarDecimal(valores.get(k) ?? 0)} de peso, ${formatarInteiro(documentos.get(k) ?? 0)} documentos. ` +
		(selecionados.has(k) ? 'No recorte; Enter para tirar.' : 'Enter para filtrar.');

	const legenda = $derived.by(() => {
		const itens: { cor: string; texto: string }[] = [];
		const fmt = (x: number) => formatarInteiro(x);
		for (let c = 1; c <= nClasses; c += 1) {
			const de = c === 1 ? null : limites[c - 2];
			const ate = c === nClasses ? null : limites[c - 1];
			const texto = de === null ? `menos de ${fmt(ate ?? 0)}` : ate === null ? `${fmt(de)} ou mais` : `${fmt(de)} a ${fmt(ate)}`;
			itens.push({ cor: corDaClasse(c, nClasses), texto: nClasses === 1 ? 'com documentos' : texto });
		}
		return itens;
	});
</script>

<div class="mapa" bind:clientWidth={largura}>
	<svg width={largura} height={altura} role="group" aria-label={rotulo}>
		<defs>
			<pattern id="hachura-{id}" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
				<rect width="6" height="6" fill="var(--seq-6)" />
				<line x1="0" y1="0" x2="0" y2="6" stroke="var(--fundo)" stroke-width="2.5" />
			</pattern>
		</defs>
		{#each regioes as _, i (i)}
			{#if !ativa(chaves[i])}
				<path d={ds[i]} class="regiao" style:fill={cor(chaves[i])} aria-hidden="true" />
			{/if}
		{/each}
		{#each regioes as _, i (i)}
			{@const k = chaves[i]}
			{#if ativa(k)}
				<path
					d={ds[i]}
					class="regiao ativa"
					class:selecionada={selecionados.has(k)}
					class:apagada={selecionados.size > 0 && !selecionados.has(k)}
					style:fill={cor(k)}
					role="button"
					tabindex="0"
					aria-pressed={selecionados.has(k)}
					aria-label={rotuloDe(k)}
					data-testid={id}
					data-chave={k}
					data-valor={(valores.get(k) ?? 0).toFixed(4)}
					onpointermove={(e) => mover(e, k)}
					onpointerleave={() => ((sobre = null), (dica = null))}
					onfocus={(e) => focar(e, k)}
					onblur={() => ((sobre = null), (dica = null))}
					onclick={() => aoEscolher(k)}
					onkeydown={(e) => {
						if (e.key === 'Enter' || e.key === ' ') {
							e.preventDefault();
							aoEscolher(k);
						}
					}}
				/>
			{/if}
		{/each}
	</svg>
	{#if dica && linhasDica.length}
		<Dica x={dica.x} y={dica.y} linhas={linhasDica} />
	{/if}
	<ul class="legenda" aria-label="Legenda: peso fracionário">
		<li><span class="caixa" style:background="var(--seq-vazio)"></span>nenhum</li>
		{#each legenda as item (item.texto)}
			<li><span class="caixa" style:background={item.cor}></span>{item.texto}</li>
		{/each}
		{#each [...fora] as k (k)}
			<li>
				<svg class="caixa" width="14" height="14" aria-hidden="true"><rect width="14" height="14" fill="url(#hachura-{id})" /></svg>
				{nome(k)}, fora da escala ({formatarDecimal(valores.get(k) ?? 0)})
			</li>
		{/each}
	</ul>
</div>

<style>
	.mapa {
		position: relative;
		width: 100%;
	}

	svg {
		display: block;
		overflow: visible;
	}

	.regiao {
		stroke: var(--fundo);
		stroke-width: 0.6;
		transition: opacity var(--duracao);
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
		stroke: var(--acento);
		stroke-width: 2;
	}

	.apagada {
		opacity: 0.45;
	}

	.legenda {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem 1rem;
		margin: 0.6rem 0 0;
		padding: 0;
		list-style: none;
		font-size: 0.78rem;
		color: var(--texto-suave);
	}

	.legenda li {
		display: flex;
		align-items: center;
		gap: 0.35rem;
	}

	.caixa {
		display: inline-block;
		width: 14px;
		height: 14px;
		border-radius: 2px;
		border: 1px solid var(--linha);
	}

	@media (prefers-reduced-motion: reduce) {
		.regiao {
			transition: none;
		}
	}
</style>
