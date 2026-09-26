<script lang="ts">
	/**
	 * O cartão de um documento: o que ele é, de onde veio, em que tópico está (e por quê) e os 5 vizinhos.
	 * O resumo vem do fragmento de detalhes, carregado na hora; sem licença que permita publicar, fica o aviso.
	 */
	import type { Topicos } from '$lib/contrato/tipos';
	import { usarProjeto } from '$lib/dados/contexto';
	import { vizinhosDe, type TabelaDocumentos } from '$lib/dados/documentos';

	let {
		tabela,
		topicos,
		indice,
		aoFechar,
		aoAbrir
	}: {
		tabela: TabelaDocumentos;
		topicos: Topicos;
		indice: number;
		aoFechar: () => void;
		aoAbrir: (i: number) => void;
	} = $props();

	const { fonte, revistas } = usarProjeto();
	const IDIOMAS: Record<string, string> = { pt: 'português', en: 'inglês', es: 'espanhol', fr: 'francês' };

	const id = $derived(tabela.ids[indice]);
	const detalhe = $derived(fonte.detalhe(id));
	const topico = $derived(topicos.topicos.find((t) => t.id === tabela.topico[indice]) ?? null);
	const reatribuido = $derived(tabela.atribuicao[indice] === 1);
	const acronimo = $derived(tabela.revistas[tabela.revista[indice]]);
	const revista = $derived(revistas?.revistas.find((r) => r.id === acronimo)?.titulo ?? acronimo);
	const doi = $derived(tabela.dois[indice]);
	const vizinhos = $derived(vizinhosDe(tabela, indice));
</script>

<article class="cartao" aria-labelledby="titulo-cartao" data-testid="cartao-documento">
	<header>
		<p class="rotulo-miudo">{revista} · {tabela.ano[indice]}</p>
		<button class="fechar" type="button" aria-label="Fechar o cartão" onclick={aoFechar}>×</button>
	</header>
	<h2 id="titulo-cartao">{tabela.titulos[indice]}</h2>

	{#await detalhe}
		<p class="suave" role="status">Carregando o resumo…</p>
	{:then d}
		{#if d}
			{#if d.autores.length}<p class="autores">{d.autores.join('; ')}</p>{/if}
		{/if}
		<p class="topico">
			{#if topico}
				<span class="cor" style:background={topico.cor}></span>
				<span>{topico.rotulo}</span>
				{#if reatribuido}<span class="marca" title="O agrupamento deixou este documento de fora; a maioria dos vizinhos está neste tópico.">pela vizinhança</span>{/if}
			{:else}
				<span class="suave">Sem tópico: o documento não pertence claramente a nenhum.</span>
			{/if}
		</p>
		{#if d?.fonte_analise === 'reserva'}
			<p class="nota" data-testid="nota-analise">Sem resumo em inglês: o tópico veio do resumo em {IDIOMAS[d.idioma_analise ?? ''] ?? d.idioma_analise}.</p>
		{:else if d?.fonte_analise === 'so_titulo'}
			<p class="nota" data-testid="nota-analise">Sem resumo: o tópico veio só do título.</p>
		{/if}
		{#if d?.resumo}
			<p class="resumo" lang={d.idioma ?? undefined}>{d.resumo}</p>
		{:else if d && d.fonte_analise !== 'so_titulo'}
			<p class="nota">A licença deste resumo ({d.licenca}) não permite mostrá-lo aqui. Ele está na página do artigo.</p>
		{/if}
		{#if d?.palavras_chave?.length}
			<p class="chaves">{d.palavras_chave.join(' · ')}</p>
		{/if}
		{#if d?.url || doi}
			<p><a href={d?.url ?? `https://doi.org/${doi}`} target="_blank" rel="noopener">{doi ? `doi:${doi}` : 'Página do artigo'} ↗</a></p>
		{/if}
		{#if d}<p class="suave licenca">Licença: {d.licenca}</p>{/if}
	{:catch}
		<p class="nota" role="alert">Não foi possível carregar os detalhes deste documento.</p>
	{/await}

	{#if vizinhos.length}
		<h3 class="rotulo-miudo">Mais parecidos</h3>
		<ol class="vizinhos" data-testid="vizinhos">
			{#each vizinhos as j (j)}
				<li><button type="button" onclick={() => aoAbrir(j)}>{tabela.titulos[j]}</button></li>
			{/each}
		</ol>
	{/if}
</article>

<style>
	.cartao {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		padding: 1rem 1.1rem 1.25rem;
		overflow-y: auto;
		background: color-mix(in oklab, var(--superficie) 94%, transparent);
		border: 1px solid var(--linha);
		border-radius: 0.75rem;
		backdrop-filter: blur(6px);
	}

	header {
		display: flex;
		align-items: start;
		justify-content: space-between;
		gap: 1rem;
	}

	header p {
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
		font-size: 1.2rem;
		font-weight: 500;
		line-height: 1.3;
	}

	p {
		margin: 0;
	}

	.autores,
	.chaves,
	.suave {
		font-size: 0.85rem;
		color: var(--texto-suave);
	}

	.licenca {
		font-size: 0.75rem;
	}

	.topico {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.9rem;
	}

	.cor {
		width: 0.7rem;
		height: 0.7rem;
		border-radius: 50%;
	}

	.marca {
		padding: 0 0.4rem;
		font-size: 0.75rem;
		color: var(--texto-suave);
		border: 1px solid var(--linha-forte);
		border-radius: 999px;
	}

	.nota {
		padding: 0.4rem 0.6rem;
		font-size: 0.8rem;
		color: var(--texto-suave);
		background: var(--superficie-alta);
		border-radius: 0.4rem;
	}

	.resumo {
		font-size: 0.9rem;
		line-height: 1.55;
	}

	a {
		color: var(--acento);
		font-size: 0.85rem;
	}

	h3 {
		margin: 0.4rem 0 0;
	}

	.vizinhos {
		margin: 0;
		padding-left: 1.1rem;
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
	}

	.vizinhos button {
		padding: 0;
		font: inherit;
		font-size: 0.85rem;
		text-align: left;
		color: var(--texto);
		background: none;
		border: 0;
		cursor: pointer;
	}

	.vizinhos button:hover {
		color: var(--acento);
		text-decoration: underline;
	}
</style>
