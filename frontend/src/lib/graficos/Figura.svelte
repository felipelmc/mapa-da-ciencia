<script lang="ts">
	/**
	 * Moldura de um gráfico: título, frase-resumo (para quem não vê o gráfico, e para todo mundo), "Ver como
	 * tabela", que mostra os mesmos números numa tabela embaixo do gráfico, e "Exportar" (SVG, PNG ou CSV, este com
	 * os números crus de `dados`). `pronto` vira `data-pronto`, que os testes e as capturas esperam.
	 */
	import type { Snippet } from 'svelte';
	import Exportar from '$lib/exportar/Exportar.svelte';
	import type { DadosCsv } from '$lib/exportar/figura';

	let {
		titulo,
		resumo,
		colunas,
		linhas,
		pronto = true,
		id,
		children,
		controles,
		dados = null,
		n = null
	}: {
		titulo: string;
		resumo: string;
		colunas: string[];
		linhas: (string | number)[][];
		pronto?: boolean;
		id: string;
		children: Snippet;
		controles?: Snippet;
		/**
		 * Os números crus para o CSV (sem separador de milhar, ponto decimal, proporções como fração, intervalos em
		 * duas colunas), separados das `linhas` formatadas da tabela da tela. Toda figura com números deve passá-los.
		 */
		dados?: DadosCsv | null;
		/** Documentos no recorte, para o rodapé da figura exportada. */
		n?: number | null;
	} = $props();

	let tabela = $state(false);
	let elemento = $state<HTMLElement | null>(null);
</script>

<figure class="figura" data-testid="figura-{id}" data-pronto={pronto ? 'sim' : undefined} bind:this={elemento}>
	<header>
		<h2>{titulo}</h2>
		{#if controles}<div class="controles">{@render controles()}</div>{/if}
	</header>
	<p class="resumo" data-testid="resumo-{id}">{resumo}</p>
	<div class="grafico">
		{@render children()}
	</div>
	<div class="acoes">
		<button
			type="button"
			class="ver-tabela"
			aria-expanded={tabela}
			aria-controls="tabela-{id}"
			onclick={() => (tabela = !tabela)}
		>
			{tabela ? 'Esconder a tabela' : 'Ver como tabela'}
		</button>
		<Exportar figura={elemento} {titulo} {colunas} {linhas} {dados} {n} />
	</div>
	{#if tabela}
		<div class="rolagem" id="tabela-{id}">
			<table data-testid="tabela-{id}">
				<caption class="visualmente-oculto">{titulo}</caption>
				<thead>
					<tr>
						{#each colunas as c (c)}<th scope="col">{c}</th>{/each}
					</tr>
				</thead>
				<tbody>
					{#each linhas as linha, i (i)}
						<tr>
							{#each linha as celula, j (j)}
								{#if j === 0}<th scope="row">{celula}</th>{:else}<td class="numero">{celula}</td>{/if}
							{/each}
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</figure>

<style>
	.figura {
		margin: 0 0 2.5rem;
	}

	header {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.75rem;
	}

	h2 {
		margin: 0;
		font-family: var(--fonte-titulo);
		font-size: 1.35rem;
		font-weight: 500;
	}

	.controles {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}

	.resumo {
		margin: 0.35rem 0 0.9rem;
		max-width: var(--medida);
		color: var(--texto-suave);
	}

	.grafico {
		position: relative;
	}

	.acoes {
		display: flex;
		gap: 1.2rem;
		align-items: baseline;
		margin-top: 0.5rem;
	}

	.ver-tabela {
		padding: 0;
		border: none;
		background: none;
		color: var(--acento);
		font: inherit;
		font-size: 0.85rem;
		text-decoration: underline;
		text-underline-offset: 0.2em;
		cursor: pointer;
	}

	.rolagem {
		max-height: 24rem;
		overflow: auto;
		margin-top: 0.6rem;
		border: 1px solid var(--linha);
		border-radius: 0.5rem;
	}

	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.85rem;
	}

	th,
	td {
		padding: 0.3rem 0.6rem;
		border-bottom: 1px solid var(--linha);
		text-align: right;
		white-space: nowrap;
	}

	th[scope='row'],
	thead th:first-child {
		position: sticky;
		left: 0;
		text-align: left;
		background: var(--superficie);
		white-space: normal;
		min-width: 12rem;
	}

	thead th {
		position: sticky;
		top: 0;
		background: var(--superficie);
	}
</style>
