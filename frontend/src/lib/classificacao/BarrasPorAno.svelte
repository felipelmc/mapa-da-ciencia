<script lang="ts">
	/**
	 * Barras 100% por ano: em cada ano, a participação de cada valor da variável entre os documentos classificados
	 * do recorte (o filtro de anos não vale aqui: os anos fora do intervalo ficam atrás de um véu, como no fluxo
	 * dos tópicos). Anos sem documento classificado ficam vazios. Cada segmento é um botão que escolhe o valor.
	 */
	import { formatarInteiro, formatarPorcentagem } from '$lib/formato';
	import Dica from '$lib/graficos/Dica.svelte';
	import Eixo from '$lib/graficos/Eixo.svelte';
	import type { PorAno, VariavelVista } from './agregar';

	let {
		dados,
		variavel,
		cores,
		intervalo,
		escolhido,
		aoEscolher
	}: {
		dados: PorAno;
		variavel: VariavelVista;
		cores: string[];
		/** Anos do recorte (os outros ficam atrás do véu); `null` = todos. */
		intervalo: [number, number] | null;
		escolhido: number | null;
		aoEscolher: (valor: number) => void;
	} = $props();

	let largura = $state(640);
	const altura = 230;
	const margem = { esq: 40, dir: 8, topo: 8, base: 24 };
	const k = $derived(variavel.valores.length);
	const nAnos = $derived(dados.anos.length);
	const passo = $derived((largura - margem.esq - margem.dir) / Math.max(1, nAnos));
	const larguraBarra = $derived(Math.max(2, passo * 0.72));
	const x = (j: number) => margem.esq + passo * (j + 0.5);
	const y = (p: number) => margem.topo + (1 - p) * (altura - margem.topo - margem.base);

	const segmentos = $derived(
		dados.anos.flatMap((ano, j) => {
			const total = dados.classificados[j];
			if (!total) return [];
			let acumulado = 0;
			return variavel.valores.map((_, v) => {
				const n = dados.n[j * k + v];
				const p0 = acumulado / total;
				acumulado += n;
				return { ano, j, v, n, total, p0, p1: acumulado / total };
			});
		})
	);
	const fora = (ano: number) => !!intervalo && (ano < intervalo[0] || ano > intervalo[1]);

	let dica = $state<{ x: number; y: number; linhas: string[] } | null>(null);
	function mostrar(evento: PointerEvent, s: (typeof segmentos)[number]) {
		const caixa = (evento.currentTarget as SVGElement).ownerSVGElement!.getBoundingClientRect();
		dica = {
			x: evento.clientX - caixa.left,
			y: evento.clientY - caixa.top,
			linhas: [
				variavel.rotulos[s.v],
				`${s.ano}: ${formatarInteiro(s.n)} de ${formatarInteiro(s.total)} classificados`,
				formatarPorcentagem(s.n / s.total)
			]
		};
	}
</script>

<div class="barras" bind:clientWidth={largura}>
	<svg width={largura} height={altura} role="group" aria-label="Participação de cada valor por ano">
		{#each segmentos as s (`${s.j}-${s.v}`)}
			{#if s.n > 0}
				<rect
					x={x(s.j) - larguraBarra / 2}
					y={y(s.p1)}
					width={larguraBarra}
					height={Math.max(0, y(s.p0) - y(s.p1))}
					style:fill={cores[s.v]}
					class:apagado={(escolhido !== null && escolhido !== s.v) || fora(s.ano)}
					role="button"
					tabindex="-1"
					aria-label="{variavel.rotulos[s.v]}, {s.ano}: {formatarPorcentagem(s.n / s.total)}"
					data-testid="segmento"
					onpointermove={(e) => mostrar(e, s)}
					onpointerleave={() => (dica = null)}
					onclick={() => aoEscolher(s.v)}
					onkeydown={() => {}}
				/>
			{/if}
		{/each}
		{#each dados.anos as ano, j (ano)}
			{#if !dados.classificados[j] && dados.total[j]}
				<text class="vazio" x={x(j)} y={y(0.5)} text-anchor="middle">·</text>
			{/if}
		{/each}
		<Eixo orientacao="x" anos={dados.anos} posicao={altura - margem.base} escala={x} comprimento={largura} />
		<Eixo orientacao="y" posicao={margem.esq - 4} escala={y} dominio={[0, 1]} comprimento={altura - margem.topo - margem.base} porcentagem />
	</svg>
	{#if dica}<Dica x={dica.x} y={dica.y} linhas={dica.linhas} />{/if}
</div>

<ul class="legenda" aria-label="Valores">
	{#each variavel.valores as _, v (v)}
		<li>
			<button type="button" aria-pressed={escolhido === v} onclick={() => aoEscolher(v)} data-testid="legenda-valor">
				<span class="amostra" style:background={cores[v]}></span>{variavel.rotulos[v]}
			</button>
		</li>
	{/each}
</ul>

<style>
	.barras {
		position: relative;
		width: 100%;
	}

	svg {
		display: block;
		overflow: visible;
	}

	rect {
		stroke: var(--fundo);
		stroke-width: 0.5;
		cursor: pointer;
		transition: opacity 0.2s;
	}

	rect.apagado {
		opacity: 0.28;
	}

	.vazio {
		fill: var(--texto-fraco);
	}

	.legenda {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 0.9rem;
		margin: 0.6rem 0 0;
		padding: 0;
		list-style: none;
		font-size: 0.82rem;
	}

	.legenda button {
		display: inline-flex;
		gap: 0.4rem;
		align-items: center;
		padding: 0.1rem 0.2rem;
		border: 0;
		background: none;
		color: var(--texto-suave);
		font: inherit;
		cursor: pointer;
	}

	.legenda button[aria-pressed='true'] {
		color: var(--texto);
		font-weight: 600;
	}

	.amostra {
		width: 0.75rem;
		height: 0.75rem;
		border-radius: 2px;
	}

	@media (prefers-reduced-motion: reduce) {
		rect {
			transition: none;
		}
	}
</style>
