<script lang="ts">
	import { page } from '$app/state';
	import EstadoVazio from '$lib/componentes/EstadoVazio.svelte';
	import { rota } from '$lib/estado/url';

	const naoEncontrada = $derived(page.status === 404);
</script>

<svelte:head>
	<title>{naoEncontrada ? 'Página não encontrada' : 'Erro'} · mapa da ciência</title>
</svelte:head>

<div class="pagina surgir">
	<h1 class="visualmente-oculto">{naoEncontrada ? 'Página não encontrada' : 'Erro'}</h1>
	<EstadoVazio
		titulo={naoEncontrada ? 'Nada neste ponto do céu' : 'Algo deu errado'}
		sobretitulo={naoEncontrada ? 'Página não encontrada (404)' : `Erro ${page.status}`}
	>
		{#if naoEncontrada}
			<p>O endereço <code>{page.url.hash || '#/'}</code> não corresponde a nenhuma seção.</p>
		{:else}
			<p>{page.error?.message}</p>
		{/if}
		<p><a href={rota('/')}>Voltar para a Início</a></p>
	</EstadoVazio>
</div>

<style>
	a {
		color: var(--acento);
		font-weight: 600;
	}
</style>
