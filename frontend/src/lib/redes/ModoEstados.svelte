<script lang="ts">
	/**
	 * A colaboração entre estados: os pares de UFs (e de UF com o exterior) que aparecem juntos nas afiliações de um
	 * documento do recorte, com o peso fracionário de `pares_ponderados`. As UFs continuam clicáveis quando o filtro
	 * de UF zera as parcerias delas (o mapa ignora o próprio filtro para decidir quem é botão, como na Geografia).
	 */
	import type { TabelaAfiliacoes } from '$lib/dados/afiliacoes';
	import type { Aberto } from '$lib/dados/corpus';
	import { D } from '$lib/dados/cubo';
	import type { TabelaRedes } from '$lib/dados/redes';
	import { mudarFiltros } from '$lib/estado/filtros';
	import type { Filtros } from '$lib/estado/url';
	import { contar, formatarDecimal, formatarInteiro, formatarPorcentagem } from '$lib/formato';
	import Figura from '$lib/graficos/Figura.svelte';
	import { NOME_UF } from '$lib/geografia/lugares';
	import { malhaUF, type PropsUF, type Regiao } from '$lib/geografia/malhas';
	import ArcosUF, { type Arco } from './ArcosUF.svelte';
	import { arestasLugares, EXTERIOR, nomeDoLugar, type Arestas, type Passa } from './calculo';
	import Colaboracao from './Colaboracao.svelte';
	import { recomecarDebug } from './debug';

	let {
		aberto,
		redes,
		afiliacoes: af,
		filtros,
		falhas
	}: { aberto: Aberto; redes: TabelaRedes; afiliacoes: TabelaAfiliacoes; filtros: Filtros; falhas: Uint8Array } = $props();

	const em = '/redes';
	const t0 = performance.now();
	const debug = recomecarDebug('estados');
	const t = $derived(aberto.tabela);
	const noRecorte = $derived(aberto.cubo.contar(falhas));
	const passa = $derived<Passa>(noRecorte === t.n ? null : (d) => falhas[d] === 0);
	const semUf = $derived<Passa>(aberto.cubo.contar(falhas, D.UF) === t.n ? null : (d) => (falhas[d] & ~D.UF & 0xff) === 0);

	const corpus = $derived(arestasLugares(af, null));
	const recorte = $derived(passa ? arestasLugares(af, passa) : corpus);
	const paraArcos = (ar: Arestas): Arco[] =>
		Array.from({ length: ar.n }, (_, k) => ({
			a: nomeDoLugar(af, ar.a[k]),
			b: nomeDoLugar(af, ar.b[k]),
			peso: ar.peso[k],
			documentos: ar.documentos[k]
		}));
	const arcos = $derived(paraArcos(recorte).sort((p, q) => q.peso - p.peso || q.documentos - p.documentos));
	const ativas = $derived.by(() => {
		const ar = !filtros.uf.length ? recorte : semUf ? arestasLugares(af, semUf) : corpus;
		const saida = new Set<string>();
		for (let k = 0; k < ar.n; k += 1) for (const i of [ar.a[k], ar.b[k]]) saida.add(nomeDoLugar(af, i));
		saida.delete(EXTERIOR);
		return saida;
	});
	const selecionadas = $derived(new Set(filtros.uf));
	function alternar(uf: string) {
		mudarFiltros({ uf: filtros.uf.includes(uf) ? filtros.uf.filter((x) => x !== uf) : [...filtros.uf, uf] }, { em });
	}

	let malha = $state<Regiao<PropsUF>[] | null>(null);
	let erroMalha = $state<string | null>(null);
	$effect(() => {
		malhaUF()
			.then((m) => (malha = m))
			.catch((e: Error) => (erroMalha = e.message));
	});

	// ---- frases
	const nome = (k: string) => (k === EXTERIOR ? 'Exterior' : (NOME_UF[k] ?? k));
	const curto = (k: string) => (k === EXTERIOR ? 'Exterior' : k);
	const par = (a: Arco) => `${nome(a.a)} e ${nome(a.b)}`;
	const pesoTotal = $derived(arcos.reduce((s, a) => s + a.peso, 0));
	const comExterior = $derived(arcos.filter((a) => a.a === EXTERIOR || a.b === EXTERIOR).reduce((s, a) => s + a.peso, 0));
	const resumo = $derived(
		arcos.length
			? `A parceria mais forte do recorte é entre ${par(arcos[0])} (${formatarDecimal(arcos[0].peso)} de peso em ` +
					`${contar(arcos[0].documentos, 'documento')}). ${formatarPorcentagem(comExterior / (pesoTotal || 1))} do peso ` +
					'das parcerias envolve o exterior. Clique numa UF para filtrar o recorte por ela.'
			: 'No recorte, nenhum documento tem afiliações em dois lugares diferentes.'
	);
	const MAIS_FORTES = 12;

	// ---- depuração
	$effect(() => {
		const lugares = new Set<number>();
		for (let k = 0; k < corpus.n; k += 1) lugares.add(corpus.a[k]).add(corpus.b[k]);
		debug.nos = lugares.size;
		debug.arestas = corpus.n;
		debug.arestasNoRecorte = recorte.n;
	});
	$effect(() => {
		if (!malha || debug.desenhado) return;
		debug.desenhado = true;
		debug.msAtePrimeiroDesenho = performance.now() - t0;
	});
</script>

<p class="lide" data-testid="lide-redes">
	{contar(noRecorte, 'documento')} no recorte e {formatarInteiro(recorte.n)}
	{recorte.n === 1 ? 'par de lugares' : 'pares de lugares'} que aparecem juntos nas afiliações de um documento: duas
	UFs, ou uma UF e o exterior. O peso é fracionário, como na coautoria: num documento com afiliações em n lugares,
	cada par ganha 1/(n−1).
</p>

{#if erroMalha}
	<p class="aviso" role="alert">Não foi possível carregar a malha das UFs: {erroMalha}</p>
{/if}

<Figura
	n={noRecorte}
	id="estados"
	titulo="Colaboração entre estados"
	{resumo}
	colunas={['Lugar', 'Com', 'Peso fracionário', 'Documentos']}
	linhas={arcos.map((a) => [nome(a.a), nome(a.b), formatarDecimal(a.peso, 2), formatarInteiro(a.documentos)])}
	pronto={!!malha}
>
	<div class="mapa-e-pares">
		<div>
			{#if malha}
				<ArcosUF regioes={malha} {arcos} {ativas} {selecionadas} aoEscolher={alternar} />
			{/if}
			<p class="nota">
				A espessura de cada arco é o peso da parceria no recorte, e o ponto de cada lugar soma o peso das parcerias
				dele. Documentos com afiliações num só lugar não formam arco.
			</p>
		</div>
		<div class="pares">
			<h3 class="rotulo-miudo">As parcerias mais fortes (peso no recorte · documentos)</h3>
			<ol data-testid="pares-estados">
				{#each arcos.slice(0, MAIS_FORTES) as a (`${a.a}|${a.b}`)}
					<li>
						<span>{curto(a.a)} · {curto(a.b)}</span>
						<span class="numero">{formatarDecimal(a.peso)}</span>
						<span class="numero suave">{contar(a.documentos, 'doc.', 'docs.')}</span>
					</li>
				{/each}
			</ol>
		</div>
	</div>
</Figura>

<Colaboracao quais={['ufs', 'exterior']} {aberto} {redes} afiliacoes={af} {filtros} {falhas} n={noRecorte} />

<style>
	.lide {
		max-width: 60rem;
		margin: 0;
		color: var(--texto-suave);
	}

	.aviso {
		color: var(--texto-suave);
	}

	.mapa-e-pares {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(14rem, 18rem);
		gap: 1.5rem;
		align-items: start;
	}

	.nota {
		margin: 0.6rem 0 0;
		font-size: 0.82rem;
		color: var(--texto-suave);
	}

	.pares h3 {
		margin: 0 0 0.5rem;
	}

	ol {
		display: grid;
		gap: 0.25rem;
		margin: 0;
		padding: 0;
		list-style: none;
		font-size: 0.85rem;
	}

	li {
		display: grid;
		grid-template-columns: 1fr auto auto;
		gap: 0.6rem;
		padding: 0.2rem 0;
		border-bottom: 1px solid var(--linha);
	}

	.suave {
		color: var(--texto-suave);
		font-size: 0.75rem;
	}

	@media (max-width: 980px) {
		.mapa-e-pares {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
