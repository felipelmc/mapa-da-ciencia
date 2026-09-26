<script lang="ts">
	import type { ProjetoAberto } from '$lib/dados/contexto';
	import { rota } from '$lib/estado/url';
	import { contar, formatarPeriodo } from '$lib/formato';
	import AlternarTema from './AlternarTema.svelte';
	import Icone from './Icone.svelte';

	let { projeto }: { projeto: ProjetoAberto } = $props();

	const manifesto = $derived(projeto.manifesto);

	// Resumo do recorte: só entra o que o projeto já tem.
	const recorte = $derived.by(() => {
		const partes = [formatarPeriodo(manifesto.recorte.anos)];
		const n = manifesto.contagens.documentos;
		partes.push(n > 0 ? contar(n, 'documento') : 'sem documentos');
		const revistas = projeto.revistas?.revistas.length ?? 0;
		if (revistas > 0) partes.push(contar(revistas, 'revista'));
		return partes;
	});
</script>

<header class="barra transicao-tema">
	<div class="identidade">
		<p class="titulo">
			<span class="titulo-texto">{manifesto.projeto.titulo}</span>
			{#if projeto.ehExemplo}
				<span class="selo-exemplo" title="Dados fictícios, só para demonstração">exemplo</span>
			{/if}
		</p>
		<p class="recorte numero" data-testid="recorte">
			{#each recorte as parte, i (i)}
				{#if i > 0}<span class="ponto" aria-hidden="true">·</span>{/if}<span>{parte}</span>
			{/each}
		</p>
	</div>

	<div class="acoes">
		<AlternarTema />
		<a class="botao-barra" href={rota('/ajuda')}>
			<Icone nome="ajuda" tamanho={18} />
			<span>Ajuda</span>
		</a>
	</div>
</header>

<style>
	.barra {
		grid-area: barra;
		position: sticky;
		top: 0;
		z-index: 10;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1.5rem;
		min-height: var(--barra-altura);
		padding: 0.5rem clamp(1.25rem, 4vw, 3.5rem);
		border-bottom: 1px solid var(--linha);
		background: color-mix(in srgb, var(--fundo) 94%, transparent);
	}

	.identidade {
		min-width: 0;
		display: grid;
		gap: 0.1rem;
	}

	.titulo {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		min-width: 0;
		font-family: var(--fonte-titulo);
		font-size: 1.08rem;
		font-weight: 460;
		line-height: 1.25;
	}

	.titulo-texto {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.selo-exemplo {
		flex: none;
		padding: 0.05rem 0.45rem;
		border: 1px solid var(--acento);
		border-radius: 999px;
		color: var(--acento);
		font-family: var(--fonte-mono);
		font-size: 0.66rem;
		font-weight: 600;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}

	.recorte {
		display: flex;
		flex-wrap: wrap;
		gap: 0 0.5rem;
		font-size: 0.76rem;
		color: var(--texto-suave);
	}

	.ponto {
		color: var(--linha-forte);
	}

	.acoes {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex: none;
	}

	.botao-barra {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		height: 2.25rem;
		padding: 0 0.8rem;
		border: 1px solid var(--linha);
		border-radius: 999px;
		color: var(--texto-suave);
		font-size: 0.85rem;
		font-weight: 500;
		text-decoration: none;
	}

	.botao-barra:hover {
		color: var(--texto);
		border-color: var(--linha-forte);
	}

	@media (max-width: 820px) {
		.barra {
			padding: 0.6rem 1rem;
			gap: 0.75rem;
		}
	}

	@media (max-width: 560px) {
		.botao-barra span {
			position: absolute;
			width: 1px;
			height: 1px;
			overflow: hidden;
			clip: rect(0 0 0 0);
			white-space: nowrap;
		}

		.botao-barra {
			width: 2.25rem;
			padding: 0;
			justify-content: center;
		}
	}
</style>
