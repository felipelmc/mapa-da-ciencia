<script lang="ts">
	import ErroAoAbrir from '$lib/componentes/ErroAoAbrir.svelte';
	import EstadoVazio from '$lib/componentes/EstadoVazio.svelte';
	import Protegida from '$lib/componentes/Protegida.svelte';
	import { usarProjeto } from '$lib/dados/contexto';
	import { abrirCubo, reabrirCubo } from '$lib/dados/corpus';
	import VistaMapa from '$lib/mapa/VistaMapa.svelte';

	const { fonte, manifesto } = usarProjeto();

	// documentos.json e topicos.json só existem depois de `mapa topicos`; sem eles, nenhum pedido é feito
	let dados = $state(abrirCubo(fonte));
</script>

<svelte:head>
	<title>Mapa · mapa da ciência</title>
</svelte:head>

{#await dados}
	<p class="aviso" role="status">Carregando o mapa…</p>
{:then d}
	<Protegida oque="a vista Mapa">
		{#if d}
			<VistaMapa tabela={d.tabela} topicos={d.topicos} cubo={d.cubo} />
		{:else}
			<div class="vazio">
				<h1>Mapa</h1>
				{#if manifesto.publicacao}
					<!-- no site publicado, quem visita não tem o que rodar -->
					<EstadoVazio titulo="O mapa não faz parte desta publicação." sobretitulo="Fora da publicação">
						<p data-testid="fora-da-publicacao">O projeto foi publicado sem os tópicos. As outras vistas continuam no trilho.</p>
					</EstadoVazio>
				{:else}
					<EstadoVazio titulo="Este projeto ainda não tem mapa." sobretitulo="Sem tópicos">
						<p>Rode <code>mapa coletar</code> e depois <code>mapa topicos</code>. Em seguida, recarregue esta página.</p>
					</EstadoVazio>
				{/if}
			</div>
		{/if}
	</Protegida>
{:catch erro}
	<div class="aviso"><ErroAoAbrir oque="o mapa" {erro} tentar={() => (dados = reabrirCubo(fonte))} /></div>
{/await}

<style>
	.aviso {
		padding: 2rem;
		color: var(--texto-suave);
	}

	.vazio {
		padding: 2.25rem clamp(1.25rem, 4vw, 3.5rem);
		max-width: var(--conteudo-largura);
		margin-inline: auto;
	}

	h1 {
		font-family: var(--fonte-titulo);
		font-weight: 500;
	}
</style>
