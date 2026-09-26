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
	import { formatarInteiro, formatarPeriodo, formatarPorcentagem } from '$lib/formato';
	import Figura from '$lib/graficos/Figura.svelte';
	import { ordemDentroFora } from '$lib/graficos/fluxo';
	import Fluxo from './Fluxo.svelte';

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
	const colunas = $derived([macroAberto ? 'Tópico' : 'Macrotema', ...topicos.anos.map(String), 'Total']);
	const linhas = $derived(
		nivel.ids.map((id, k) => [
			nivel.rotulos.get(id) ?? String(id),
			...Array.from(nivel.matriz[k], (v) => formatarInteiro(v)),
			formatarInteiro(nivel.matriz[k].reduce((a, b) => a + b, 0))
		])
	);
</script>

<svelte:head>
	<title>Tópicos · mapa da ciência</title>
</svelte:head>

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
		id="fluxo"
		titulo={macroAberto ? `Os tópicos de “${macroAberto.rotulo}” no tempo` : 'Os macrotemas no tempo'}
		{resumo}
		{colunas}
		{linhas}
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

	.nota {
		margin: 0.5rem 0 0;
		font-size: 0.85rem;
		color: var(--texto-suave);
		max-width: 60rem;
	}
</style>
