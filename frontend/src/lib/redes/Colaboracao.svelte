<script lang="ts" module>
	export type ChaveSerie = 'coautoria' | 'autores' | 'instituicoes' | 'ufs' | 'exterior';
</script>

<script lang="ts">
	/**
	 * A colaboração por ano, ao lado das redes (embaixo delas, com o cartão de um nó aberto): pequenas séries
	 * recalculadas no recorte (`colaboracaoPorAno`). Elas ignoram o próprio filtro de anos, como o fluxo dos tópicos:
	 * mostram o período inteiro, com o intervalo do recorte em destaque.
	 */
	import type { TabelaAfiliacoes } from '$lib/dados/afiliacoes';
	import type { Aberto } from '$lib/dados/corpus';
	import { D } from '$lib/dados/cubo';
	import type { TabelaRedes } from '$lib/dados/redes';
	import type { Filtros } from '$lib/estado/url';
	import { formatarDecimal, formatarInteiro, formatarPorcentagem } from '$lib/formato';
	import { numeroCru } from '$lib/exportar/figura';
	import Figura from '$lib/graficos/Figura.svelte';
	import { colaboracaoPorAno, type Colaboracao, type Passa } from './calculo';
	import SerieAnual from './SerieAnual.svelte';

	let {
		quais,
		aberto,
		redes,
		afiliacoes,
		filtros,
		falhas,
		n
	}: {
		quais: ChaveSerie[];
		aberto: Aberto;
		redes: TabelaRedes;
		afiliacoes: TabelaAfiliacoes | null;
		filtros: Filtros;
		falhas: Uint8Array;
		/** Documentos no recorte, para o rodapé da figura exportada. */
		n: number;
	} = $props();

	const SERIES: Record<ChaveSerie, { titulo: string; formato: 'porcentagem' | 'decimal'; valor: (c: Colaboracao) => number | null }> = {
		coautoria: { titulo: 'Documentos com mais de um autor', formato: 'porcentagem', valor: (c) => c.comCoautoria },
		autores: { titulo: 'Autores por documento', formato: 'decimal', valor: (c) => c.autoresMedio },
		instituicoes: { titulo: 'Com duas ou mais instituições', formato: 'porcentagem', valor: (c) => c.comInstituicoes },
		ufs: { titulo: 'Com duas ou mais UFs', formato: 'porcentagem', valor: (c) => c.entreUfs },
		exterior: { titulo: 'Com Brasil e exterior', formato: 'porcentagem', valor: (c) => c.comExterior }
	};

	const t = $derived(aberto.tabela);
	const anos = $derived(aberto.topicos.anos);
	const porAno = $derived.by(() => {
		const semAno: Passa = aberto.cubo.contar(falhas, D.ANO) === t.n ? null : (d) => (falhas[d] & ~D.ANO & 0xff) === 0;
		const mapa = new Map(colaboracaoPorAno(t.ano, redes, afiliacoes, semAno).map((c) => [c.ano, c]));
		return anos.map((a) => mapa.get(a) ?? null);
	});
	const janela = $derived(
		filtros.anos
			? ([Math.max(0, filtros.anos[0] - anos[0]), Math.min(anos.length - 1, filtros.anos[1] - anos[0])] as [number, number])
			: null
	);
	const series = $derived(
		quais.map((id) => ({ id, ...SERIES[id], valores: porAno.map((c) => (c ? SERIES[id].valor(c) : null)) }))
	);
	const texto = (v: number | null, formato: 'porcentagem' | 'decimal') =>
		v === null ? '—' : formato === 'porcentagem' ? formatarPorcentagem(v) : formatarDecimal(v, 2);
	const resumo = $derived.by(() => {
		const s = series[0];
		const validos = s.valores.map((v, j) => [v, anos[j]] as const).filter(([v]) => v !== null) as [number, number][];
		if (validos.length < 2) return 'Poucos anos com documentos para ver a evolução.';
		const [[v0, a0], [v1, a1]] = [validos[0], validos.at(-1)!];
		return `${s.titulo}: ${texto(v0, s.formato)} em ${a0} e ${texto(v1, s.formato)} em ${a1}.`;
	});
</script>

<Figura
	{n}
	id="colaboracao"
	titulo="A colaboração por ano"
	{resumo}
	colunas={['Ano', 'Documentos', ...series.map((s) => s.titulo)]}
	linhas={anos.map((a, j) => [String(a), formatarInteiro(porAno[j]?.documentos ?? 0), ...series.map((s) => texto(s.valores[j], s.formato))])}
	dados={{
		colunas: ['Ano', 'Documentos', ...series.map((s) => s.titulo)],
		linhas: anos.map((a, j) => [a, porAno[j]?.documentos ?? 0, ...series.map((s) => (s.valores[j] === null ? null : numeroCru(s.valores[j]!)))])
	}}
>
	<div class="series">
		{#each series as s (s.id)}
			<SerieAnual id={s.id} titulo={s.titulo} {anos} valores={s.valores} formato={s.formato} {janela} />
		{/each}
	</div>
</Figura>

<style>
	.series {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
		gap: 0.8rem 1.5rem;
	}
</style>
