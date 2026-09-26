<script lang="ts">
	import type { Snippet } from 'svelte';
	import { definirProjeto, type ProjetoAberto } from '$lib/dados/contexto';
	import { secoesDoTrilho } from '$lib/secoes';
	import BarraSuperior from './BarraSuperior.svelte';
	import Trilho from './Trilho.svelte';

	let { projeto, children }: { projeto: ProjetoAberto; children: Snippet } = $props();

	// O projeto não muda depois de aberto; as páginas o leem com usarProjeto().
	// svelte-ignore state_referenced_locally
	definirProjeto(projeto);

	const secoes = $derived(secoesDoTrilho(projeto.manifesto));

	let principal: HTMLElement;

	// Com o router por hash, um href="#conteudo" viraria uma navegação para a rota
	// "conteudo" (404). O link de pular só move o foco, sem tocar na URL.
	function pular(evento: MouseEvent) {
		evento.preventDefault();
		principal.focus();
		principal.scrollIntoView({ block: 'start' });
	}
</script>

<a class="pular" href="#conteudo" onclick={pular}>Pular para o conteúdo</a>

<div class="casca">
	<Trilho {secoes} {projeto} />
	<BarraSuperior {projeto} />
	<main id="conteudo" class="conteudo" tabindex="-1" bind:this={principal}>
		{@render children()}
	</main>
</div>

<style>
	.pular {
		position: fixed;
		top: 0.75rem;
		left: 0.75rem;
		z-index: 100;
		padding: 0.6rem 1rem;
		border-radius: var(--raio);
		background: var(--acento);
		color: var(--sobre-acento);
		font-weight: 600;
		text-decoration: none;
		transform: translateY(-200%);
	}

	.pular:focus-visible {
		transform: none;
		outline-color: var(--texto);
	}

	.casca {
		display: grid;
		grid-template-columns: var(--trilho-largura) minmax(0, 1fr);
		grid-template-rows: var(--barra-altura) minmax(0, 1fr);
		grid-template-areas:
			'trilho barra'
			'trilho conteudo';
		min-height: 100dvh;
	}

	.conteudo {
		grid-area: conteudo;
		width: 100%;
		max-width: var(--conteudo-largura);
		padding: 2.25rem clamp(1.25rem, 4vw, 3.5rem) 4rem;
	}

	.conteudo:focus {
		outline: none;
	}

	/* Tela estreita: o trilho vira uma barra fixa embaixo (ver Trilho.svelte). */
	@media (max-width: 820px) {
		.casca {
			grid-template-columns: minmax(0, 1fr);
			grid-template-rows: auto minmax(0, 1fr);
			grid-template-areas:
				'barra'
				'conteudo';
		}

		.conteudo {
			padding: 1.5rem 1rem calc(5.5rem + env(safe-area-inset-bottom));
		}
	}
</style>
