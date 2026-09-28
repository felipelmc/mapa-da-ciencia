<script lang="ts">
	/**
	 * O fluxo dos tópicos (ou dos macrotemas) no tempo: faixas empilhadas por ano, em três modos. A troca de modo
	 * é animada (sem animação com movimento reduzido); mudanças do recorte redesenham na hora, para o play ficar
	 * leve. Passar o mouse (ou o foco) numa faixa apaga as outras e mostra a dica; clicar escolhe a faixa.
	 */
	import { untrack } from 'svelte';
	import { Tween, prefersReducedMotion } from 'svelte/motion';
	import { formatarInteiro, formatarPorcentagem } from '$lib/formato';
	import Dica from '$lib/graficos/Dica.svelte';
	import Eixo from '$lib/graficos/Eixo.svelte';
	import { rotularFaixas } from '$lib/graficos/faixas';
	import { caminho, empilhar, type ModoFluxo, type SerieEmpilhada } from '$lib/graficos/fluxo';

	let {
		matriz,
		ids,
		ordem,
		modo,
		anos,
		cores,
		rotulos,
		destaque,
		janela,
		aoEscolher,
		altura = 380,
		rotuloAcao = 'abrir',
		compacto = false
	}: {
		/** Uma linha por faixa (na ordem de `ids`), uma coluna por ano: documentos. */
		matriz: Float64Array[];
		ids: number[];
		/** Ordem das faixas, de baixo para cima (índices em `ids`). */
		ordem: number[];
		modo: ModoFluxo;
		anos: number[];
		cores: Map<number, string>;
		rotulos: Map<number, string>;
		/** Faixas em destaque (as do filtro de tópicos); vazio = todas. */
		destaque: Set<number>;
		/** Colunas do intervalo de anos do recorte; fora dele, as faixas ficam veladas. */
		janela: [number, number] | null;
		aoEscolher: (id: number) => void;
		altura?: number;
		/** Verbo do clique, para o rótulo acessível ("abrir" um macrotema, "ver" um tópico). */
		rotuloAcao?: string;
		/** Pequeno múltiplo: sem rótulos nas faixas, sem eixo vertical, sem foco por faixa. */
		compacto?: boolean;
	} = $props();

	let largura = $state(800);
	const margem = $derived(
		compacto ? { esq: 2, dir: 2, topo: 2, base: 18 } : { esq: modo === 'fluxo' ? 12 : 52, dir: 12, topo: 10, base: 28 }
	);
	const nAnos = $derived(anos.length);

	// ---- empilhamento com transição entre modos: o Tween interpola um vetor plano [domínio, y0…, y1…]
	const alvo = $derived(empilhar(matriz, ids, modo, ordem));
	const plano = (e: ReturnType<typeof empilhar>) => [
		e.dominio[0],
		e.dominio[1],
		...e.series.flatMap((s) => [...s.y0, ...s.y1])
	];
	const quadro = new Tween<number[]>([]);
	let modoAnterior: ModoFluxo | null = null;
	$effect(() => {
		const novo = plano(alvo);
		const animar = modoAnterior !== null && modoAnterior !== modo && !prefersReducedMotion.current;
		untrack(() => {
			const mesmoTamanho = quadro.current.length === novo.length;
			quadro.set(novo, { duration: animar && mesmoTamanho ? 450 : 0 });
		});
		modoAnterior = modo;
	});
	const series = $derived.by((): SerieEmpilhada[] => {
		const v = quadro.current.length === 2 + alvo.series.length * 2 * nAnos ? quadro.current : plano(alvo);
		return alvo.series.map((s, k) => {
			const base = 2 + k * 2 * nAnos;
			return { id: s.id, y0: Float64Array.from(v.slice(base, base + nAnos)), y1: Float64Array.from(v.slice(base + nAnos, base + 2 * nAnos)) };
		});
	});
	const dominio = $derived((quadro.current.length >= 2 ? [quadro.current[0], quadro.current[1]] : alvo.dominio) as [number, number]);

	const x = $derived((j: number) => margem.esq + (j * (largura - margem.esq - margem.dir)) / Math.max(1, nAnos - 1));
	const y = $derived((v: number) => {
		const [a, b] = dominio;
		return altura - margem.base - ((v - a) / (b - a || 1)) * (altura - margem.topo - margem.base);
	});

	// ---- rótulos dentro das faixas (medidos no canvas)
	let medidor: CanvasRenderingContext2D | null = null;
	function medir(texto: string): number {
		medidor ??= document.createElement('canvas').getContext('2d');
		if (!medidor) return texto.length * 6.5;
		medidor.font = '500 12px "Instrument Sans Variable", sans-serif';
		return medidor.measureText(texto).width;
	}
	const textos = $derived(rotulos);
	const rotulosFaixas = $derived(
		compacto || typeof document === 'undefined' ? [] : rotularFaixas(series, textos, x, y, medir)
	);

	// ---- dica
	let sobre = $state<number | null>(null);
	let dica = $state<{ x: number; y: number; coluna: number } | null>(null);
	const totalAno = $derived(Array.from({ length: nAnos }, (_, j) => matriz.reduce((s, linha) => s + linha[j], 0)));
	function mover(evento: PointerEvent, id: number) {
		const caixa = (evento.currentTarget as SVGElement).ownerSVGElement!.getBoundingClientRect();
		const px = evento.clientX - caixa.left;
		const coluna = Math.max(0, Math.min(nAnos - 1, Math.round(((px - margem.esq) / (largura - margem.esq - margem.dir)) * (nAnos - 1))));
		sobre = id;
		dica = { x: px, y: evento.clientY - caixa.top, coluna };
	}
	const linhasDica = $derived.by(() => {
		if (sobre === null || !dica) return [];
		const k = ids.indexOf(sobre);
		const n = matriz[k]?.[dica.coluna] ?? 0;
		const total = totalAno[dica.coluna];
		return [
			rotulos.get(sobre) ?? '',
			`${anos[dica.coluna]}: ${formatarInteiro(n)} documentos`,
			total ? `${formatarPorcentagem(n / total)} do ano` : 'nenhum documento no ano'
		];
	});
	const apagada = (id: number) => (sobre !== null && sobre !== id) || (destaque.size > 0 && !destaque.has(id));
	const totalFaixa = (id: number) => matriz[ids.indexOf(id)]?.reduce((s, v) => s + v, 0) ?? 0;
</script>

<div class="fluxo" bind:clientWidth={largura}>
	<svg width={largura} height={altura} role="group" aria-label="Fluxo no tempo">
		{#each series as s (s.id)}
			<path
				d={caminho(s, x, y)}
				style:fill={cores.get(s.id) ?? 'var(--linha-forte)'}
				class:apagada={apagada(s.id)}
				role="button"
				tabindex={compacto ? -1 : 0}
				data-testid={compacto ? 'faixa-mini' : 'faixa'}
				data-id={s.id}
				aria-label="{rotulos.get(s.id)}: {formatarInteiro(totalFaixa(s.id))} documentos. Enter para {rotuloAcao}."
				onpointermove={(e) => mover(e, s.id)}
				onpointerleave={() => ((sobre = null), (dica = null))}
				onfocus={() => (sobre = s.id)}
				onblur={() => (sobre = null)}
				onclick={() => aoEscolher(s.id)}
				onkeydown={(e) => {
					if (e.key === 'Enter' || e.key === ' ') {
						e.preventDefault();
						aoEscolher(s.id);
					}
				}}
			/>
		{/each}
		{#if janela}
			{#if janela[0] > 0}
				<rect class="veu" x={margem.esq - 1} y={margem.topo} width={Math.max(0, x(janela[0] - 0.5) - margem.esq + 1)} height={altura - margem.topo - margem.base} />
			{/if}
			{#if janela[1] < nAnos - 1}
				<rect class="veu" x={x(janela[1] + 0.5)} y={margem.topo} width={Math.max(0, largura - margem.dir - x(janela[1] + 0.5) + 1)} height={altura - margem.topo - margem.base} />
			{/if}
		{/if}
		{#each rotulosFaixas as r (r.id)}
			<text class="rotulo" class:apagado={apagada(r.id)} x={r.x} y={r.y + 4} text-anchor="middle">{r.texto}</text>
		{/each}
		<Eixo
			orientacao="x"
			anos={compacto ? [anos[0], anos[anos.length - 1]] : anos}
			posicao={altura - margem.base}
			escala={compacto ? (j) => x(j === 0 ? 0 : nAnos - 1) : x}
			comprimento={compacto ? 60 : largura}
			pontas={compacto}
		/>
		{#if modo !== 'fluxo' && !compacto}
			<Eixo
				orientacao="y"
				posicao={margem.esq - 4}
				escala={y}
				dominio={dominio}
				comprimento={altura - margem.topo - margem.base}
				porcentagem={modo === 'proporcao'}
			/>
		{/if}
	</svg>
	{#if dica && linhasDica.length}
		<Dica x={dica.x} y={dica.y} linhas={linhasDica} />
	{/if}
</div>

<style>
	.fluxo {
		position: relative;
		width: 100%;
	}

	svg {
		display: block;
		overflow: visible;
	}

	path {
		stroke: var(--fundo);
		stroke-width: 0.6;
		cursor: pointer;
		transition: opacity 0.2s;
	}

	path:focus-visible {
		outline: none;
		stroke: var(--texto);
		stroke-width: 2;
	}

	.apagada {
		opacity: 0.22;
	}

	.veu {
		fill: var(--fundo);
		opacity: 0.6;
		pointer-events: none;
	}

	.rotulo {
		font-size: 12px;
		font-weight: 500;
		fill: var(--fundo);
		pointer-events: none;
		paint-order: stroke;
	}

	.rotulo.apagado {
		opacity: 0.3;
	}

	@media (prefers-reduced-motion: reduce) {
		path {
			transition: none;
		}
	}
</style>
