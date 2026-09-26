<script lang="ts">
	/**
	 * A gaveta de um tópico (`topico=` na URL): o que ele é (rótulo, descrição, palavras-chave, documentos
	 * representativos), como ele anda no tempo no recorte (série e tendência) e em quais revistas aparece. Dali se
	 * vai ao mapa com o tópico filtrado. `Esc` fecha; o foco vai para o título ao abrir.
	 */
	import { tick } from 'svelte';
	import type { Macrotema, Topico, Topicos } from '$lib/contrato/tipos';
	import { D, type Cubo } from '$lib/dados/cubo';
	import { ajustados, tendencia } from '$lib/estatistica/glm';
	import { mudarFiltros } from '$lib/estado/filtros';
	import { escreverFiltros, recorteDe, rota, type Filtros } from '$lib/estado/url';
	import { formatarDecimal, formatarInteiro, formatarPp } from '$lib/formato';
	import Sparkline from '$lib/graficos/Sparkline.svelte';
	import { metodoDe } from './tendencias';

	let {
		topico,
		macro,
		topicos,
		cubo,
		filtros,
		aoFechar
	}: {
		topico: Topico;
		macro: Macrotema | null;
		topicos: Topicos;
		cubo: Cubo;
		filtros: Filtros;
		aoFechar: () => void;
	} = $props();

	let titulo = $state<HTMLHeadingElement>();
	$effect(() => {
		void topico.id;
		tick().then(() => titulo?.focus());
	});

	const t = $derived(cubo.t);
	const falhas = $derived(cubo.falhas(filtros));
	const nAnos = $derived(topicos.anos.length);

	// série no recorte (período inteiro, sem o filtro de tópicos) e tendência no intervalo do recorte
	const porAno = $derived(cubo.topicoPorAno(falhas, D.ANO | D.TOPICO));
	const linha = $derived(porAno.ids.indexOf(topico.id));
	const serie = $derived(linha >= 0 ? porAno.n.subarray(linha * nAnos, (linha + 1) * nAnos) : new Float64Array(nAnos));
	const porAnoJanela = $derived(cubo.topicoPorAno(falhas, D.TOPICO));
	const serieJanela = $derived(
		linha >= 0 ? porAnoJanela.n.subarray(linha * nAnos, (linha + 1) * nAnos) : new Float64Array(nAnos)
	);
	const tend = $derived(tendencia(serieJanela, porAnoJanela.total, topicos.anos, metodoDe(topicos)));
	const observado = $derived(Array.from(serie, (v, j) => (porAno.total[j] > 0 ? v / porAno.total[j] : null)));
	const ajuste = $derived(ajustados(tend, topicos.anos));
	const noRecorte = $derived(serieJanela.reduce((a, b) => a + b, 0));

	const porRevista = $derived.by(() => {
		const contagem = cubo.contarPor(falhas, D.TOPICO | D.REVISTA, t.revistas.length, (i) =>
			t.topico[i] === topico.id ? t.revista[i] : -1
		);
		const itens = t.revistas.map((r, i) => ({ r, n: contagem[i] })).filter((x) => x.n > 0);
		return itens.sort((a, b) => b.n - a.n);
	});
	const maiorRevista = $derived(Math.max(1, ...porRevista.map((x) => x.n)));
	const maiorPeso = $derived(Math.max(1e-9, ...topico.palavras_chave.map(([, p]) => p)));

	const recorte = $derived(recorteDe(filtros));
	const noMapa = $derived(rota('/mapa', escreverFiltros({ ...recorte, topicos: [topico.id] })));
	const filtrado = $derived(filtros.topicos.includes(topico.id));
	const FONTE: Record<string, string> = {
		llm: 'rótulo escrito pelo modelo de linguagem',
		palavras: 'rótulo pelas palavras-chave',
		manual: 'rótulo escrito à mão (rotulos.yaml)'
	};
	const DIRECAO: Record<string, string> = { alta: 'Em alta', queda: 'Em queda', estavel: 'Estável', insuficiente: 'Sem dados suficientes' };
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && aoFechar()} />

<aside class="gaveta" aria-labelledby="titulo-gaveta" data-testid="gaveta-topico">
	<header>
		{#if macro}
			<p class="macro"><span class="cor" style:background={macro.cor}></span>{macro.rotulo}</p>
		{/if}
		<h2 id="titulo-gaveta" tabindex="-1" bind:this={titulo}>{topico.rotulo}</h2>
		<button type="button" class="fechar" aria-label="Fechar" onclick={aoFechar}>×</button>
	</header>
	{#if topico.descricao}<p class="descricao">{topico.descricao}</p>{/if}
	<p class="fonte">{FONTE[topico.rotulo_fonte ?? 'llm']}</p>

	<section>
		<h3>No tempo</h3>
		<p class="numero-grande">
			{formatarInteiro(noRecorte)} <span>documentos no recorte (de {formatarInteiro(topico.n)} no corpus)</span>
		</p>
		<Sparkline observado={observado} ajustado={ajuste} largura={320} altura={72} cor={topico.cor} rotulo="Participação por ano de {topico.rotulo}" />
		<p class="tendencia" data-testid="tendencia-gaveta">
			<strong>{DIRECAO[tend.direcao]}</strong>
			{#if tend.pp_periodo !== null}
				· {formatarPp(tend.pp_periodo)} de {tend.anos![0]} a {tend.anos![1]}
				({formatarDecimal(100 * tend.prop_inicio!)}% → {formatarDecimal(100 * tend.prop_fim!)}% dos documentos do ano)
			{/if}
		</p>
	</section>

	<section>
		<h3>Palavras-chave</h3>
		<ul class="palavras">
			{#each topico.palavras_chave.slice(0, 10) as [termo, peso] (termo)}
				<li><span class="barra" style:width="{(100 * peso) / maiorPeso}%"></span><span>{termo}</span></li>
			{/each}
		</ul>
	</section>

	{#if porRevista.length}
		<section>
			<h3>Por revista, no recorte</h3>
			<ul class="revistas">
				{#each porRevista as { r, n } (r)}
					<li>
						<span class="nome">{r}</span>
						<span class="barra" style:width="{(100 * n) / maiorRevista}%" style:background={topico.cor}></span>
						<span class="numero">{formatarInteiro(n)}</span>
					</li>
				{/each}
			</ul>
		</section>
	{/if}

	<section>
		<h3>Documentos representativos</h3>
		<ol class="representativos">
			{#each topico.representativos as id (id)}
				{@const i = t.indice.get(id)}
				{#if i !== undefined}
					<li><a href={rota('/mapa', escreverFiltros({ ...recorte, topicos: [topico.id], doc: id }))}>{t.titulos[i]}</a></li>
				{/if}
			{/each}
		</ol>
	</section>

	<div class="acoes">
		<a class="botao" href={noMapa} data-testid="ver-no-mapa">Ver no mapa</a>
		<button
			type="button"
			class="botao"
			aria-pressed={filtrado}
			onclick={() =>
				mudarFiltros({
					topicos: filtrado ? filtros.topicos.filter((x) => x !== topico.id) : [...filtros.topicos, topico.id]
				})}
		>
			{filtrado ? 'Tirar do recorte' : 'Filtrar pelo tópico'}
		</button>
	</div>
</aside>

<style>
	.gaveta {
		position: fixed;
		/* abaixo da barra do topo e da barra do recorte */
		top: calc(var(--barra-altura) + 4.5rem);
		right: 0.75rem;
		bottom: 0.75rem;
		z-index: 40;
		width: min(28rem, calc(100vw - 1.5rem));
		overflow-y: auto;
		display: grid;
		align-content: start;
		gap: 1.1rem;
		padding: 1.25rem 1.25rem 1.5rem;
		background: var(--superficie);
		border: 1px solid var(--linha);
		border-radius: 0.8rem;
		box-shadow: 0 18px 50px rgb(0 0 0 / 0.3);
	}

	header {
		position: relative;
		padding-right: 2rem;
	}

	.macro {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		margin: 0 0 0.3rem;
		font-size: 0.82rem;
		color: var(--texto-suave);
	}

	.cor {
		width: 0.65rem;
		height: 0.65rem;
		border-radius: 50%;
	}

	h2 {
		margin: 0;
		font-family: var(--fonte-titulo);
		font-size: 1.45rem;
		font-weight: 500;
	}

	h2:focus {
		outline: none;
	}

	.fechar {
		position: absolute;
		top: -0.25rem;
		right: -0.25rem;
		width: 2rem;
		height: 2rem;
		border: 1px solid var(--linha);
		border-radius: 50%;
		background: none;
		color: var(--texto);
		font-size: 1.1rem;
		cursor: pointer;
	}

	.descricao {
		margin: 0;
	}

	.fonte {
		margin: -0.6rem 0 0;
		font-size: 0.78rem;
		color: var(--texto-suave);
	}

	h3 {
		margin: 0 0 0.45rem;
		font-family: var(--fonte-mono);
		font-size: 0.72rem;
		font-weight: 500;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--texto-suave);
	}

	.numero-grande {
		margin: 0 0 0.4rem;
		font-family: var(--fonte-titulo);
		font-size: 1.5rem;
	}

	.numero-grande span {
		font-family: var(--fonte-corpo, inherit);
		font-size: 0.85rem;
		color: var(--texto-suave);
	}

	.tendencia {
		margin: 0.4rem 0 0;
		font-size: 0.88rem;
	}

	ul,
	ol {
		margin: 0;
		padding: 0;
	}

	.palavras,
	.revistas {
		list-style: none;
		display: grid;
		gap: 0.3rem;
	}

	.palavras li {
		position: relative;
		padding: 0.1rem 0.4rem;
		font-size: 0.85rem;
	}

	.palavras .barra {
		position: absolute;
		inset: 0 auto 0 0;
		background: var(--acento-suave);
		border-radius: 0.25rem;
	}

	.palavras li span:last-child {
		position: relative;
	}

	.revistas li {
		display: grid;
		grid-template-columns: 5.5rem 1fr auto;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.82rem;
	}

	.revistas .barra {
		height: 0.55rem;
		border-radius: 0.2rem;
	}

	.representativos {
		display: grid;
		gap: 0.4rem;
		padding-left: 1.2rem;
		font-size: 0.88rem;
	}

	.representativos a {
		color: var(--texto);
	}

	.acoes {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}

	a.botao {
		text-decoration: none;
	}
</style>
