<script lang="ts">
	import EstadoVazio from '$lib/componentes/EstadoVazio.svelte';
	import { usarProjeto } from '$lib/dados/contexto';
	import { decodificar } from '$lib/dados/documentos';
	import VistaMapa from '$lib/mapa/VistaMapa.svelte';

	const { fonte, manifesto } = usarProjeto();

	// Versão do mapa: muda quando os tópicos são regenerados. Um laço de um link antigo abre com aviso.
	function versaoDoMapa(texto: string): string {
		let h = 0x811c9dc5;
		for (let i = 0; i < texto.length; i += 1) h = Math.imul(h ^ texto.charCodeAt(i), 0x01000193) >>> 0;
		return h.toString(36).slice(0, 6);
	}
	const versaoMapa = versaoDoMapa(`${manifesto.gerado_em}|${manifesto.contagens.topicos}`);

	// documentos.json e topicos.json só existem depois de `mapa topicos`; sem eles, nenhum pedido é feito
	const dados = (async () => {
		const [documentos, topicos] = await Promise.all([fonte.documentos(), fonte.topicos()]);
		return documentos && topicos ? { tabela: decodificar(documentos), topicos } : null;
	})();
</script>

<svelte:head>
	<title>Mapa · mapa da ciência</title>
</svelte:head>

{#await dados}
	<p class="aviso" role="status">Carregando o mapa…</p>
{:then d}
	{#if d}
		<VistaMapa tabela={d.tabela} topicos={d.topicos} {versaoMapa} />
	{:else}
		<div class="vazio">
			<h1>Mapa</h1>
			<EstadoVazio titulo="Este projeto ainda não tem mapa." sobretitulo="Sem tópicos">
				<p>Rode <code>mapa coletar</code> e depois <code>mapa topicos</code>. Em seguida, recarregue esta página.</p>
			</EstadoVazio>
		</div>
	{/if}
{:catch erro}
	<p class="aviso" role="alert">Não foi possível abrir o mapa: {erro.message}</p>
{/await}

<style>
	.aviso {
		padding: 2rem;
		color: var(--texto-suave);
	}

	.vazio {
		padding: 2.25rem clamp(1.25rem, 4vw, 3.5rem);
		max-width: var(--conteudo-largura);
	}

	h1 {
		font-family: var(--fonte-titulo);
		font-weight: 500;
	}
</style>
