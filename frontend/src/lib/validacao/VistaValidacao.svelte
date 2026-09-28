<script lang="ts">
	/**
	 * A vista Validação › Concordância: quanto o modelo concorda com quem codificou a amostra.
	 *
	 * - os participantes, com o tipo (um codificador de referência nunca aparece como pessoa);
	 * - a tabela do par escolhido: concordância, kappa com IC 95%, PABAK e alfa por variável;
	 * - a variável escolhida: matriz de confusão, precisão e revocação por categoria e as divergências com a
	 *   evidência que o modelo citou (no painel local, de todos os codificadores; no site, só das referências);
	 * - a comparação entre modelos (McNemar) e a evidência literal de cada modelo na amostra.
	 */
	import type { CodebookContrato, MetricaVariavel, Validacao } from '$lib/contrato/tipos';
	import type { TabelaDocumentos } from '$lib/dados/documentos';
	import { escreverFiltros, rota } from '$lib/estado/url';
	import { formatarDecimal, formatarInteiro, formatarPorcentagem } from '$lib/formato';
	import { numeroCru } from '$lib/exportar/figura';
	import Figura from '$lib/graficos/Figura.svelte';
	import { KAPPA_FRACO } from '$lib/classificacao/agregar';
	import MatrizConfusao from './MatrizConfusao.svelte';

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
	const quem = (nome: string) => (tipo(nome) === 'referencia' ? `${nome} (referência)` : nome);
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
			(semente {validacao.amostra.semente}).
			{#each participantes as p, i (p.nome)}{i ? (i === participantes.length - 1 ? ' e ' : ', ') : 'Responderam: '}<strong>{p.nome}</strong> ({TIPOS[p.tipo]}, {formatarInteiro(p.n)}){/each}.
		</p>
		{#if participantes.some((p) => p.tipo === 'referencia')}
			<p class="nota-referencia" data-testid="aviso-referencia">
				Um codificador de referência não é uma pessoa: a concordância com ele mede quanto o modelo reproduz aquela
				leitura, não se ele acerta.
			</p>
		{/if}
		{#if api}<a class="codificar" href={rota('/validacao/codificar')} data-testid="link-codificar">Codificar a amostra →</a>{/if}
	</header>

	<nav class="pares" aria-label="Pares comparados">
		{#each pares as [r, c] (`${r}|${c}`)}
			<button type="button" aria-pressed={`${r}|${c}` === chavePar} onclick={() => ((escolhido = `${r}|${c}`), (variavelEscolhida = null))} data-testid="par">
				{quem(r)} × {quem(c)}
			</button>
		{/each}
	</nav>

	<Figura
		id="concordancia"
		titulo="{quem(ref)} × {quem(comp)}"
		resumo={resumoPar}
		colunas={['Variável', 'n', 'Concordância', 'Kappa', 'IC 95%', 'PABAK', 'Alfa']}
		linhas={linhasPar}
		dados={dadosPar}
	>
		<div class="rolagem-lateral">
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
								<button type="button" onclick={() => (variavelEscolhida = m.variavel)} aria-pressed={m === metrica} data-testid="linha-variavel">
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
								· <strong>{comp}</strong>: {rotuloValor(d.variavel, d.modelo)}
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

	{#if validacao.comparacoes_modelos?.length}
		<Figura
			id="modelos"
			titulo="Comparação entre modelos"
			resumo="Teste de McNemar exato: só os documentos em que um modelo acertou e o outro errou, contra a mesma referência. Com muitas variáveis, alguma diferença com p < 0,05 aparece por acaso."
			colunas={['Variável', 'Referência', 'Modelos', 'n', 'Acertos', 'p']}
			linhas={validacao.comparacoes_modelos.map((c) => [nomeVariavel(c.variavel), c.referencia, `${c.modelo_a} × ${c.modelo_b}`, formatarInteiro(c.n), `${c.acertos_a} × ${c.acertos_b}`, formatarDecimal(c.p, 3)])}
			dados={{
				colunas: ['Variável', 'Referência', 'Modelo A', 'Modelo B', 'n', 'Acertos de A', 'Acertos de B', 'p'],
				linhas: validacao.comparacoes_modelos.map((c) => [nomeVariavel(c.variavel), c.referencia, c.modelo_a, c.modelo_b, c.n, c.acertos_a, c.acertos_b, c.p])
			}}
		>
			<ul class="mcnemar">
				{#each validacao.comparacoes_modelos.filter((c) => c.p < 0.05) as c (c.variavel + c.referencia)}
					<li>{nomeVariavel(c.variavel)} (contra {quem(c.referencia)}): {c.acertos_a > c.acertos_b ? c.modelo_a : c.modelo_b} acerta mais ({c.acertos_a} × {c.acertos_b} de {c.n}; p = {formatarDecimal(c.p, 3)}).</li>
				{:else}
					<li>Nenhuma diferença entre os modelos com p &lt; 0,05.</li>
				{/each}
			</ul>
		</Figura>
	{/if}

	{#if Object.keys(validacao.evidencia_literal ?? {}).length}
		<p class="creditos">
			Evidência literal na amostra:
			{#each Object.entries(validacao.evidencia_literal ?? {}) as [modelo, x], i (modelo)}{i ? '; ' : ''}{modelo}, {formatarPorcentagem(x)}{/each}.
		</p>
	{/if}
</div>

<style>
	.vista {
		display: grid;
		gap: 1.5rem;
		max-width: 76rem;
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
		max-width: 60rem;
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
</style>
