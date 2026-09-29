<script lang="ts">
	/**
	 * A vista Classificação: como o modelo codificou os resumos do recorte, uma variável do codebook por vez.
	 *
	 * - as variáveis, cada uma com o selo de kappa da validação (hachura quando a concordância é fraca);
	 * - barras 100% por ano, no período inteiro (o intervalo do recorte fica destacado);
	 * - a variável cruzada com macrotemas, tópicos ou revistas, no recorte;
	 * - os documentos de uma célula, com a evidência marcada no resumo.
	 *
	 * A variável e o cruzamento vão na URL; a célula escolhida, não (ela depende do recorte).
	 */
	import type { Classificacoes, CodebookContrato, Validacao } from '$lib/contrato/tipos';
	import { usarProjeto } from '$lib/dados/contexto';
	import type { Aberto } from '$lib/dados/corpus';
	import { filtrosDaPagina, mudarFiltros } from '$lib/estado/filtros';
	import { CRUZAR, type Cruzar } from '$lib/estado/url';
	import { formatarInteiro, formatarPorcentagem } from '$lib/formato';
	import { numeroCru } from '$lib/exportar/figura';
	import Figura from '$lib/graficos/Figura.svelte';
	import { coresDosValores, cruzamento, documentosDaCelula, porAno, referenciaDe, variaveisDaVista } from './agregar';
	import BarrasPorAno from './BarrasPorAno.svelte';
	import Cruzamento from './Cruzamento.svelte';
	import ListaDocumentos from './ListaDocumentos.svelte';
	import SeloKappa from './SeloKappa.svelte';
	import { nomesLegiveis } from '$lib/validacao/nomes';

	let {
		aberto,
		codebook,
		classificacoes,
		validacao
	}: {
		aberto: Aberto;
		codebook: CodebookContrato;
		classificacoes: Classificacoes;
		validacao: Validacao | null;
	} = $props();

	const em = '/classificacao';
	const cubo = $derived(aberto.cubo);
	const filtros = $derived(filtrosDaPagina());
	const falhas = $derived(cubo.falhas(filtros));
	const variaveis = $derived(variaveisDaVista(codebook, cubo.t));
	const v = $derived(variaveis.find((x) => x.id === filtros.variavel) ?? variaveis[0]);
	const cores = $derived(coresDosValores(v));

	const anos = $derived(aberto.topicos.anos);
	const dadosAno = $derived(porAno(cubo, falhas, v, anos));
	const cruz = $derived(cruzamento(cubo, falhas, v, filtros.cruzar));
	const total = $derived(cubo.contar(falhas));
	const classificadosRecorte = $derived(cruz.classificados.reduce((s, x) => s + x, 0));

	let escolhida = $state<{ linha: number; valor: number } | null>(null);
	let valorEscolhido = $state<number | null>(null);
	$effect(() => {
		// outra variável, outro cruzamento ou outro recorte: a escolha antiga não vale mais
		void [v.id, filtros.cruzar, falhas];
		escolhida = null;
		valorEscolhido = null;
	});
	const docsEscolhidos = $derived(
		escolhida
			? documentosDaCelula(cubo, falhas, v, cruz, escolhida.linha, escolhida.valor)
			: valorEscolhido !== null
				? documentosDaCelula(cubo, falhas, v, cruz, -1, valorEscolhido)
				: []
	);
	const tituloLista = $derived(
		escolhida
			? `${cruz.linhas[escolhida.linha].rotulo} · ${v.rotulos[escolhida.valor]}`
			: valorEscolhido !== null
				? v.rotulos[valorEscolhido]
				: ''
	);

	const NOMES_CRUZAR: Record<Cruzar, string> = { macrotema: 'Macrotemas', topico: 'Tópicos', revista: 'Revistas' };

	// ---- frases e tabelas
	const contagemValores = $derived(
		v.valores.map((_, x) => cruz.linhas.reduce((s, _l, l) => s + cruz.n[l * v.valores.length + x], 0))
	);
	const resumoAno = $derived.by(() => {
		if (!classificadosRecorte) return 'Nenhum documento classificado no recorte.';
		const ordem = contagemValores.map((n, x) => ({ n, x })).sort((a, b) => b.n - a.n);
		const [a, b] = ordem;
		return (
			`No recorte, ${v.rotulos[a.x]} é o valor mais comum (${formatarPorcentagem(a.n / classificadosRecorte)} dos ` +
			`classificados)` +
			(b && b.n ? `, seguido de ${v.rotulos[b.x]} (${formatarPorcentagem(b.n / classificadosRecorte)}).` : '.')
		);
	});
	const linhasAno = $derived(
		anos.map((ano, j) => [
			String(ano),
			formatarInteiro(dadosAno.classificados[j]),
			...v.valores.map((_, x) =>
				dadosAno.classificados[j] ? formatarPorcentagem(dadosAno.n[j * v.valores.length + x] / dadosAno.classificados[j]) : '—'
			)
		])
	);
	// no CSV, as proporções vão como fração (0 a 1); ano sem classificado fica vazio
	const dadosAnoCsv = $derived({
		colunas: ['Ano', 'Classificados', ...v.rotulos],
		linhas: anos.map((ano, j) => [
			ano,
			dadosAno.classificados[j],
			...v.valores.map((_, x) =>
				dadosAno.classificados[j] ? numeroCru(dadosAno.n[j * v.valores.length + x] / dadosAno.classificados[j], 6) : null
			)
		])
	});
	const resumoCruz = $derived.by(() => {
		const k = v.valores.length;
		let melhor = { l: -1, x: -1, p: 0 };
		cruz.linhas.forEach((_, l) => {
			if (cruz.classificados[l] < 10) return;
			v.valores.forEach((_, x) => {
				if (v.semInformacao[x]) return;
				const p = cruz.n[l * k + x] / cruz.classificados[l];
				if (p > melhor.p) melhor = { l, x, p };
			});
		});
		return melhor.l < 0
			? `Nenhum grupo com pelo menos 10 documentos classificados no recorte.`
			: `A maior concentração (entre os grupos com pelo menos 10 documentos) é ${v.rotulos[melhor.x]} em ` +
					`${cruz.linhas[melhor.l].rotulo}: ${formatarPorcentagem(melhor.p)} dos classificados.`;
	});
	const linhasCruz = $derived(
		cruz.linhas
			.map((l, i) => ({ l, i }))
			.filter(({ i }) => cruz.classificados[i] > 0)
			.map(({ l, i }) => [
				l.rotulo,
				formatarInteiro(cruz.classificados[i]),
				...v.valores.map((_, x) => formatarInteiro(cruz.n[i * v.valores.length + x]))
			])
	);
	const dadosCruzCsv = $derived({
		colunas: [NOMES_CRUZAR[filtros.cruzar], 'Classificados', ...v.rotulos],
		linhas: cruz.linhas
			.map((l, i) => ({ l, i }))
			.filter(({ i }) => cruz.classificados[i] > 0)
			.map(({ l, i }) => [l.rotulo, cruz.classificados[i], ...v.valores.map((_, x) => cruz.n[i * v.valores.length + x])])
	});
	const modelo = $derived(classificacoes.modelo.split('@')[0]);
	// no site publicado, sem o id interno do codebook nem o digest e o hash (que ficam na Metodologia, em "Para reproduzir")
	const { manifesto } = usarProjeto();
	const nomes = $derived(validacao ? nomesLegiveis(validacao) : new Map<string, string>());
</script>

<div class="vista surgir">
	<header class="cabecalho">
		<h1>Classificação</h1>
		<p class="lide" data-testid="lide-classificacao">
			{formatarInteiro(classificadosRecorte)} de {formatarInteiro(total)} documentos do recorte classificados por
			<strong>{modelo}</strong>, segundo o codebook {manifesto.api ? `${codebook.nome} ${codebook.versao}` : 'do projeto'}. Cada resposta vem com um trecho
			do resumo que a justifica: {formatarPorcentagem(classificacoes.evidencia_literal)} deles aparecem literalmente no
			texto.
		</p>
		{#if classificacoes.parcial}
			<p class="aviso" role="status">
				A classificação ainda não terminou: {formatarInteiro(classificacoes.classificados ?? 0)} de
				{formatarInteiro(classificacoes.documentos ?? 0)} documentos com resumo. Os números mudam quando ela terminar.
			</p>
		{/if}
	</header>

	<nav class="variaveis" aria-label="Variáveis do codebook">
		{#each variaveis as x (x.id)}
			{@const ref = referenciaDe(validacao, x.id)}
			<button
				type="button"
				aria-pressed={x.id === v.id}
				data-testid="variavel"
				onclick={() => mudarFiltros({ variavel: x.id === variaveis[0].id ? null : x.id }, { em })}
			>
				{x.rotulo}
				{#if ref}<SeloKappa referencia={ref} nome={nomes.get(ref.participante.nome) ?? null} />{/if}
			</button>
		{/each}
	</nav>

	<details class="definicoes">
		<summary>{v.pergunta}</summary>
		<dl>
			{#each v.valores as _, x (x)}
				{#if v.definicoes[x]}
					<dt><span class="amostra" style:background={cores[x]}></span>{v.rotulos[x]}</dt>
					<dd>{v.definicoes[x]}</dd>
				{/if}
			{/each}
		</dl>
	</details>

	<div class="duas-colunas">
		<Figura
			n={classificadosRecorte}
			id="por-ano"
			titulo="Por ano"
			resumo={resumoAno}
			colunas={['Ano', 'Classificados', ...v.rotulos]}
			linhas={linhasAno}
			dados={dadosAnoCsv}
		>
			<BarrasPorAno
				dados={dadosAno}
				variavel={v}
				{cores}
				intervalo={filtros.anos}
				escolhido={valorEscolhido}
				aoEscolher={(x) => ((escolhida = null), (valorEscolhido = valorEscolhido === x ? null : x))}
			/>
		</Figura>

		<Figura
			n={classificadosRecorte}
			id="cruzamento"
			titulo="Por {NOMES_CRUZAR[filtros.cruzar].toLowerCase()}"
			resumo={resumoCruz}
			colunas={[NOMES_CRUZAR[filtros.cruzar], 'Classificados', ...v.rotulos]}
			linhas={linhasCruz}
			dados={dadosCruzCsv}
		>
			{#snippet controles()}
				<div class="segmentado" role="group" aria-label="Cruzar com">
					{#each CRUZAR as c (c)}
						<button
							type="button"
							aria-pressed={filtros.cruzar === c}
							onclick={() => mudarFiltros({ cruzar: c }, { em })}
						>
							{NOMES_CRUZAR[c]}
						</button>
					{/each}
				</div>
			{/snippet}
			<Cruzamento
				dados={cruz}
				variavel={v}
				{cores}
				{escolhida}
				aoEscolher={(linha, valor) => {
					valorEscolhido = null;
					escolhida = escolhida?.linha === linha && escolhida.valor === valor ? null : { linha, valor };
				}}
			/>
		</Figura>
	</div>

	{#if docsEscolhidos.length}
		{#key tituloLista}
			<ListaDocumentos
				titulo={tituloLista}
				indices={docsEscolhidos}
				tabela={cubo.t}
				variavel={v.id}
				{filtros}
				aoFechar={() => ((escolhida = null), (valorEscolhido = null))}
			/>
		{/key}
	{:else}
		<p class="dica">Escolha uma célula da tabela, ou um valor na legenda, para ler os documentos e as evidências.</p>
	{/if}

	<p class="creditos">
		{#if manifesto.api}
			Modelo {classificacoes.modelo} · codebook {codebook.nome} {codebook.versao} (<code>{classificacoes.hash_codebook}</code>).
		{:else}
			Modelo {modelo}.
		{/if}
		{#if validacao}
			Selos de kappa: concordância do modelo com a codificação da amostra de validação ({formatarInteiro(validacao.amostra.n)}
			documentos); com hachura, abaixo de 0,6.
		{/if}
	</p>
</div>

<style>
	.vista {
		display: grid;
		gap: 1.5rem;
	}

	.cabecalho {
		display: grid;
		gap: 0.5rem;
	}

	h1 {
		margin: 0;
		font-size: clamp(2.2rem, 4.5vw, 3.2rem);
		font-weight: 380;
	}

	.lide {
		max-width: var(--medida);
		margin: 0;
		color: var(--texto-suave);
	}

	.aviso,
	.dica {
		margin: 0;
		color: var(--texto-suave);
		font-size: 0.9rem;
	}

	.variaveis {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}

	.variaveis button,
	.segmentado button {
		display: inline-flex;
		gap: 0.45rem;
		align-items: center;
		padding: 0.3rem 0.7rem;
		border: 1px solid var(--linha);
		border-radius: 999px;
		background: none;
		color: var(--texto-suave);
		font: inherit;
		font-size: 0.88rem;
		cursor: pointer;
	}

	.variaveis button[aria-pressed='true'],
	.segmentado button[aria-pressed='true'] {
		border-color: var(--acento);
		color: var(--texto);
	}

	.segmentado {
		display: inline-flex;
		gap: 0.25rem;
	}

	.segmentado button {
		padding: 0.15rem 0.55rem;
		font-size: 0.8rem;
	}

	.definicoes summary {
		cursor: pointer;
		color: var(--texto);
	}

	.definicoes dl {
		display: grid;
		grid-template-columns: max-content 1fr;
		gap: 0.3rem 1rem;
		margin: 0.6rem 0 0;
		font-size: 0.86rem;
	}

	.definicoes dt {
		color: var(--texto);
	}

	.definicoes dd {
		margin: 0;
		color: var(--texto-suave);
	}

	.amostra {
		display: inline-block;
		width: 0.6rem;
		height: 0.6rem;
		margin-right: 0.35rem;
		border-radius: 2px;
	}

	.creditos {
		margin: 0;
		font-size: 0.78rem;
		color: var(--texto-suave);
	}

	@media (max-width: 640px) {
		.definicoes dl {
			grid-template-columns: 1fr;
		}
	}

	/* numa tela larga, a série por ano e o cruzamento lado a lado */
	.duas-colunas {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
	}

	@media (min-width: 1600px) {
		.duas-colunas {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			column-gap: 2.5rem;
			align-items: start;
		}
	}
</style>
