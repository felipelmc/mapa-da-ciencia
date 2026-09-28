<script lang="ts" module>
	export interface Parceiro {
		/** Índice do nó parceiro. */
		i: number;
		nome: string;
		peso: number;
		documentos: number;
	}
</script>

<script lang="ts">
	/**
	 * O cartão de um nó da rede (uma pessoa ou uma instituição): os números, os parceiros mais fortes no recorte (cada
	 * um abre o próprio cartão) e os documentos do nó que estão no recorte, com o link para cada um no Mapa. Numa
	 * instituição, um botão põe (ou tira) a instituição no recorte.
	 */
	import type { TabelaDocumentos } from '$lib/dados/documentos';
	import { contar, formatarDecimal } from '$lib/formato';

	let {
		titulo,
		sobretitulo,
		cor = null,
		comunidade = null,
		numeros,
		rotuloParceiros,
		parceiros,
		documentos,
		tabela,
		linkDoc,
		aoAbrir,
		aoFechar,
		filtro = null
	}: {
		titulo: string;
		sobretitulo: string;
		cor?: string | null;
		comunidade?: string | null;
		numeros: string;
		rotuloParceiros: string;
		parceiros: Parceiro[];
		/** Índices dos documentos do nó que estão no recorte. */
		documentos: number[];
		tabela: TabelaDocumentos;
		linkDoc: (d: number) => string;
		aoAbrir: (i: number) => void;
		aoFechar: () => void;
		filtro?: { ativo: boolean; alternar: () => void } | null;
	} = $props();

	const INICIAIS = 12;

	/** Fecha e devolve o foco a quem o tinha (senão, à busca da vista), para quem usa o teclado não voltar ao topo. */
	function fechar() {
		const destino = voltarPara?.isConnected ? voltarPara : document.querySelector<HTMLElement>('[data-busca-no]');
		const tinhaFoco = !!document.activeElement?.closest('[data-testid="cartao-no"]');
		aoFechar();
		if (tinhaFoco || document.activeElement === document.body) destino?.focus({ preventScroll: true });
	}
	let todos = $state(false);
	const ordenados = $derived([...documentos].sort((a, b) => tabela.ano[b] - tabela.ano[a] || a - b));
	const visiveis = $derived(todos ? ordenados : ordenados.slice(0, INICIAIS));
	let titulo_: HTMLElement;
	// quem tinha o foco quando o cartão abriu (a busca, um parceiro…): ao fechar, o foco volta para lá
	let voltarPara: HTMLElement | null = null;

	// aberto pela busca ou por um parceiro, o foco vai para o título (quem usa o teclado sabe que o cartão mudou);
	// aberto pelo link ou por um clique no grafo, o foco fica onde está
	$effect(() => {
		void titulo;
		todos = false;
		const ativo = document.activeElement;
		if (!ativo || ativo === document.body || ativo === titulo_) return;
		if (!ativo.closest('[data-testid="cartao-no"]')) voltarPara = ativo as HTMLElement;
		titulo_?.focus({ preventScroll: true });
		// na tela estreita o cartão fica embaixo do grafo: rola até ele
		const caixa = titulo_?.getBoundingClientRect();
		if (caixa && (caixa.top < 0 || caixa.bottom > window.innerHeight)) titulo_.scrollIntoView({ block: 'center' });
	});
</script>

<svelte:window
	onkeydown={(e) => {
		// Esc fecha o cartão, como no Mapa; num campo de texto, o Esc é do campo (a busca limpa com ele)
		const alvo = e.target as HTMLElement | null;
		if (e.key === 'Escape' && !e.defaultPrevented && !alvo?.closest('input, textarea, select')) fechar();
	}}
/>

<article class="cartao" aria-labelledby="titulo-no" data-testid="cartao-no">
	<header>
		<p class="rotulo-miudo">{sobretitulo}</p>
		<button class="fechar" type="button" aria-label="Fechar o cartão" onclick={fechar}>×</button>
	</header>
	<h2 id="titulo-no" tabindex="-1" bind:this={titulo_}>{titulo}</h2>
	{#if comunidade}
		<p class="comunidade">
			<span class="cor" style:background={cor ?? 'var(--texto-fraco)'}></span>
			<span>{comunidade}</span>
		</p>
	{/if}
	<p class="numeros" data-testid="numeros-no">{numeros}</p>
	{#if filtro}
		<button type="button" class="botao filtrar" aria-pressed={filtro.ativo} onclick={filtro.alternar} data-testid="filtrar-instituicao">
			{filtro.ativo ? 'Tirar esta instituição do recorte' : 'Filtrar por esta instituição'}
		</button>
	{/if}

	{#if parceiros.length}
		<h3 class="rotulo-miudo">{rotuloParceiros}</h3>
		<ul class="parceiros">
			{#each parceiros as p (p.i)}
				<li>
					<button type="button" onclick={() => aoAbrir(p.i)}>{p.nome}</button>
					<span class="numero" title="Peso da parceria no recorte: soma de 1/(n−1) em cada documento em comum com n autores">
						peso {formatarDecimal(p.peso)} · {contar(p.documentos, 'doc.', 'docs.')}
					</span>
				</li>
			{/each}
		</ul>
	{/if}

	<h3 class="rotulo-miudo">Documentos no recorte</h3>
	{#if ordenados.length}
		<ol class="documentos" data-testid="documentos-no">
			{#each visiveis as d (d)}
				<li>
					<a href={linkDoc(d)}>{tabela.titulos[d]}</a>
					<span class="suave">{tabela.revistas[tabela.revista[d]]} · {tabela.ano[d]}</span>
				</li>
			{/each}
		</ol>
		{#if ordenados.length > INICIAIS}
			<button type="button" class="mais" onclick={() => (todos = !todos)}>
				{todos ? 'Mostrar menos' : `Mostrar todos (${ordenados.length})`}
			</button>
		{/if}
	{:else}
		<p class="suave" data-testid="sem-documentos-no">Nenhum documento no recorte. Amplie o recorte para ver os outros.</p>
	{/if}
</article>

<style>
	.cartao {
		display: flex;
		flex-direction: column;
		gap: 0.55rem;
		padding: 1rem 1.1rem 1.2rem;
		max-height: 44rem;
		overflow-y: auto;
		background: var(--superficie);
		border: 1px solid var(--linha);
		border-radius: 0.75rem;
	}

	header {
		display: flex;
		align-items: start;
		justify-content: space-between;
		gap: 1rem;
	}

	p {
		margin: 0;
	}

	.fechar {
		flex: none;
		width: 1.75rem;
		height: 1.75rem;
		font-size: 1.2rem;
		line-height: 1;
		color: var(--texto-suave);
		background: none;
		border: 1px solid var(--linha);
		border-radius: 50%;
		cursor: pointer;
	}

	h2 {
		margin: 0;
		font-family: var(--fonte-titulo);
		font-size: 1.25rem;
		font-weight: 500;
		line-height: 1.25;
	}

	h3 {
		margin: 0.4rem 0 0;
	}

	.comunidade {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.85rem;
	}

	.cor {
		flex: none;
		width: 0.7rem;
		height: 0.7rem;
		border-radius: 50%;
	}

	.numeros,
	.suave {
		font-size: 0.82rem;
		color: var(--texto-suave);
	}

	.filtrar {
		justify-self: start;
		align-self: flex-start;
	}

	ul,
	ol {
		display: grid;
		gap: 0.35rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.parceiros li {
		display: flex;
		justify-content: space-between;
		gap: 0.6rem;
		font-size: 0.85rem;
	}

	.parceiros button,
	.mais {
		padding: 0;
		border: none;
		background: none;
		color: var(--acento);
		font: inherit;
		text-align: left;
		text-decoration: underline;
		text-underline-offset: 0.2em;
		cursor: pointer;
	}

	.parceiros .numero {
		flex: none;
		font-size: 0.75rem;
		color: var(--texto-suave);
	}

	.documentos li {
		display: grid;
		font-size: 0.85rem;
		line-height: 1.35;
	}

	.documentos a {
		color: var(--texto);
		text-underline-offset: 0.15em;
	}

	.documentos a:hover {
		color: var(--acento);
	}

	.mais {
		justify-self: start;
		align-self: flex-start;
		font-size: 0.82rem;
	}
</style>
