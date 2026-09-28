<script lang="ts">
	/**
	 * A vista do mapa: a nuvem de documentos com contornos e rótulos, o "colorir por", a legenda, a busca, o
	 * laço, a linha do tempo e o cartão do documento. Todo o estado vem da URL (`filtrosDaPagina`) e volta para
	 * ela (`mudarFiltros`): um link reproduz exatamente o que está na tela.
	 *
	 * Atalhos: `/` busca, `L` liga o laço, `Esc` fecha o cartão ou desliga o laço, `?` abre os atalhos na Ajuda.
	 */
	import { tick } from 'svelte';
	import { goto } from '$app/navigation';
	import type { Topicos } from '$lib/contrato/tipos';
	import { buscar, indiceDe } from '$lib/dados/busca';
	import type { Cubo } from '$lib/dados/cubo';
	import { deNdc, paraNdc, type TabelaDocumentos } from '$lib/dados/documentos';
	import { filtrosDaPagina, mudarFiltros } from '$lib/estado/filtros';
	import { tema } from '$lib/estado/tema.svelte';
	import { CORES_POR, rota, type CorPor } from '$lib/estado/url';
	import { formatarInteiro } from '$lib/formato';
	import { simplificar, type Ponto } from '$lib/graficos/geometria';
	import Nuvem, { type Anotacao, type Camera } from '$lib/graficos/Nuvem.svelte';
	import Rotulos, { type Caixa, type ItemRotulo } from '$lib/graficos/Rotulos.svelte';
	import Cartao from './Cartao.svelte';
	import { calcularContornos, centroDePeso } from './contornos';
	import { colorir, type ItemLegenda } from './cores';

	let {
		tabela,
		topicos,
		cubo,
		versaoMapa
	}: { tabela: TabelaDocumentos; topicos: Topicos; cubo: Cubo; versaoMapa: string } = $props();

	const filtros = $derived(filtrosDaPagina());

	// ---- cores do tema (o canvas não lê CSS)
	let fundo = $state('#0a0e1f');
	let cinza = $state('#3b4579');
	let acento = $state('#ffb547');
	$effect(() => {
		void tema.atual;
		const estilo = getComputedStyle(document.documentElement);
		fundo = estilo.getPropertyValue('--fundo').trim() || fundo;
		cinza = estilo.getPropertyValue('--linha-forte').trim() || cinza;
		acento = estilo.getPropertyValue('--acento').trim() || acento;
	});

	const coloracao = $derived(colorir(tabela, topicos, filtros.cor, cinza));

	// ---- busca (o índice é montado na primeira vez e compartilhado com o cubo)
	let campoBusca = $state<HTMLInputElement>();
	// svelte-ignore state_referenced_locally
	let textoBusca = $state(filtros.busca);
	let temporizadorBusca: ReturnType<typeof setTimeout> | undefined;
	function digitar(texto: string) {
		textoBusca = texto;
		clearTimeout(temporizadorBusca);
		temporizadorBusca = setTimeout(() => {
			temporizadorBusca = undefined;
			mudarFiltros({ busca: texto }, { substituir: true, em: '/mapa' });
		}, 250);
	}
	const buscados = $derived(filtros.busca ? buscar(indiceDe(tabela), filtros.busca) : null);
	const MAX_RESULTADOS = 6;
	// a barra do recorte pode limpar a busca: o campo acompanha
	$effect(() => {
		const busca = filtros.busca;
		if (busca === '' && textoBusca !== '' && !temporizadorBusca) textoBusca = '';
	});

	// ---- laço: polígono na URL em coordenadas dos dados (o cubo o converte para NDC)
	let modoLaco = $state(false);
	function aoLaco(vertices: Ponto[]) {
		modoLaco = false;
		const pontos = simplificar(vertices).map(([x, y]) => deNdc(tabela.escala, x, y));
		mudarFiltros({ laco: { versao: versaoMapa, pontos } });
	}

	// o recorte inteiro (anos, revistas, tópicos, busca, laço e lugares) sai do cubo compartilhado
	const indicesVisiveis = $derived(cubo.indices(cubo.falhas(filtros), 0));
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
			const novos = ativo(item) ? filtros.topicos.filter((t) => !ids.includes(t)) : [...new Set([...filtros.topicos, ...ids])];
			mudarFiltros({ topicos: novos });
		}
	}

	// ---- documento em destaque (cartão)
	const destaque = $derived(filtros.doc ? (tabela.indice.get(filtros.doc) ?? null) : null);
	const abrir = (i: number | null) => mudarFiltros({ doc: i === null ? null : tabela.ids[i] });

	// ---- contornos (uma vez) e rótulos (a cada movimento da câmera)
	const ZOOM_TOPICOS = 1.8; // abaixo, rótulos dos macrotemas; acima, dos tópicos
	const contornos = $derived(calcularContornos(tabela, topicos.topicos.map((t) => t.id)));
	const macroDoTopico = $derived(new Map(topicos.macrotemas.flatMap((m) => m.topicos.map((t) => [t, m] as const))));
	const posicao = $derived(new Map(topicos.topicos.map((t) => [t.id, paraNdc(tabela.escala, t.centroide[0], t.centroide[1])])));

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
	let raiz: HTMLDivElement;
	/** Onde estão os painéis sobre o mapa: rótulos não ficam escondidos atrás deles. */
	// caixas dos controles sobre o mapa, nas coordenadas do canvas (a `.tela`), como os rótulos
	function bloqueios(): Caixa[] {
		if (!raiz || !tela) return [];
		const base = tela.getBoundingClientRect();
		return [...raiz.querySelectorAll('[data-sobre-o-mapa]')].map((el) => {
			const r = el.getBoundingClientRect();
			return { x0: r.left - base.left - 8, y0: r.top - base.top - 8, x1: r.right - base.left + 8, y1: r.bottom - base.top + 8 };
		});
	}

	function repassarRoda(evento: WheelEvent) {
		evento.preventDefault();
		tela.querySelector('canvas')?.dispatchEvent(new WheelEvent('wheel', evento));
	}

	let camera = $state<Camera | null>(null);
	let versaoCamera = $state(0);
	function aoVer(c: Camera) {
		camera = c;
		versaoCamera += 1;
		if (window.__mapaDebug) window.__mapaDebug.laco = aoLaco; // para os testes desenharem um laço
	}

	const rotulos = $derived.by((): ItemRotulo[] => {
		const zoom = camera?.zoom ?? 1;
		if (zoom < ZOOM_TOPICOS && !filtros.topicos.length) {
			return topicos.macrotemas.map((m) => {
				const membros = topicos.topicos.filter((t) => m.topicos.includes(t.id));
				const [x, y] = centroDePeso(membros.map((t) => ({ x: posicao.get(t.id)![0], y: posicao.get(t.id)![1], peso: t.n })));
				const item: ItemLegenda = { rotulo: m.rotulo, cor: m.cor, topicos: m.topicos };
				const peso = 1e6 + membros.reduce((s, t) => s + t.n, 0);
				return { id: `m${m.id}`, texto: m.rotulo, x, y, cor: m.cor, peso, ativo: ativo(item), aoClicar: () => alternar(item) };
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

	// ---- painel e atalhos
	let recolhido = $state(false);

	// cartão aberto ou painel recolhido mudam as áreas cobertas: reposiciona os rótulos depois do desenho
	$effect(() => {
		void destaque;
		void recolhido;
		tick().then(() => (versaoCamera += 1));
	});

	function tecla(evento: KeyboardEvent) {
		const alvo = evento.target as HTMLElement | null;
		if (alvo?.closest('input, select, textarea, [contenteditable]')) {
			if (evento.key === 'Escape') alvo.blur();
			return;
		}
		if (evento.metaKey || evento.ctrlKey || evento.altKey) return;
		if (evento.key === '/') {
			evento.preventDefault();
			recolhido = false;
			queueMicrotask(() => campoBusca?.focus());
		} else if (evento.key === 'l' || evento.key === 'L') {
			modoLaco = !modoLaco;
		} else if (evento.key === 'Escape') {
			if (modoLaco) modoLaco = false;
			else if (filtros.doc) abrir(null);
		} else if (evento.key === '?') {
			goto(rota('/ajuda'));
		}
	}
</script>

<div class="mapa" class:com-painel={!recolhido} bind:this={raiz}>
	<div class="tela" bind:this={tela}>
		<Nuvem
			x={tabela.x}
			y={tabela.y}
			valores={coloracao.valores}
			tipo={coloracao.tipo}
			cores={coloracao.cores}
			visiveis={indicesVisiveis}
			selecionados={[]}
			{destaque}
			{fundo}
			corLaco={acento}
			{modoLaco}
			vista={vistaInicial}
			{anotacoes}
			{aoVer}
			aoClicar={abrir}
			{aoLaco}
			aoMoverCamera={(v) => mudarFiltros({ vista: v }, { substituir: true, em: '/mapa' })}
		/>
		<Rotulos
			itens={rotulos}
			projetar={camera?.projetar ?? null}
			versao={versaoCamera}
			largura={camera?.largura ?? 0}
			altura={camera?.altura ?? 0}
			aoRoda={repassarRoda}
			inertes={modoLaco}
			{bloqueios}
		/>
	</div>

	<aside class="painel" class:recolhido aria-label="Controles do mapa" data-sobre-o-mapa>
		<div class="topo">
			<h1>Mapa</h1>
			<button type="button" class="recolher" onclick={() => (recolhido = !recolhido)} aria-expanded={!recolhido}>
				{recolhido ? 'Mostrar controles' : 'Recolher'}
			</button>
		</div>
		{#if !recolhido}
			<label class="campo">
				<span class="rotulo-miudo">Buscar título ou autor <kbd>/</kbd></span>
				<input
					type="search"
					data-testid="busca-mapa"
					bind:this={campoBusca}
					value={textoBusca}
					oninput={(e) => digitar(e.currentTarget.value)}
					placeholder="ex.: coalizão, Limongi"
				/>
			</label>
			{#if buscados}
				<ol class="resultados" data-testid="resultados-busca">
					{#each buscados.slice(0, MAX_RESULTADOS) as i (i)}
						<li><button type="button" onclick={() => abrir(i)}>{tabela.titulos[i]}</button></li>
					{:else}
						<li class="suave">Nada encontrado.</li>
					{/each}
				</ol>
				{#if buscados.length > MAX_RESULTADOS}
					<p class="suave" data-testid="mais-resultados">
						{MAX_RESULTADOS} de {formatarInteiro(buscados.length)}; refine a busca para ver os outros.
					</p>
				{/if}
			{/if}
			<div class="acoes">
				<button type="button" class="botao" aria-pressed={modoLaco} data-testid="botao-laco" onclick={() => (modoLaco = !modoLaco)}>
					{modoLaco ? 'Desenhe o laço…' : 'Laço'} <kbd>L</kbd>
				</button>
			</div>
			<label class="campo">
				<span class="rotulo-miudo">Colorir por</span>
				<select data-testid="cor-por" value={filtros.cor} onchange={(e) => mudarFiltros({ cor: e.currentTarget.value as CorPor })}>
					{#each CORES_POR as c (c)}
						<option value={c}>{NOMES_COR[c]}</option>
					{/each}
				</select>
			</label>
			{#if coloracao.tipo === 'continuous'}
				<div class="degrade" style:--de={coloracao.cores[0]} style:--ate={coloracao.cores.at(-1)}>
					<span>{coloracao.legenda[0].rotulo}</span><span>{coloracao.legenda[1].rotulo}</span>
				</div>
			{:else}
				<ul class="legenda" data-testid="legenda-mapa">
					{#each coloracao.legenda as item (item.rotulo + item.cor)}
						<li>
							<button type="button" class:ativo={ativo(item)} aria-pressed={ativo(item)} onclick={() => alternar(item)} title="Mostrar só {item.rotulo}">
								<span class="cor" style:background={item.cor}></span>
								<span class="nome">{item.rotulo}</span>
							</button>
						</li>
					{/each}
				</ul>
			{/if}
		{/if}
	</aside>

	{#if destaque !== null}
		<div class="lado" data-sobre-o-mapa>
			<Cartao {tabela} {topicos} indice={destaque} aoFechar={() => abrir(null)} aoAbrir={abrir} />
		</div>
	{/if}
</div>

<svelte:window onkeydown={tecla} />

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



	.campo {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	select {
		font: inherit;
		color: var(--texto);
		background: var(--superficie-alta);
		border: 1px solid var(--linha-forte);
		border-radius: 0.4rem;
		padding: 0.35rem 0.5rem;
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

	.topo {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.recolher {
		font: inherit;
		font-size: 0.8rem;
		color: var(--texto);
		background: var(--superficie-alta);
		border: 1px solid var(--linha-forte);
		border-radius: 0.4rem;
		padding: 0.25rem 0.55rem;
		cursor: pointer;
	}

	.acoes {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}

	input[type='search'] {
		font: inherit;
		color: var(--texto);
		background: var(--superficie-alta);
		border: 1px solid var(--linha-forte);
		border-radius: 0.4rem;
		padding: 0.35rem 0.5rem;
	}

	kbd {
		font-family: var(--fonte-mono);
		font-size: 0.7rem;
		padding: 0 0.3rem;
		border: 1px solid var(--linha-forte);
		border-radius: 0.25rem;
	}

	/* a lista não encolhe: sem isso, a legenda (com dezenas de tópicos) ficava com quase todo o painel, e os
	   resultados (e o "Nada encontrado.") com poucos pixels */
	.resultados {
		flex-shrink: 0;
		margin: 0;
		padding-left: 1.1rem;
		max-height: 9rem;
		overflow-y: auto;
		font-size: 0.8rem;
	}

	.resultados button {
		padding: 0.1rem 0;
		font: inherit;
		text-align: left;
		color: var(--texto);
		background: none;
		border: 0;
		cursor: pointer;
	}

	.resultados button:hover {
		color: var(--acento);
	}

	.suave {
		margin: 0;
		font-size: 0.8rem;
		color: var(--texto-suave);
	}



	.painel.recolhido {
		width: auto;
	}


	.lado {
		position: absolute;
		top: 1rem;
		right: 1rem;
		bottom: 1rem;
		width: min(24rem, calc(100% - 2rem));
		display: flex;
		flex-direction: column;
	}

	.lado > :global(*) {
		max-height: 100%;
	}

	/* em telas largas, o painel aberto fica ao lado do mapa, e não por cima: a nuvem inteira aparece */
	@media (min-width: 821px) {
		.mapa.com-painel .tela {
			left: 20rem;
		}
	}

	@media (max-width: 820px) {
		.lado {
			top: auto;
			height: 55%;
		}

		/* no celular, o painel rola por inteiro: a legenda não fica espremida em poucos pixels */
		.painel {
			top: auto;
			bottom: 1rem;
			max-height: 40%;
			overflow-y: auto;
		}

		.painel > :global(*) {
			flex-shrink: 0;
		}

		.legenda {
			overflow: visible;
		}
	}
</style>
