<script lang="ts">
	/**
	 * As citações: o cânone (as obras de fora do corpus que os documentos do recorte mais citam, empilhadas pelo
	 * macrotema de quem cita) e o fluxo entre macrotemas pelas citações internas (as duas pontas no recorte). Tudo sai
	 * das referências que o OpenAlex identificou, e a nota diz quanto isso cobre.
	 */
	import type { Aberto } from '$lib/dados/corpus';
	import type { TabelaCitacoes } from '$lib/dados/redes';
	import { contar, formatarInteiro, formatarPorcentagem } from '$lib/formato';
	import Figura from '$lib/graficos/Figura.svelte';
	import Canone, { type ObraDesenhada } from './Canone.svelte';
	import { canoneNoRecorte, citacoesInternas, maisCitadas, posicaoDoMacro, type Passa } from './calculo';
	import { recomecarDebug } from './debug';
	import MatrizFluxo from './MatrizFluxo.svelte';

	let { aberto, citacoes: c, falhas }: { aberto: Aberto; citacoes: TabelaCitacoes; falhas: Uint8Array } = $props();

	const t0 = performance.now();
	const debug = recomecarDebug('citacoes');
	const MAIS_CITADAS = 30;
	const t = $derived(aberto.tabela);
	const topicos = $derived(aberto.topicos);
	const noRecorte = $derived(aberto.cubo.contar(falhas));
	const passa = $derived<Passa>(noRecorte === t.n ? null : (d) => falhas[d] === 0);

	// linhas, colunas e fatias pela posição do macrotema em `topicos.macrotemas` (os ids não são contíguos)
	const nMacros = $derived(topicos.macrotemas.length);
	const macro = $derived(posicaoDoMacro(t.topico, topicos));
	const nomes = $derived([...topicos.macrotemas.map((m) => m.rotulo), 'Sem tópico']);
	const cores = $derived([...topicos.macrotemas.map((m) => m.cor), 'var(--texto-fraco)']);

	// ---- o cânone
	const lista = $derived(canoneNoRecorte(c, passa, macro, nMacros));
	const top = $derived(maisCitadas(lista, MAIS_CITADAS));
	const rotuloDa = (k: number) => {
		const o = c.canone[k];
		const autor = o.autores[0] ? `${o.autores[0]}${o.autores.length > 1 ? ' et al.' : ''}` : 'Autoria desconhecida';
		return `${autor} (${o.ano ?? 's.d.'}). ${o.titulo ?? 'Sem título'}`;
	};
	const citacaoDa = (k: number) => {
		const o = c.canone[k];
		const autor = o.autores[0] ? `${o.autores[0]}${o.autores.length > 1 ? ' et al.' : ''}` : 'autoria desconhecida';
		return `“${o.titulo ?? 'Sem título'}”, de ${autor} (${o.ano ?? 's.d.'})`;
	};
	const obras = $derived(top.map((o): ObraDesenhada => ({ id: c.canone[o.obra].id, rotulo: rotuloDa(o.obra), n: o.n, fatias: o.porMacro })));
	const usados = $derived(nomes.map((_, k) => top.some((o) => o.porMacro[k] > 0)));
	const resumoCanone = $derived(
		top.length
			? `A obra mais citada no recorte é ${citacaoDa(top[0].obra)}, por ${contar(top[0].n, 'documento')}. ` +
					`As barras dividem os citantes pelo macrotema de cada um.`
			: 'Nenhum documento do recorte cita as obras do cânone.'
	);
	const linhasCanone = $derived(
		top.map((o) => {
			const obra = c.canone[o.obra];
			return [rotuloDa(o.obra), obra.tipo ?? '—', obra.doi ?? '—', formatarInteiro(o.n), ...o.porMacro.map((v) => formatarInteiro(v))];
		})
	);

	// ---- a cobertura das referências
	const cob = $derived(c.cobertura);
	const comReferenciasNoRecorte = $derived.by(() => {
		let n = 0;
		for (let d = 0; d < t.n; d += 1) if ((!passa || passa(d)) && c.nReferencias[d] > 0) n += 1;
		return n;
	});

	// ---- o fluxo entre macrotemas
	const internas = $derived(citacoesInternas(c, passa, macro, nMacros));
	const diagonal = $derived(internas.matriz.reduce((s, linha, i) => s + linha[i], 0));
	const entreMacros = $derived(internas.matriz.reduce((s, linha) => s + linha.reduce((a, b) => a + b, 0), 0));
	const maiorFora = $derived.by(() => {
		let melhor: [number, number, number] | null = null;
		internas.matriz.forEach((linha, i) =>
			linha.forEach((v, j) => {
				if (i !== j && v > 0 && (!melhor || v > melhor[2])) melhor = [i, j, v];
			})
		);
		return melhor as [number, number, number] | null;
	});
	const resumoFluxo = $derived(
		entreMacros
			? `${formatarPorcentagem(diagonal / entreMacros)} das citações entre documentos do recorte ficam no mesmo macrotema. ` +
					(maiorFora
						? `O maior fluxo entre macrotemas vai de ${nomes[maiorFora[0]]} para ${nomes[maiorFora[1]]} (${contar(maiorFora[2], 'citação', 'citações')}).`
						: 'Nenhuma citação cruza macrotemas.')
			: 'No recorte, nenhum documento cita outro do recorte.'
	);

	// ---- depuração
	$effect(() => {
		debug.nos = c.canone.length;
		debug.arestas = c.de.length;
		debug.arestasNoRecorte = internas.n;
		if (!debug.desenhado) {
			debug.desenhado = true;
			debug.msAtePrimeiroDesenho = performance.now() - t0;
		}
	});
</script>

<p class="lide" data-testid="lide-redes">
	{contar(noRecorte, 'documento')} no recorte, com {formatarInteiro(internas.n)}
	{internas.n === 1 ? 'citação a outro documento do recorte' : 'citações a outros documentos do recorte'}.
	{formatarInteiro(comReferenciasNoRecorte)} deles ({formatarPorcentagem(comReferenciasNoRecorte / (noRecorte || 1))}) têm
	referências identificadas no OpenAlex.
</p>

<Figura
	n={noRecorte}
	id="canone"
	titulo="O cânone: as obras mais citadas"
	resumo={resumoCanone}
	colunas={['Obra', 'Tipo', 'DOI', 'Documentos que citam', ...nomes]}
	linhas={linhasCanone}
>
	<ul class="legenda" aria-label="Macrotema de quem cita">
		{#each nomes as nome, k (k)}
			{#if usados[k]}<li><span class="caixa" style:background={cores[k]}></span>{nome}</li>{/if}
		{/each}
	</ul>
	<Canone {obras} {cores} {nomes} />
	<p class="nota" data-testid="nota-cobertura">
		O cânone só enxerga as referências que o OpenAlex identificou: {formatarInteiro(cob.com_referencias ?? 0)} dos
		{formatarInteiro(cob.documentos ?? t.n)} documentos do corpus têm referências lá, somando
		{formatarInteiro(cob.referencias ?? 0)}. Obras sem DOI ou fora do OpenAlex (muitos livros, capítulos e textos
		antigos) ficam de fora, então a lista favorece o que tem DOI. Entram só as {formatarInteiro(c.canone.length)} obras
		mais citadas no corpus inteiro, e aqui aparecem as {formatarInteiro(top.length)} mais citadas no recorte (até
		{formatarInteiro(MAIS_CITADAS)}).
	</p>
</Figura>

<Figura
	n={noRecorte}
	id="fluxo-citacoes"
	titulo="Quem cita quem, entre os macrotemas"
	resumo={resumoFluxo}
	colunas={['Quem cita ↓ / quem é citado →', ...nomes.slice(0, nMacros)]}
	linhas={internas.matriz.map((linha, i) => [nomes[i], ...linha.map((v) => formatarInteiro(v))])}
>
	<MatrizFluxo rotulos={nomes.slice(0, nMacros)} cores={cores.slice(0, nMacros)} matriz={internas.matriz} />
	<p class="nota">
		Cada linha é o macrotema de quem cita; cada coluna, o de quem é citado. Só contam as citações com as duas pontas
		no recorte e com tópico: com um período, a citação de um artigo de dentro a um de antes do período sai da conta.
	</p>
</Figura>

<style>
	.lide {
		max-width: 60rem;
		margin: 0;
		color: var(--texto-suave);
	}

	.legenda {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 1rem;
		margin: 0 0 0.8rem;
		padding: 0;
		list-style: none;
		font-size: 0.78rem;
		color: var(--texto-suave);
	}

	.legenda li {
		display: flex;
		align-items: center;
		gap: 0.35rem;
	}

	.caixa {
		width: 0.75rem;
		height: 0.75rem;
		border-radius: 2px;
	}

	.nota {
		margin: 0.7rem 0 0;
		max-width: 60rem;
		font-size: 0.82rem;
		color: var(--texto-suave);
	}
</style>
