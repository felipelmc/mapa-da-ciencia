<script lang="ts">
	/**
	 * A vista do mapa: a nuvem de documentos, o "colorir por", a legenda e o contador. Todo o estado vem da URL
	 * (`filtrosDaPagina`) e volta para ela (`mudarFiltros`): um link reproduz exatamente o que está na tela.
	 */
	import type { Topicos } from '$lib/contrato/tipos';
	import { paraNdc, type TabelaDocumentos } from '$lib/dados/documentos';
	import { filtrosDaPagina, mudarFiltros } from '$lib/estado/filtros';
	import { tema } from '$lib/estado/tema.svelte';
	import { CORES_POR, type CorPor } from '$lib/estado/url';
	import { formatarInteiro } from '$lib/formato';
	import Nuvem, { type Anotacao, type Camera } from '$lib/graficos/Nuvem.svelte';
	import Rotulos, { type ItemRotulo } from '$lib/graficos/Rotulos.svelte';
	import { calcularContornos, centroDePeso } from './contornos';
	import { colorir, type ItemLegenda } from './cores';
	import { visiveis } from './filtro';

	let { tabela, topicos }: { tabela: TabelaDocumentos; topicos: Topicos } = $props();

	const filtros = $derived(filtrosDaPagina());

	let fundo = $state('#0a0e1f');
	let cinza = $state('#3b4579');
	let acento = $state('#ffb547');
	$effect(() => {
		void tema.atual; // relê as cores quando o tema muda
		const estilo = getComputedStyle(document.documentElement);
		fundo = estilo.getPropertyValue('--fundo').trim() || fundo;
		cinza = estilo.getPropertyValue('--linha-forte').trim() || cinza;
		acento = estilo.getPropertyValue('--acento').trim() || acento;
	});

	const coloracao = $derived(colorir(tabela, topicos, filtros.cor, cinza));
	const indicesVisiveis = $derived(visiveis(tabela, filtros));
	const nVisiveis = $derived(indicesVisiveis?.length ?? tabela.n);
	// A câmera do link vale só na montagem; depois, quem manda na câmera é quem usa o mapa.
	// svelte-ignore state_referenced_locally
	const vistaInicial = filtros.vista;

	const NOMES_COR: Record<CorPor, string> = { topico: 'tópico', macrotema: 'macrotema', revista: 'revista', ano: 'ano' };

	function ativo(item: ItemLegenda): boolean {
		if (item.revista) return filtros.revistas.includes(item.revista);
		return !!item.topicos?.length && item.topicos.every((t) => filtros.topicos.includes(t));
	}

	function alternar(item: ItemLegenda) {
		if (item.revista) {
			const r = item.revista;
			const revistas = filtros.revistas.includes(r) ? filtros.revistas.filter((x) => x !== r) : [...filtros.revistas, r];
			mudarFiltros({ revistas });
		} else if (item.topicos) {
			const ids = item.topicos;
			const topicosNovos = ativo(item)
				? filtros.topicos.filter((t) => !ids.includes(t))
				: [...new Set([...filtros.topicos, ...ids])];
			mudarFiltros({ topicos: topicosNovos });
		}
	}

	const temRecorte = $derived(!!(filtros.anos || filtros.revistas.length || filtros.topicos.length));

	// ---- contornos (uma vez) e rótulos (a cada movimento da câmera)
	const ZOOM_TOPICOS = 1.8; // abaixo, rótulos dos macrotemas; acima, dos tópicos
	const contornos = $derived(calcularContornos(tabela, topicos.topicos.map((t) => t.id)));
	const macroDoTopico = $derived(new Map(topicos.macrotemas.flatMap((m) => m.topicos.map((t) => [t, m] as const))));
	const posicao = $derived(
		new Map(topicos.topicos.map((t) => [t.id, paraNdc(tabela.escala, t.centroide[0], t.centroide[1])]))
	);

	const anotacoes = $derived.by(() => {
		const neutra = filtros.cor === 'revista' || filtros.cor === 'ano';
		const saida: Anotacao[] = [];
		for (const t of topicos.topicos) {
			if (filtros.topicos.length && !filtros.topicos.includes(t.id)) continue;
			const cor = neutra ? cinza : filtros.cor === 'macrotema' ? (macroDoTopico.get(t.id)?.cor ?? t.cor) : t.cor;
			for (const anel of contornos.get(t.id) ?? []) saida.push({ vertices: anel, cor, largura: neutra ? 1 : 1.5 });
		}
		return saida;
	});

	let tela: HTMLDivElement;
	function repassarRoda(evento: WheelEvent) {
		evento.preventDefault();
		tela.querySelector('canvas')?.dispatchEvent(new WheelEvent('wheel', evento));
	}

	let camera = $state<Camera | null>(null);
	let versaoCamera = $state(0);
	function aoVer(c: Camera) {
		camera = c;
		versaoCamera += 1;
	}

	const rotulos = $derived.by((): ItemRotulo[] => {
		const zoom = camera?.zoom ?? 1;
		if (zoom < ZOOM_TOPICOS && !filtros.topicos.length) {
			return topicos.macrotemas.map((m) => {
				const membros = topicos.topicos.filter((t) => m.topicos.includes(t.id));
				const [x, y] = centroDePeso(membros.map((t) => ({ x: posicao.get(t.id)![0], y: posicao.get(t.id)![1], peso: t.n })));
				const item: ItemLegenda = { rotulo: m.rotulo, cor: m.cor, topicos: m.topicos };
				return { id: `m${m.id}`, texto: m.rotulo, x, y, cor: m.cor, peso: 1e6 + membros.reduce((s, t) => s + t.n, 0), ativo: ativo(item), aoClicar: () => alternar(item) };
			});
		}
		return topicos.topicos
			.filter((t) => !filtros.topicos.length || filtros.topicos.includes(t.id))
			.map((t) => {
				const [x, y] = posicao.get(t.id)!;
				const item: ItemLegenda = { rotulo: t.rotulo, cor: t.cor, topicos: [t.id] };
				return { id: `t${t.id}`, texto: t.rotulo, x, y, cor: t.cor, peso: t.n, ativo: ativo(item), aoClicar: () => alternar(item) };
			});
	});
</script>

<div class="mapa">
	<div class="tela" bind:this={tela}>
		<Nuvem
			x={tabela.x}
			y={tabela.y}
			valores={coloracao.valores}
			tipo={coloracao.tipo}
			cores={coloracao.cores}
			visiveis={indicesVisiveis}
			selecionados={[]}
			destaque={null}
			{fundo}
			corLaco={acento}
			modoLaco={false}
			vista={vistaInicial}
			{anotacoes}
			{aoVer}
			aoClicar={() => {}}
			aoLaco={() => {}}
			aoMoverCamera={(v) => mudarFiltros({ vista: v }, { substituir: true, em: '/mapa' })}
		/>
		<Rotulos
			itens={rotulos}
			projetar={camera?.projetar ?? null}
			versao={versaoCamera}
			largura={camera?.largura ?? 0}
			altura={camera?.altura ?? 0}
			aoRoda={repassarRoda}
		/>
	</div>

	<aside class="painel" aria-label="Controles do mapa">
		<h1>Mapa</h1>
		<p class="contador numero" data-testid="contador-mapa" aria-live="polite">
			{formatarInteiro(nVisiveis)}
			<span>de {formatarInteiro(tabela.n)} documentos</span>
		</p>
		<label class="campo">
			<span class="rotulo-miudo">Colorir por</span>
			<select
				data-testid="cor-por"
				value={filtros.cor}
				onchange={(e) => mudarFiltros({ cor: e.currentTarget.value as CorPor })}
			>
				{#each CORES_POR as c (c)}
					<option value={c}>{NOMES_COR[c]}</option>
				{/each}
			</select>
		</label>
		{#if temRecorte}
			<button class="limpar" type="button" onclick={() => mudarFiltros({ anos: null, revistas: [], topicos: [] })}>
				Limpar filtros
			</button>
		{/if}
		{#if coloracao.tipo === 'continuous'}
			<div class="degrade" style:--de={coloracao.cores[0]} style:--ate={coloracao.cores.at(-1)}>
				<span>{coloracao.legenda[0].rotulo}</span><span>{coloracao.legenda[1].rotulo}</span>
			</div>
		{:else}
			<ul class="legenda" data-testid="legenda-mapa">
				{#each coloracao.legenda as item (item.rotulo + item.cor)}
					<li>
						<button
							type="button"
							class:ativo={ativo(item)}
							aria-pressed={ativo(item)}
							onclick={() => alternar(item)}
							title="Mostrar só {item.rotulo}"
						>
							<span class="cor" style:background={item.cor}></span>
							<span class="nome">{item.rotulo}</span>
						</button>
					</li>
				{/each}
			</ul>
		{/if}
	</aside>
</div>

<style>
	.mapa {
		position: relative;
		height: 100%;
		overflow: hidden;
	}

	.tela {
		position: absolute;
		inset: 0;
	}

	.painel {
		position: absolute;
		top: 1rem;
		left: 1rem;
		width: min(18rem, calc(100% - 2rem));
		max-height: calc(100% - 2rem);
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		padding: 1rem;
		background: color-mix(in oklab, var(--superficie) 88%, transparent);
		border: 1px solid var(--linha);
		border-radius: 0.75rem;
		backdrop-filter: blur(6px);
		overflow: hidden;
	}

	h1 {
		font-family: var(--fonte-titulo);
		font-size: 1.5rem;
		font-weight: 500;
		margin: 0;
	}

	.contador {
		margin: 0;
		font-size: 1.25rem;
	}

	.contador span {
		font-size: 0.8rem;
		color: var(--texto-suave);
	}

	.campo {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	select,
	.limpar {
		font: inherit;
		color: var(--texto);
		background: var(--superficie-alta);
		border: 1px solid var(--linha-forte);
		border-radius: 0.4rem;
		padding: 0.35rem 0.5rem;
	}

	.limpar {
		cursor: pointer;
		align-self: flex-start;
	}

	.legenda {
		list-style: none;
		margin: 0;
		padding: 0;
		overflow-y: auto;
		min-height: 0;
	}

	.legenda button {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		width: 100%;
		padding: 0.2rem 0.25rem;
		font: inherit;
		font-size: 0.85rem;
		text-align: left;
		color: var(--texto);
		background: none;
		border: 0;
		border-radius: 0.3rem;
		cursor: pointer;
	}

	.legenda button:hover,
	.legenda button.ativo {
		background: var(--superficie-alta);
	}

	.legenda button.ativo .nome {
		font-weight: 600;
	}

	.cor {
		flex: none;
		width: 0.75rem;
		height: 0.75rem;
		border-radius: 50%;
	}

	.nome {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.degrade {
		display: flex;
		justify-content: space-between;
		padding-top: 1.1rem;
		font-size: 0.8rem;
		color: var(--texto-suave);
		background: linear-gradient(to right, var(--de), var(--ate)) top / 100% 0.6rem no-repeat;
		border-radius: 0.3rem;
	}

	@media (max-width: 820px) {
		.painel {
			top: auto;
			bottom: 1rem;
			max-height: 40%;
		}
	}
</style>
