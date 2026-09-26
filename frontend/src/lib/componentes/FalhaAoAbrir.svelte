<script lang="ts">
	import { ErroDeDados } from '$lib/dados';
	import EstadoVazio from './EstadoVazio.svelte';

	/** Tela de erro quando nem o manifesto carrega: não há casca sem ele. */
	let { erro }: { erro: unknown } = $props();

	const mensagem = $derived(erro instanceof Error ? erro.message : String(erro));
	const semManifesto = $derived(erro instanceof ErroDeDados && erro.status === 404);
</script>

<svelte:head>
	<title>Dados indisponíveis · mapa da ciência</title>
</svelte:head>

<main class="falha" id="conteudo">
	<EstadoVazio titulo="Não foi possível abrir os dados" sobretitulo="mapa da ciência" nivel={2}>
		<p role="alert">{mensagem}</p>
		{#if semManifesto}
			<p>
				A interface procura <code>dados/manifesto.json</code> ao lado da página. Para ver um projeto,
				rode <code>mapa painel</code> na pasta dele. Para ver o exemplo, rode
				<code>mapa painel --exemplo</code>.
			</p>
		{/if}
		<p>
			<button type="button" class="tentar" onclick={() => location.reload()}>Tentar de novo</button>
		</p>
	</EstadoVazio>
</main>

<style>
	.falha {
		min-height: 100dvh;
		display: grid;
		place-content: center;
		padding: 1.5rem;
		max-width: 52rem;
		margin: 0 auto;
	}

	.tentar {
		padding: 0.5rem 1rem;
		border: 1px solid var(--acento);
		border-radius: 999px;
		background: var(--acento);
		color: var(--sobre-acento);
		font-weight: 600;
		cursor: pointer;
	}
</style>
