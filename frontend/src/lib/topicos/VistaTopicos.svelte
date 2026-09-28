<script lang="ts">
	/**
	 * A vista Tópicos: como os assuntos do corpus mudam no tempo. O fluxo mostra os macrotemas (ou, aberto um
	 * macrotema, os tópicos dele) ano a ano; o recorte da barra filtra os documentos. O fluxo ignora o próprio
	 * filtro de anos e de tópicos (mostra o período e as faixas inteiros, com o intervalo e os tópicos escolhidos
	 * em destaque), e respeita o resto: revistas, busca, laço e lugares.
	 */
	import type { Topicos } from '$lib/contrato/tipos';
	import { D, type Cubo } from '$lib/dados/cubo';
	import { filtrosDaPagina, mudarFiltros } from '$lib/estado/filtros';
	import { MODOS, type Modo } from '$lib/estado/url';
	import { formatarDecimal, formatarInteiro, formatarPeriodo, formatarPorcentagem, formatarPp } from '$lib/formato';
	import { numeroCru } from '$lib/exportar/figura';
	import Figura from '$lib/graficos/Figura.svelte';
	import { ordemDentroFora } from '$lib/graficos/fluxo';
	import Fluxo from './Fluxo.svelte';
	import GavetaTopico from './GavetaTopico.svelte';
	import Tendencias from './Tendencias.svelte';
	import { metodoDe, separar, tendencias } from './tendencias';

	let { topicos, cubo }: { topicos: Topicos; cubo: Cubo } = $props();

	const filtros = $derived(filtrosDaPagina());
	const em = '/topicos';
	const NOME_MODO: Record<Modo, string> = { fluxo: 'Fluxo', absoluto: 'Absoluto', proporcao: '100%' };
	const SEM_TOPICO = -1;

	const macros = $derived(new Map(topicos.macrotemas.map((m) => [m.id, m])));
	const macroAberto = $derived(filtros.macro !== null ? (macros.get(filtros.macro) ?? null) : null);
	const nAnos = $derived(topicos.anos.length);

	// contagens do recorte, ignorando os filtros de anos e de tópicos (o fluxo mostra tudo, com destaque)
	const falhas = $derived(cubo.falhas(filtros));
	const porAno = $derived(cubo.topicoPorAno(falhas, D.ANO | D.TOPICO));
	const linhaDoTopico = $derived(new Map(porAno.ids.map((id, i) => [id, i])));
	const serieDe = (linha: number) => porAno.n.subarray(linha * nAnos, (linha + 1) * nAnos);

	interface Nivel {
		ids: number[];
		matriz: Float64Array[];
		ordem: number[];
		cores: Map<number, string>;
		rotulos: Map<number, string>;
		destaque: Set<number>;
	}

	const nivel = $derived.by((): Nivel => {
		const selecionados = new Set(filtros.topicos);
		if (macroAberto) {
			const ids = macroAberto.topicos.filter((t) => linhaDoTopico.has(t));
			const doTopico = new Map(topicos.topicos.map((t) => [t.id, t]));
			// a ordem vem da série do corpus inteiro, para não mudar com o recorte
			const ordem = ordemDentroFora(ids.map((t) => doTopico.get(t)!.serie.n));
			return {
				ids,
				matriz: ids.map((t) => Float64Array.from(serieDe(linhaDoTopico.get(t)!))),
				ordem,
				cores: new Map(ids.map((t) => [t, doTopico.get(t)!.cor])),
				rotulos: new Map(ids.map((t) => [t, doTopico.get(t)!.rotulo])),
				destaque: new Set(ids.filter((t) => selecionados.has(t)))
			};
		}
		const lista = topicos.macrotemas;
		const matriz = lista.map((m) => {
			const soma = new Float64Array(nAnos);
			for (const t of m.topicos) {
				const linha = linhaDoTopico.get(t);
				if (linha === undefined) continue;
				const s = serieDe(linha);
				for (let j = 0; j < nAnos; j += 1) soma[j] += s[j];
			}
			return soma;
		});
		matriz.push(Float64Array.from(serieDe(porAno.ids.length)));
		const ids = [...lista.map((m) => m.id), SEM_TOPICO];
		const seriesCorpus = [
			...lista.map((m) => m.serie?.n ?? m.topicos.map(() => 0)),
			topicos.outliers.sem_topico_por_ano ?? []
		];
		return {
			ids,
			matriz,
			ordem: ordemDentroFora(seriesCorpus.length === ids.length ? seriesCorpus : matriz, [ids.length - 1]),
			cores: new Map([...lista.map((m) => [m.id, m.cor] as [number, string])]),
			rotulos: new Map([...lista.map((m) => [m.id, m.rotulo] as [number, string]), [SEM_TOPICO, 'Sem tópico']]),
			destaque: new Set(lista.filter((m) => m.topicos.some((t) => selecionados.has(t))).map((m) => m.id))
		};
	});

	const janela = $derived(
		filtros.anos
			? ([
					Math.max(0, filtros.anos[0] - topicos.anos[0]),
					Math.min(nAnos - 1, filtros.anos[1] - topicos.anos[0])
				] as [number, number])
			: null
	);

	function escolher(id: number) {
		if (macroAberto) mudarFiltros({ topico: id }, { em });
		else if (id !== SEM_TOPICO) mudarFiltros({ macro: id, topico: null }, { em });
	}

	// ---- frase-resumo e tabela do fluxo
	const noRecorte = $derived(cubo.contar(falhas));
	const periodo = $derived(filtros.anos ?? ([topicos.anos[0], topicos.anos[nAnos - 1]] as [number, number]));
	const resumo = $derived.by(() => {
		const totais = nivel.matriz.map((s) => s.reduce((a, b) => a + b, 0));
		const total = totais.reduce((a, b) => a + b, 0);
		const candidatos = nivel.ids.map((id, k) => ({ id, n: totais[k] })).filter((c) => c.id !== SEM_TOPICO);
		const maior = candidatos.sort((a, b) => b.n - a.n)[0];
		const onde = macroAberto ? `Em “${macroAberto.rotulo}”` : 'No recorte';
		const quem = macroAberto ? 'o tópico com mais documentos' : 'o macrotema com mais documentos';
		if (!total || !maior) return `${onde}, não há documentos.`;
		return (
			`${onde}, ${formatarInteiro(noRecorte)} documentos de ${formatarPeriodo(periodo)}. ` +
			`No período inteiro, ${quem} é ${nivel.rotulos.get(maior.id)} (${formatarPorcentagem(maior.n / total)}).`
		);
	});
	// ---- tendências no recorte: o filtro de anos vale (a regressão usa só o intervalo); o de tópicos, não
	const porAnoTendencia = $derived(cubo.topicoPorAno(falhas, D.TOPICO));
	const idsTendencia = $derived(macroAberto ? macroAberto.topicos : topicos.topicos.map((t) => t.id));
	const listaTendencias = $derived(tendencias(porAnoTendencia, idsTendencia, metodoDe(topicos)));
	const grupos = $derived(separar(listaTendencias));
	const acaso = $derived(Math.max(1, Math.round(grupos.testados * 0.05)));
	const anosNoRecorte = $derived(Array.from(porAnoTendencia.total).filter((v) => v > 0).length);
	const minimoAnos = $derived(topicos.metodo_tendencia?.anos_minimos ?? 5);
	const coresTopicos = $derived(new Map(topicos.topicos.map((t) => [t.id, t.cor])));
	const rotulosTopicos = $derived(new Map(topicos.topicos.map((t) => [t.id, t.rotulo])));
	const resumoTendencias = $derived.by(() => {
		const { alta, queda } = grupos;
		const nomes = (l: typeof alta) =>
			l.slice(0, 2).map((t) => `${rotulosTopicos.get(t.id)} (${formatarPp(t.pp_periodo!)})`).join(' e ') +
			(l.length > 2 ? ` e mais ${l.length - 2}` : '');
		const partes = [];
		if (alta.length) partes.push(`Em alta: ${nomes(alta)}.`);
		if (queda.length) partes.push(`Em queda: ${nomes(queda)}.`);
		if (!partes.length) partes.push('Nenhum tópico com tendência distinguível do acaso no recorte.');
		return partes.join(' ');
	});
	const dadosTendencia = $derived({
		colunas: [
			'Tópico',
			'Tendência',
			'Variação (p.p.)',
			'Participação no início',
			'Participação no fim',
			'Primeiro ano',
			'Último ano',
			'IC 95% da inclinação (inferior)',
			'IC 95% da inclinação (superior)'
		],
		linhas: [...grupos.alta, ...grupos.queda].map((t) => [
			rotulosTopicos.get(t.id) ?? String(t.id),
			t.direcao,
			numeroCru(t.pp_periodo!),
			numeroCru(t.prop_inicio!, 6),
			numeroCru(t.prop_fim!, 6),
			t.anos![0],
			t.anos![1],
			numeroCru(t.ic95![0], 6),
			numeroCru(t.ic95![1], 6)
		])
	});
	const linhasTendencia = $derived(
		[...grupos.alta, ...grupos.queda].map((t) => [
			rotulosTopicos.get(t.id) ?? String(t.id),
			t.direcao === 'alta' ? 'em alta' : 'em queda',
			formatarPp(t.pp_periodo!),
			`${formatarDecimal(100 * t.prop_inicio!)}% → ${formatarDecimal(100 * t.prop_fim!)}%`,
			`${formatarDecimal(t.ic95![0], 3)} a ${formatarDecimal(t.ic95![1], 3)}`
		])
	);

	// ---- gaveta do tópico
	const topicoAberto = $derived(filtros.topico !== null ? (topicos.topicos.find((t) => t.id === filtros.topico) ?? null) : null);
	const macroDoAberto = $derived(topicoAberto ? (macros.get(topicoAberto.macro_id) ?? null) : null);

	// ---- pequenos múltiplos por revista: macrotemas por ano em cada revista (sem os filtros de revista, anos e
	// tópicos, que o próprio gráfico mostra)
	const porRevista = $derived.by(() => {
		const t = cubo.t;
		const lista = topicos.macrotemas;
		const macroDe = new Map(lista.flatMap((m, k) => m.topicos.map((id) => [id, k] as const)));
		const nLinhas = lista.length + 1;
		const nRevistas = t.revistas.length;
		const primeiro = topicos.anos[0];
		const celulas = cubo.contarPor(falhas, D.REVISTA | D.ANO | D.TOPICO, nRevistas * nLinhas * nAnos, (i) => {
			const coluna = t.ano[i] - primeiro;
			if (coluna < 0 || coluna >= nAnos) return -1;
			const linha = macroDe.get(t.topico[i]) ?? lista.length;
			return (t.revista[i] * nLinhas + linha) * nAnos + coluna;
		});
		return t.revistas.map((id, r) => {
			const matriz = Array.from({ length: nLinhas }, (_, linha) =>
				celulas.subarray((r * nLinhas + linha) * nAnos, (r * nLinhas + linha + 1) * nAnos)
			).map((a) => Float64Array.from(a));
			const total = matriz.reduce((s, linha) => s + linha.reduce((a, b) => a + b, 0), 0);
			return { id, matriz, total };
		}).filter((x) => x.total > 0).sort((a, b) => b.total - a.total);
	});
	const idsMacro = $derived([...topicos.macrotemas.map((m) => m.id), SEM_TOPICO]);
	const ordemMacro = $derived(
		ordemDentroFora(
			[...topicos.macrotemas.map((m) => m.serie?.n ?? []), topicos.outliers.sem_topico_por_ano ?? []],
			[topicos.macrotemas.length]
		)
	);
	const coresMacro = $derived(new Map(topicos.macrotemas.map((m) => [m.id, m.cor] as [number, string])));
	const rotulosMacro = $derived(new Map([...topicos.macrotemas.map((m) => [m.id, m.rotulo] as [number, string]), [SEM_TOPICO, 'Sem tópico']]));
	function alternarRevista(id: string) {
		mudarFiltros({ revistas: filtros.revistas.includes(id) ? filtros.revistas.filter((r) => r !== id) : [...filtros.revistas, id] }, { em });
	}

	const colunas = $derived([macroAberto ? 'Tópico' : 'Macrotema', ...topicos.anos.map(String), 'Total']);
	const linhas = $derived(
		nivel.ids.map((id, k) => [
			nivel.rotulos.get(id) ?? String(id),
			...Array.from(nivel.matriz[k], (v) => formatarInteiro(v)),
			formatarInteiro(nivel.matriz[k].reduce((a, b) => a + b, 0))
		])
	);
	const dadosFluxo = $derived({
		colunas,
		linhas: nivel.ids.map((id, k) => [
			nivel.rotulos.get(id) ?? String(id),
			...nivel.matriz[k],
			nivel.matriz[k].reduce((a, b) => a + b, 0)
		])
	});
	const colunasRevista = $derived(['Revista', ...topicos.macrotemas.map((m) => m.rotulo), 'Sem tópico', 'Documentos']);
	const somaDe = (l: Float64Array) => l.reduce((a, b) => a + b, 0);
</script>

<div class="vista surgir">
	<header class="cabecalho">
		<h1>Tópicos</h1>
		<nav class="trilha" aria-label="Nível">
			{#if macroAberto}
				<button type="button" class="link" onclick={() => mudarFiltros({ macro: null, topico: null }, { em })}>
					Todos os macrotemas
				</button>
				<span aria-hidden="true">›</span>
				<span aria-current="page" data-testid="macro-aberto">{macroAberto.rotulo}</span>
			{:else}
				<span aria-current="page">Todos os macrotemas</span>
			{/if}
		</nav>
	</header>

	<Figura
		n={noRecorte}
		id="fluxo"
		titulo={macroAberto ? `Os tópicos de “${macroAberto.rotulo}” no tempo` : 'Os macrotemas no tempo'}
		{resumo}
		{colunas}
		{linhas}
		dados={dadosFluxo}
	>
		{#snippet controles()}
			<div class="modos" role="group" aria-label="Modo">
				{#each MODOS as m (m)}
					<button
						type="button"
						class="botao"
						aria-pressed={filtros.modo === m}
						data-testid="modo-{m}"
						onclick={() => mudarFiltros({ modo: m }, { em, substituir: true })}
					>
						{NOME_MODO[m]}
					</button>
				{/each}
			</div>
		{/snippet}
		<Fluxo
			matriz={nivel.matriz}
			ids={nivel.ids}
			ordem={nivel.ordem}
			modo={filtros.modo}
			anos={topicos.anos}
			cores={nivel.cores}
			rotulos={nivel.rotulos}
			destaque={nivel.destaque}
			{janela}
			aoEscolher={escolher}
			rotuloAcao={macroAberto ? 'ver o tópico' : 'abrir o macrotema'}
		/>
		<p class="nota">
			{#if filtros.modo === 'fluxo'}
				A espessura de cada faixa é o número de documentos no ano; a linha de base ondula para as faixas
				balançarem menos, e o eixo vertical não tem zero.
			{:else if filtros.modo === 'proporcao'}
				Cada ano soma 100%{macroAberto ? ' do macrotema' : ''}: a altura é a participação no ano.
			{:else}
				Faixas empilhadas a partir do zero, em documentos.
			{/if}
			{#if !macroAberto}Clique num macrotema para ver os tópicos dele.{:else}Clique num tópico para ver os detalhes.{/if}
		</p>
	</Figura>

	<Figura
		n={noRecorte}
		id="tendencias"
		titulo="Em alta e em queda"
		resumo={resumoTendencias}
		colunas={['Tópico', 'Tendência', 'Variação', 'Participação ajustada', 'IC 95% da inclinação']}
		linhas={linhasTendencia}
		dados={dadosTendencia}
	>
		{#if anosNoRecorte < minimoAnos}
			<p class="nota" data-testid="tendencias-poucos-anos">
				Escolha um período de pelo menos {minimoAnos} anos com documentos para ver as tendências.
			</p>
		{:else}
			<Tendencias
				alta={grupos.alta}
				queda={grupos.queda}
				cores={coresTopicos}
				rotulos={rotulosTopicos}
				destaque={new Set(filtros.topicos)}
				aoAbrir={(id) => mudarFiltros({ topico: id }, { em })}
			/>
			<p class="nota">
				Um tópico está em alta (ou em queda) quando a participação dele nos documentos de cada ano cresce (ou
				cai) de forma distinguível do acaso: o intervalo de 95% da inclinação de uma regressão logística,
				corrigido pela dispersão da série, não inclui zero. Com {formatarInteiro(grupos.testados)} tópicos testados,
				{acaso === 1 ? 'cerca de 1 pode aparecer' : `cerca de ${formatarInteiro(acaso)} podem aparecer`} aqui por acaso.
				{#if grupos.estaveis}{formatarInteiro(grupos.estaveis)} tópicos estão estáveis.{/if}
				{#if grupos.insuficientes}{formatarInteiro(grupos.insuficientes)} não têm documentos suficientes no recorte.{/if}
			</p>
		{/if}
	</Figura>

	{#if porRevista.length > 1}
		<Figura
		n={noRecorte}
			id="por-revista"
			titulo="Os macrotemas em cada revista"
			resumo="A participação de cada macrotema nos artigos de cada revista, ano a ano (cada ano soma 100%). Clique numa revista para filtrar o recorte por ela."
			colunas={colunasRevista}
			linhas={porRevista.map((r) => [r.id, ...r.matriz.map((l) => formatarInteiro(somaDe(l))), formatarInteiro(r.total)])}
			dados={{ colunas: colunasRevista, linhas: porRevista.map((r) => [r.id, ...r.matriz.map(somaDe), r.total]) }}
		>
			<div class="multiplos">
				{#each porRevista as r (r.id)}
					<div class="multiplo" class:apagado={filtros.revistas.length > 0 && !filtros.revistas.includes(r.id)}>
						<button type="button" class="titulo-multiplo" aria-pressed={filtros.revistas.includes(r.id)} onclick={() => alternarRevista(r.id)}>
							{r.id} <span class="numero">{formatarInteiro(r.total)}</span>
						</button>
						<Fluxo
							matriz={r.matriz}
							ids={idsMacro}
							ordem={ordemMacro}
							modo="proporcao"
							anos={topicos.anos}
							cores={coresMacro}
							rotulos={rotulosMacro}
							destaque={new Set()}
							janela={null}
							aoEscolher={() => alternarRevista(r.id)}
							altura={110}
							compacto
						/>
					</div>
				{/each}
			</div>
		</Figura>
	{/if}
</div>

{#if topicoAberto}
	<GavetaTopico
		topico={topicoAberto}
		macro={macroDoAberto}
		{topicos}
		{cubo}
		{filtros}
		aoFechar={() => mudarFiltros({ topico: null }, { em })}
	/>
{/if}

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

	.trilha {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.95rem;
		color: var(--texto-suave);
	}

	.trilha [aria-current] {
		color: var(--texto);
	}

	.link {
		padding: 0;
		border: none;
		background: none;
		color: var(--acento);
		font: inherit;
		text-decoration: underline;
		text-underline-offset: 0.2em;
		cursor: pointer;
	}

	.modos {
		display: flex;
		gap: 0.3rem;
	}

	.multiplos {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr));
		gap: 1rem 1.25rem;
	}

	.multiplo.apagado {
		opacity: 0.4;
	}

	.titulo-multiplo {
		display: flex;
		justify-content: space-between;
		width: 100%;
		margin-bottom: 0.2rem;
		padding: 0;
		border: none;
		background: none;
		color: var(--texto);
		font: inherit;
		font-size: 0.85rem;
		font-weight: 600;
		cursor: pointer;
	}

	.titulo-multiplo[aria-pressed='true'] {
		color: var(--acento);
	}

	.titulo-multiplo .numero {
		font-weight: 400;
		color: var(--texto-suave);
	}

	.nota {
		margin: 0.5rem 0 0;
		font-size: 0.85rem;
		color: var(--texto-suave);
		max-width: 60rem;
	}
</style>
