<script lang="ts">
	/**
	 * A vista Validação › Concordância: quanto o modelo concorda com quem codificou a amostra.
	 *
	 * - os participantes, com o tipo (um codificador de referência nunca aparece como pessoa);
	 * - a tabela do par escolhido: concordância, kappa com IC 95%, PABAK e alfa por variável;
	 * - a variável escolhida: matriz de confusão, precisão e revocação por categoria e as divergências com a
	 *   evidência que o modelo citou (no painel local, de todos os codificadores; no site, só das referências);
	 * - a comparação entre modelos (McNemar) e a evidência literal de cada modelo na amostra.
	 *
	 * Os participantes aparecem pelo nome legível (`nomes.ts`), e não pelo id interno. No site publicado, que é para quem
	 * lê, a vista abre no par principal, e os outros pares e a parte técnica (McNemar, júri, auditoria) ficam em blocos
	 * recolhidos; no painel local, tudo aberto, como antes.
	 */
	import { tick } from 'svelte';
	import type { CodebookContrato, MetricaVariavel, Validacao } from '$lib/contrato/tipos';
	import type { TabelaDocumentos } from '$lib/dados/documentos';
	import { escreverFiltros, rota } from '$lib/estado/url';
	import { formatarDecimal, formatarInteiro, formatarPorcentagem } from '$lib/formato';
	import { numeroCru } from '$lib/exportar/figura';
	import Figura from '$lib/graficos/Figura.svelte';
	import { KAPPA_FRACO } from '$lib/classificacao/agregar';
	import MatrizConfusao from './MatrizConfusao.svelte';
	import { nomesLegiveis } from './nomes';

	let {
		validacao,
		codebook,
		tabela,
		api
	}: { validacao: Validacao; codebook: CodebookContrato | null; tabela: TabelaDocumentos | null; api: boolean } =
		$props();

	const TIPOS = { humano: 'pessoa', referencia: 'referência (não humano)', modelo: 'modelo' } as const;
	const ESTRATOS: Record<string, string> = { topico: 'tópico', ano: 'ano', revista: 'revista' };
	const participantes = $derived(validacao.codificadores ?? []);
	const tipo = (nome: string) => participantes.find((p) => p.nome === nome)?.tipo;
	const par = (m: MetricaVariavel): [string, string] =>
		m.referencia && m.comparado ? [m.referencia, m.comparado] : (m.comparacao.split(' × ') as [string, string]);
	const pares = $derived([...new Map(validacao.metricas.map((m) => [par(m).join('|'), par(m)])).values()]);
	const padrao = $derived.by(() => {
		const principal = validacao.modelo_principal;
		const comModelo = pares.filter(([r, c]) => c === principal && tipo(r) !== 'modelo');
		comModelo.sort((a, b) => Number(tipo(b[0]) === 'humano') - Number(tipo(a[0]) === 'humano'));
		return (comModelo[0] ?? pares[0])?.join('|') ?? '';
	});
	let escolhido = $state<string | null>(null);
	const chavePar = $derived(escolhido && pares.some((p) => p.join('|') === escolhido) ? escolhido : padrao);
	const [ref, comp] = $derived((chavePar.split('|') as [string, string]) ?? ['', '']);
	const doPar = $derived(validacao.metricas.filter((m) => par(m).join('|') === chavePar));
	let variavelEscolhida = $state<string | null>(null);
	const metrica = $derived(doPar.find((m) => m.variavel === variavelEscolhida) ?? doPar[0]);
	/** Numa tela larga, a tabela acompanha a rolagem: escolhida outra variável lá embaixo, o detalhe dela volta à vista. */
	async function escolherVariavel(v: string) {
		variavelEscolhida = v;
		await tick();
		const titulo = document.getElementById('titulo-detalhe');
		const barra = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--altura-barra')) || 0;
		if (titulo && titulo.getBoundingClientRect().top < barra) titulo.scrollIntoView({ block: 'start' });
	}

	// ---- nomes
	const variaveis = $derived(new Map((codebook?.variaveis ?? []).map((v) => [v.id, v])));
	function nomeVariavel(id: string): string {
		const [base, categoria] = id.split(':');
		const v = variaveis.get(base);
		if (!v) return id;
		if (!categoria) return v.rotulo;
		return `${v.rotulo}: ${v.categorias?.find((c) => c.valor === categoria)?.rotulo ?? categoria}`;
	}
	function rotuloValor(variavel: string, valor: string): string {
		if (valor === 'true') return 'Sim';
		if (valor === 'false') return 'Não';
		const v = variaveis.get(variavel.split(':')[0]);
		if (v?.tipo === 'multipla' && valor.startsWith('[')) {
			const lista = JSON.parse(valor) as string[];
			return lista.map((c) => v.categorias?.find((x) => x.valor === c)?.rotulo ?? c).join(' + ') || 'nenhuma';
		}
		return v?.categorias?.find((c) => c.valor === valor)?.rotulo ?? valor.replaceAll('_', ' ');
	}
	const nomes = $derived(nomesLegiveis(validacao));
	const nome = (id: string) => nomes.get(id) ?? id;
	const quem = (id: string) => (tipo(id) === 'referencia' ? `${nome(id)} (referência)` : nome(id));
	// kappa nulo: numa variável de texto livre ele não se aplica; nas outras, as respostas não variaram
	const semKappa = (id: string) =>
		variaveis.get(id.split(':')[0])?.tipo === 'texto' ? 'não se aplica (texto livre)' : 'indefinido (sem variação)';

	// ---- frases e tabelas
	const comKappa = $derived(doPar.filter((m) => m.kappa !== null));
	const resumoPar = $derived.by(() => {
		if (!doPar.length) return 'Nenhuma variável com respostas dos dois.';
		const fortes = comKappa.filter((m) => m.kappa! >= KAPPA_FRACO).length;
		const pior = [...comKappa].sort((a, b) => a.kappa! - b.kappa!)[0];
		return (
			`Kappa de pelo menos 0,6 em ${formatarInteiro(fortes)} de ${formatarInteiro(comKappa.length)} variáveis` +
			(pior ? `; a mais fraca é ${nomeVariavel(pior.variavel)} (κ = ${formatarDecimal(pior.kappa!, 2)}).` : '.')
		);
	});
	const linhasPar = $derived(
		doPar.map((m) => [
			nomeVariavel(m.variavel),
			formatarInteiro(m.n),
			m.concordancia === null ? '—' : formatarPorcentagem(m.concordancia),
			m.kappa === null ? '—' : formatarDecimal(m.kappa, 2),
			m.kappa_ic95 ? `${formatarDecimal(m.kappa_ic95[0], 2)} a ${formatarDecimal(m.kappa_ic95[1], 2)}` : '—',
			m.pabak === null ? '—' : formatarDecimal(m.pabak, 2),
			m.alfa === null ? '—' : formatarDecimal(m.alfa, 2)
		])
	);
	const cru = (v: number | null | undefined, casas = 6) => (v === null || v === undefined ? null : numeroCru(v, casas));
	const dadosPar = $derived({
		colunas: ['Variável', 'n', 'Concordância', 'Kappa', 'IC 95% do kappa (inferior)', 'IC 95% do kappa (superior)', 'PABAK', 'Alfa'],
		linhas: doPar.map((m) => [
			nomeVariavel(m.variavel),
			m.n,
			cru(m.concordancia),
			cru(m.kappa),
			cru(m.kappa_ic95?.[0]),
			cru(m.kappa_ic95?.[1]),
			cru(m.pabak),
			cru(m.alfa)
		])
	});
	const divergencias = $derived(
		metrica
			? validacao.divergencias.filter(
					(d) => d.variavel === metrica.variavel.split(':')[0] && (d.codificador || ref) === ref && comp === validacao.modelo_principal
				)
			: []
	);
	// ---- júri e comparações circulares
	const circular = (r: string, c: string) =>
		validacao.metricas.some((m) => par(m).join('|') === `${r}|${c}` && m.circular);
	const parCircular = $derived(circular(ref, comp));
	const juri = $derived(validacao.juri ?? null);
	const ETAPAS_JURI = { unanime: 'Unânime', maioria: 'Maioria', deliberacao: 'Na deliberação', sem_maioria: 'Sem maioria' } as const;
	const dadosJuri = $derived({
		colunas: ['Variável', 'Unânime', 'Maioria', 'Na deliberação', 'Sem maioria', 'Mudou na deliberação'],
		linhas: juri
			? Object.entries(juri.etapas).map(([v, e]) => [
					nomeVariavel(v),
					...(['unanime', 'maioria', 'deliberacao', 'sem_maioria'] as const).map((k) => e[k] ?? 0),
					juri.virou?.[v] ?? 0
				])
			: []
	});
	const linhasJuri = $derived(
		juri
			? Object.entries(juri.etapas).map(([v, e]) => [
					nomeVariavel(v),
					...(['unanime', 'maioria', 'deliberacao', 'sem_maioria'] as const).map((k) => formatarInteiro(e[k] ?? 0)),
					formatarInteiro(juri.virou?.[v] ?? 0)
				])
			: []
	);
	const resumoJuri = $derived.by(() => {
		if (!juri) return '';
		const total = Object.values(juri.etapas).reduce((s, e) => s + Object.values(e).reduce((a, b) => a + b, 0), 0);
		const unan = Object.values(juri.etapas).reduce((s, e) => s + (e.unanime ?? 0), 0);
		return `${formatarInteiro(juri.membros.length)} modelos locais votaram em ${formatarInteiro(juri.documentos)} documentos: ${formatarPorcentagem(total ? unan / total : 0)} das decisões foram unânimes.`;
	});
	/** O valor-p do McNemar: "< 0,001" em vez de "= 0,000". */
	const textoP = (p: number) => (p < 0.001 ? '< 0,001' : `= ${formatarDecimal(p, 3)}`);
	const titulo = (doc: string) => {
		const i = tabela?.indice.get(doc);
		return i === undefined ? doc : tabela!.titulos[i];
	};
</script>

<div class="vista surgir">
	<header class="cabecalho">
		<h1>Validação</h1>
		<p class="lide" data-testid="lide-validacao">
			Amostra de {formatarInteiro(validacao.amostra.n)} documentos, estratificada por {ESTRATOS[validacao.amostra.estratificar_por] ?? validacao.amostra.estratificar_por}
			{#if api}(semente {validacao.amostra.semente}){/if}.
			{#each participantes as p, i (p.nome)}{i ? (i === participantes.length - 1 ? ' e ' : ', ') : 'Responderam: '}<strong>{nome(p.nome)}</strong> ({TIPOS[p.tipo]}, {formatarInteiro(p.n)}){/each}.
		</p>
		{#if participantes.some((p) => p.tipo === 'referencia')}
			<p class="nota-referencia" data-testid="aviso-referencia">
				Um codificador de referência não é uma pessoa: a concordância com ele mede quanto o modelo reproduz aquela
				leitura, não se ele acerta.
			</p>
		{/if}
		{#if api}<a class="codificar" href={rota('/validacao/codificar')} data-testid="link-codificar">Codificar a amostra →</a>{/if}
	</header>

	{#snippet listaDePares()}
		<nav class="pares" aria-label="Pares comparados">
			{#each pares as [r, c] (`${r}|${c}`)}
				<button type="button" aria-pressed={`${r}|${c}` === chavePar} onclick={() => ((escolhido = `${r}|${c}`), (variavelEscolhida = null))} data-testid="par">
					{quem(r)} × {quem(c)}{#if circular(r, c)}{' '}<span class="circular" title="Os dois são da mesma família de modelo">circular</span>{/if}
				</button>
			{/each}
		</nav>
	{/snippet}
	{#if api}
		{@render listaDePares()}
	{:else if pares.length > 1}
		<details class="recolhido" data-testid="outros-pares">
			<summary>Comparar outros pares ({formatarInteiro(pares.length)})</summary>
			{@render listaDePares()}
		</details>
	{/if}

	{#if parCircular}
		<p class="nota-referencia" data-testid="aviso-circular">
			{quem(ref)} e {nome(comp)} são da mesma família de modelo: esta concordância é um limite superior, e não uma medida
			independente da qualidade.
		</p>
	{/if}

	<!-- numa tela larga, a tabela do par e o detalhe da variável lado a lado -->
	<div class="par-e-detalhe">
		<Figura
			id="concordancia"
			titulo="{quem(ref)} × {quem(comp)}"
			resumo={resumoPar}
			colunas={['Variável', 'n', 'Concordância', 'Kappa', 'IC 95%', 'PABAK', 'Alfa']}
			linhas={linhasPar}
			dados={dadosPar}
		>
			<div class="rolagem-lateral tabela-do-par">
				<table class="metricas" data-testid="tabela-metricas">
					<thead>
						<tr>
							<th scope="col">Variável</th>
							<th scope="col" class="num">n</th>
							<th scope="col" class="num">Concordância</th>
							<th scope="col" class="kappa">Kappa (IC 95%)</th>
							<th scope="col" class="num">PABAK</th>
							<th scope="col" class="num">Alfa</th>
						</tr>
					</thead>
					<tbody>
						{#each doPar as m (m.variavel)}
							<tr class:escolhida={m === metrica}>
								<th scope="row">
									<button type="button" onclick={() => escolherVariavel(m.variavel)} aria-pressed={m === metrica} data-testid="linha-variavel">
										{nomeVariavel(m.variavel)}
									</button>
								</th>
								<td class="num">{formatarInteiro(m.n)}</td>
								<td class="num">{m.concordancia === null ? '—' : formatarPorcentagem(m.concordancia)}</td>
								<td class="kappa">
									{#if m.kappa === null}
										<span class="suave">{semKappa(m.variavel)}</span>
									{:else}
										<span class="barra-kappa" class:fraco={m.kappa < KAPPA_FRACO}>
											<span style:width="{Math.max(0, m.kappa) * 100}%"></span>
										</span>
										{formatarDecimal(m.kappa, 2)}
										{#if m.kappa_ic95}<span class="suave">({formatarDecimal(m.kappa_ic95[0], 2)} a {formatarDecimal(m.kappa_ic95[1], 2)})</span>{/if}
									{/if}
								</td>
								<td class="num">{m.pabak === null ? '—' : formatarDecimal(m.pabak, 2)}</td>
								<td class="num">{m.alfa === null ? '—' : formatarDecimal(m.alfa, 2)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</Figura>

		{#if metrica}
			<section class="detalhe" aria-labelledby="titulo-detalhe" data-testid="detalhe-variavel">
				<h2 id="titulo-detalhe">{nomeVariavel(metrica.variavel)}</h2>
				<div class="lado-a-lado" class:largo={metrica.matriz.rotulos.length > 5}>
					{#if metrica.matriz.rotulos.length}
						<div>
							<h3>Matriz de confusão</h3>
							<MatrizConfusao matriz={metrica.matriz} referencia={quem(ref)} comparado={quem(comp)} rotulo={(v) => rotuloValor(metrica.variavel, v)} />
						</div>
					{/if}
					{#if metrica.por_classe?.length}
						<div>
							<h3>Por categoria</h3>
							<div class="rolagem-lateral">
								<table class="classes">
									<thead>
										<tr><th scope="col">Categoria</th><th scope="col" class="num">Na referência</th><th scope="col" class="num">Precisão</th><th scope="col" class="num">Revocação</th><th scope="col" class="num">F1</th></tr>
									</thead>
									<tbody>
										{#each metrica.por_classe.filter((c) => c.suporte || c.precisao !== null) as c (c.rotulo)}
											<tr>
												<th scope="row">{rotuloValor(metrica.variavel, c.rotulo)}</th>
												<td class="num">{formatarInteiro(c.suporte)}</td>
												<td class="num">{c.precisao === null ? '—' : formatarDecimal(c.precisao, 2)}</td>
												<td class="num">{c.revocacao === null ? '—' : formatarDecimal(c.revocacao, 2)}</td>
												<td class="num">{c.f1 === null ? '—' : formatarDecimal(c.f1, 2)}</td>
											</tr>
										{/each}
									</tbody>
								</table>
							</div>
							<p class="suave">Tomando {quem(ref)} como referência.</p>
						</div>
					{/if}
				</div>

				{#if divergencias.length}
					<h3>Divergências ({formatarInteiro(divergencias.length)})</h3>
					<ol class="divergencias" data-testid="divergencias">
						{#each divergencias as d (d.doc + d.codificador)}
							<li>
								<a href={rota('/mapa', escreverFiltros({ doc: d.doc }))}>{titulo(d.doc)}</a>
								<p>
									<strong>{quem(d.codificador || ref)}</strong>: {rotuloValor(d.variavel, d.humano)}{#if d.incerto} <span class="incerto">incerto</span>{/if}
									· <strong>{nome(comp)}</strong>: {rotuloValor(d.variavel, d.modelo)}
								</p>
								{#if d.evidencia}
									<blockquote class:ausente={d.status === 'ausente'}>
										«{d.evidencia}»{#if d.status === 'ausente'} <span class="suave">(trecho não encontrado no resumo)</span>{/if}
									</blockquote>
								{/if}
							</li>
						{/each}
					</ol>
				{/if}
			</section>
		{/if}
	</div>

	{#snippet tecnico()}
		{#if validacao.comparacoes_modelos?.length}
			<Figura
				id="modelos"
				titulo="Comparação entre modelos"
				resumo="Teste de McNemar exato: só os documentos em que um modelo acertou e o outro errou, contra a mesma referência. Com muitas variáveis, alguma diferença com p < 0,05 aparece por acaso."
				colunas={['Variável', 'Referência', 'Modelos', 'n', 'Acertos', 'p']}
				linhas={validacao.comparacoes_modelos.map((c) => [nomeVariavel(c.variavel), quem(c.referencia), `${nome(c.modelo_a)} × ${nome(c.modelo_b)}`, formatarInteiro(c.n), `${c.acertos_a} × ${c.acertos_b}`, c.p < 0.001 ? '< 0,001' : formatarDecimal(c.p, 3)])}
				dados={{
					colunas: ['Variável', 'Referência', 'Modelo A', 'Modelo B', 'n', 'Acertos de A', 'Acertos de B', 'p'],
					linhas: validacao.comparacoes_modelos.map((c) => [nomeVariavel(c.variavel), c.referencia, c.modelo_a, c.modelo_b, c.n, c.acertos_a, c.acertos_b, c.p])
				}}
			>
				<ul class="mcnemar" data-testid="lista-mcnemar">
					{#each validacao.comparacoes_modelos.filter((c) => c.p < 0.05) as c (`${c.variavel}|${c.referencia}|${c.modelo_a}|${c.modelo_b}`)}
						{@const [vence, perde, av, ap] = c.acertos_a >= c.acertos_b ? [c.modelo_a, c.modelo_b, c.acertos_a, c.acertos_b] : [c.modelo_b, c.modelo_a, c.acertos_b, c.acertos_a]}
						<li>{nomeVariavel(c.variavel)}, contra {quem(c.referencia)}: <strong>{nome(vence)}</strong> acerta mais que {nome(perde)} ({av} × {ap} acertos em {c.n}; p {textoP(c.p)}).</li>
					{:else}
						<li>Nenhuma diferença entre os modelos com p &lt; 0,05.</li>
					{/each}
				</ul>
			</Figura>
		{/if}

		{#if juri}
			<section class="juri" aria-labelledby="titulo-juri" data-testid="secao-juri">
				<h2 id="titulo-juri">Júri de modelos locais</h2>
				<p class="lide">
					Membros: {juri.membros.join(', ')}.
					{#if juri.supervisor}O que ficou sem maioria depois da deliberação foi decidido pelo supervisor ({nome(juri.supervisor)}), que escolheu entre os votos dos membros.{/if}
					{#if tipo('juri-r1') && tipo('juri')}Os participantes <strong>{nome('juri-r1')}</strong> (a votação) e <strong>{nome('juri')}</strong> (depois da deliberação) aparecem nos pares {api ? 'acima' : 'comparados'}.{/if}
				</p>
				<Figura
					id="juri-etapas"
					titulo="Como o júri decidiu"
					resumo={resumoJuri}
					colunas={['Variável', 'Unânime', 'Maioria', 'Na deliberação', 'Sem maioria', 'Mudou na deliberação']}
					linhas={linhasJuri}
					dados={dadosJuri}
				>
					<div class="rolagem-lateral">
					<table class="metricas" data-testid="tabela-juri">
						<thead>
							<tr>
								<th scope="col">Variável</th>
								{#each Object.values(ETAPAS_JURI) as rotulo (rotulo)}<th scope="col" class="num">{rotulo}</th>{/each}
								<th scope="col" class="num">Mudou na deliberação</th>
							</tr>
						</thead>
						<tbody>
							{#each Object.entries(juri.etapas) as [v, e] (v)}
								<tr>
									<th scope="row">{nomeVariavel(v)}</th>
									{#each Object.keys(ETAPAS_JURI) as k (k)}<td class="num">{formatarInteiro(e[k] ?? 0)}</td>{/each}
									<td class="num">{formatarInteiro(juri.virou?.[v] ?? 0)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
					</div>
				</Figura>
				{#if juri.referencia && Object.keys(juri.concordancia_por_etapa ?? {}).length}
					<p class="creditos">
						Concordância com {quem(juri.referencia)} por estágio:
						{#each Object.entries(juri.concordancia_por_etapa ?? {}) as [etapa, c], i (etapa)}{i ? '; ' : ''}{ETAPAS_JURI[etapa as keyof typeof ETAPAS_JURI] ?? etapa}, {formatarPorcentagem(c.n ? c.acertos / c.n : 0)} de {formatarInteiro(c.n)}{/each}
						(a decisão do júri sem o supervisor).
						{#if juri.concordancia_supervisor}
							{@const s = juri.concordancia_supervisor}
							<span data-testid="concordancia-supervisor">
								Com a escolha do supervisor, nas {formatarInteiro(s.n)} decisões sem maioria que ele arbitrou:
								{formatarPorcentagem(s.n ? s.acertos / s.n : 0)}{#if s.circular}{' '}<span class="circular" title="O supervisor e a referência são da mesma família de modelo">circular</span>{/if}.
							</span>
						{/if}
					</p>
				{/if}
				{#if juri.auditoria}
					<p class="creditos" data-testid="auditoria-juri">
						Auditoria: o supervisor conferiu {formatarInteiro(juri.auditoria.n)} decisões unânimes sorteadas e discordou de {formatarInteiro(juri.auditoria.erros)}{#if juri.auditoria.ic95}{' '}(erro estimado entre {formatarPorcentagem(juri.auditoria.ic95[0])} e {formatarPorcentagem(juri.auditoria.ic95[1])}, IC 95% de Wilson){/if}.
					</p>
				{/if}
			</section>
		{/if}

		{#if Object.keys(validacao.evidencia_literal ?? {}).length}
			<p class="creditos">
				Evidência literal na amostra:
				{#each Object.entries(validacao.evidencia_literal ?? {}) as [modelo, x], i (modelo)}{i ? '; ' : ''}{nome(modelo)}, {formatarPorcentagem(x)}{/each}.
			</p>
		{/if}
	{/snippet}
	{#if api}
		{@render tecnico()}
	{:else if validacao.comparacoes_modelos?.length || juri || Object.keys(validacao.evidencia_literal ?? {}).length}
		<details class="recolhido" data-testid="detalhes-tecnicos">
			<summary>Detalhes técnicos: comparação entre modelos, júri e evidência literal</summary>
			<div class="tecnico">{@render tecnico()}</div>
		</details>
	{/if}
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

	h2 {
		margin: 0;
		font-size: 1.3rem;
		font-weight: 450;
	}

	h3 {
		margin: 0.4rem 0 0.5rem;
		font-size: 0.95rem;
		font-weight: 500;
	}

	.lide,
	.nota-referencia {
		max-width: var(--medida);
		margin: 0;
		color: var(--texto-suave);
	}

	.nota-referencia {
		font-size: 0.88rem;
		padding-left: 0.7rem;
		border-left: 2px dashed var(--linha-forte);
	}

	.codificar {
		justify-self: start;
		color: var(--acento);
	}

	/* no site publicado, os outros pares e a parte técnica ficam recolhidos */
	.recolhido > summary {
		cursor: pointer;
		color: var(--acento);
		font-size: 0.92rem;
	}

	.recolhido[open] > summary {
		margin-bottom: 0.8rem;
	}

	.tecnico {
		display: grid;
		gap: 1.5rem;
	}

	.pares {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}

	.pares button,
	.metricas button {
		padding: 0.3rem 0.7rem;
		border: 1px solid var(--linha);
		border-radius: 999px;
		background: none;
		color: var(--texto-suave);
		font: inherit;
		font-size: 0.86rem;
		cursor: pointer;
	}

	.circular {
		margin-left: 0.2rem;
		padding: 0 0.35rem;
		border: 1px dashed var(--linha-forte);
		border-radius: 999px;
		font-size: 0.72rem;
		color: var(--texto-suave);
	}

	.juri {
		display: grid;
		grid-template-columns: minmax(0, 1fr); /* a tabela rola na própria caixa, sem alargar a página no celular */
		gap: 0.8rem;
	}

	.pares button[aria-pressed='true'] {
		border-color: var(--acento);
		color: var(--texto);
	}

	.metricas button {
		padding: 0.1rem 0;
		border: 0;
		border-radius: 0;
		color: var(--texto);
		text-align: left;
	}

	.metricas button[aria-pressed='true'] {
		font-weight: 600;
	}

	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.86rem;
	}

	/* numa tela larga, a tabela das métricas não se espalha: as colunas ficam perto dos nomes */
	table.metricas {
		max-width: 72rem;
	}

	/* numa tela estreita, a tabela rola dentro da própria caixa, e não a página inteira */
	.rolagem-lateral {
		max-width: 100%;
		overflow-x: auto;
	}

	th,
	td {
		padding: 0.3rem 0.4rem;
		border-bottom: 1px solid var(--linha);
		text-align: left;
		font-weight: 400;
	}

	thead th {
		color: var(--texto-suave);
	}

	.num {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}

	.kappa {
		min-width: 14rem;
		font-variant-numeric: tabular-nums;
	}

	tr.escolhida {
		background: var(--superficie-alta);
	}

	.barra-kappa {
		display: inline-block;
		width: 5rem;
		height: 0.5rem;
		margin-right: 0.4rem;
		border-radius: 2px;
		background: var(--linha);
		vertical-align: middle;
		overflow: hidden;
	}

	.barra-kappa span {
		display: block;
		height: 100%;
		background: var(--acento);
	}

	.barra-kappa.fraco span {
		background: repeating-linear-gradient(135deg, var(--acento) 0 3px, transparent 3px 5px);
	}

	.suave {
		color: var(--texto-suave);
		font-size: 0.82rem;
	}

	.detalhe {
		display: grid;
		gap: 0.8rem;
		padding: 1rem 1.2rem;
		border: 1px solid var(--linha);
		border-radius: var(--raio);
		background: var(--superficie);
	}

	.lado-a-lado {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
		gap: 1.5rem;
		align-items: start;
	}

	.divergencias {
		display: grid;
		gap: 0.9rem;
		margin: 0;
		padding-left: 1.2rem;
	}

	.divergencias a {
		color: var(--texto);
		font-weight: 500;
	}

	.divergencias p {
		margin: 0.2rem 0;
		font-size: 0.86rem;
		color: var(--texto-suave);
	}

	blockquote {
		margin: 0;
		padding-left: 0.7rem;
		border-left: 2px solid var(--linha-forte);
		font-size: 0.86rem;
		color: var(--texto-suave);
	}

	blockquote.ausente {
		border-left-style: dashed;
	}

	.incerto {
		padding: 0 0.35rem;
		border: 1px dashed var(--linha-forte);
		border-radius: 999px;
		font-size: 0.7rem;
	}

	.mcnemar {
		margin: 0;
		padding-left: 1.2rem;
		font-size: 0.88rem;
	}

	.creditos {
		margin: 0;
		font-size: 0.8rem;
		color: var(--texto-suave);
	}

	.lado-a-lado.largo {
		grid-template-columns: minmax(0, 1fr);
	}

	@media (max-width: 900px) {
		.lado-a-lado {
			grid-template-columns: minmax(0, 1fr);
		}
	}

	.par-e-detalhe {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: 1.5rem;
		align-items: start;
	}

	@media (min-width: 1600px) {
		.par-e-detalhe {
			grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr);
		}

		/* na coluna, a matriz e as categorias uma embaixo da outra */
		.par-e-detalhe .lado-a-lado {
			grid-template-columns: minmax(0, 1fr);
		}

		/* a tabela do par acompanha a rolagem ao lado do detalhe (que é longo, com as divergências) */
		/* o primeiro filho é o <Figura>, de outro componente: sem o :global, a regra não o alcança */
		.par-e-detalhe > :global(:first-child) {
			position: sticky;
			top: calc(var(--altura-barra, 4rem) + 1rem);
		}

		/* com muitas variáveis, a tabela grudada rola por dentro, para a última linha não ficar abaixo da tela */
		.tabela-do-par {
			max-height: max(14rem, calc(100dvh - var(--altura-barra, 4rem) - 18rem));
			overflow-y: auto;
		}
	}
</style>
