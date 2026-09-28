<script lang="ts">
	/**
	 * Os documentos de uma célula do cruzamento (ou de um valor), com a evidência de cada um lida no resumo. Os
	 * resumos vêm dos fragmentos de detalhes, pedidos só para os documentos visíveis; "Mostrar mais" acrescenta 10.
	 * O título leva ao documento no mapa, com o recorte.
	 */
	import { usarProjeto } from '$lib/dados/contexto';
	import type { TabelaDocumentos } from '$lib/dados/documentos';
	import { recorteDe, rota, escreverFiltros, type Filtros } from '$lib/estado/url';
	import { formatarInteiro } from '$lib/formato';
	import Trecho from './Trecho.svelte';

	let {
		titulo,
		indices,
		tabela,
		variavel,
		filtros,
		aoFechar
	}: {
		titulo: string;
		indices: number[];
		tabela: TabelaDocumentos;
		variavel: string;
		filtros: Filtros;
		aoFechar: () => void;
	} = $props();

	const { fonte } = usarProjeto();
	let mostrar = $state(10);
	const visiveis = $derived(indices.slice(0, mostrar));
	const noMapa = (i: number) => rota('/mapa', escreverFiltros({ ...recorteDe(filtros), doc: tabela.ids[i] }));
</script>

<section class="lista" aria-labelledby="titulo-lista" data-testid="lista-documentos">
	<header>
		<h2 id="titulo-lista">{titulo}</h2>
		<button type="button" class="fechar" aria-label="Fechar a lista" onclick={aoFechar}>×</button>
	</header>
	<p class="suave">{formatarInteiro(indices.length)} {indices.length === 1 ? 'documento' : 'documentos'} no recorte.</p>
	<ol>
		{#each visiveis as i (i)}
			<li data-testid="item-documento">
				<a href={noMapa(i)}>{tabela.titulos[i]}</a>
				<p class="meta">{tabela.revistas[tabela.revista[i]]} · {tabela.ano[i]} · {tabela.autores[i]}</p>
				{#await fonte.detalhe(tabela.ids[i])}
					<p class="suave">Carregando a evidência…</p>
				{:then d}
					{#if d?.evidencias?.[variavel]}
						<Trecho evidencia={d.evidencias[variavel]} resumo={d.resumo} titulo={tabela.titulos[i]} />
					{:else}
						<p class="suave">Sem evidência registrada.</p>
					{/if}
				{/await}
			</li>
		{/each}
	</ol>
	{#if indices.length > mostrar}
		<button type="button" class="mais" onclick={() => (mostrar += 10)}>Mostrar mais</button>
	{/if}
</section>

<style>
	.lista {
		display: grid;
		gap: 0.5rem;
		padding: 1rem 1.2rem;
		border: 1px solid var(--linha);
		border-radius: var(--raio);
		background: var(--superficie);
	}

	header {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 1rem;
	}

	h2 {
		margin: 0;
		font-size: 1.1rem;
		font-weight: 500;
	}

	.fechar {
		border: 0;
		background: none;
		color: var(--texto-suave);
		font-size: 1.3rem;
		cursor: pointer;
	}

	ol {
		display: grid;
		gap: 1rem;
		margin: 0;
		padding-left: 1.2rem;
	}

	a {
		color: var(--texto);
		font-weight: 500;
	}

	.meta,
	.suave {
		margin: 0.1rem 0 0.35rem;
		font-size: 0.8rem;
		color: var(--texto-suave);
	}

	.mais {
		justify-self: start;
		padding: 0.3rem 0.7rem;
		border: 1px solid var(--linha-forte);
		border-radius: var(--raio-pequeno);
		background: none;
		color: var(--texto);
		font: inherit;
		cursor: pointer;
	}
</style>
