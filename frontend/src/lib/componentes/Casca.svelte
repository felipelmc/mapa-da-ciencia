<script lang="ts">
	import type { Snippet } from 'svelte';
	import { page } from '$app/state';
	import { definirProjeto, type ProjetoAberto } from '$lib/dados/contexto';
	import { lerHash } from '$lib/estado/url';
	import BarraDeRecorte from '$lib/recorte/BarraDeRecorte.svelte';
	import { secoesDoTrilho } from '$lib/secoes';
	import BarraSuperior from './BarraSuperior.svelte';
	import Protegida from './Protegida.svelte';
	import Trilho from './Trilho.svelte';

	let { projeto, children }: { projeto: ProjetoAberto; children: Snippet } = $props();

	// O projeto não muda depois de aberto; as páginas o leem com usarProjeto().
	// svelte-ignore state_referenced_locally
	definirProjeto(projeto);

	const secoes = $derived(secoesDoTrilho(projeto.manifesto));
	const caminho = $derived(lerHash(page.url.hash).caminho);
	const secao = $derived(secoes.find((s) => s.caminho === caminho));
	const telaCheia = $derived(secao?.telaCheia ?? false);
	// a barra do recorte aparece nas vistas de análise, e só quando há documentos (projeto vazio: nenhum pedido)
	const comRecorte = $derived(!!secao?.recorte && projeto.manifesto.arquivos.includes('documentos'));

	let principal: HTMLElement;

	// Modo apresentação (tecla P): esconde o trilho e as barras e aumenta a tipografia, para projetar. Esc sai.
	// Não vale na codificação, que usa o teclado para responder.
	let apresentando = $state(false);
	const naCodificacao = $derived(caminho.startsWith('/validacao/codificar'));
	function tecla(e: KeyboardEvent) {
		const alvo = e.target as HTMLElement;
		if (alvo.closest('input, textarea, select, [contenteditable]') || e.metaKey || e.ctrlKey || e.altKey) return;
		if ((e.key === 'p' || e.key === 'P') && !naCodificacao) {
			apresentando = !apresentando;
			e.preventDefault();
		} else if (e.key === 'Escape' && apresentando) {
			apresentando = false;
			// o Esc só sai do modo apresentação (não fecha também o cartão, nem solta a comunidade)
			e.preventDefault();
		}
	}
	$effect(() => {
		document.documentElement.dataset.apresentacao = apresentando ? 'sim' : 'nao';
	});

	// Com o router por hash, um href="#conteudo" viraria uma navegação para a rota
	// "conteudo" (404). O link de pular só move o foco, sem tocar na URL.
	function pular(evento: MouseEvent) {
		evento.preventDefault();
		principal.focus();
		principal.scrollIntoView({ block: 'start' });
	}
</script>

<svelte:window onkeydown={tecla} />

<a class="pular" href="#conteudo" onclick={pular}>Pular para o conteúdo</a>

{#if apresentando}
	<p class="aviso-apresentacao" role="status" data-testid="modo-apresentacao">Modo apresentação: <kbd>P</kbd> ou <kbd>Esc</kbd> para sair</p>
{/if}

<div class="casca" class:tela-cheia={telaCheia} class:apresentando>
	<Trilho {secoes} {projeto} />
	<BarraSuperior {projeto} />
	{#if comRecorte}
		<BarraDeRecorte />
	{/if}
	<main id="conteudo" class="conteudo" class:tela-cheia={telaCheia} tabindex="-1" bind:this={principal}>
		<!-- um erro ao desenhar uma vista vira o aviso com "Tentar de novo", em vez de deixar a página parada; a troca
		     de rota recomeça do zero (o {#key}). As rotas protegem também o que desenham dentro do {#await} -->
		{#key caminho}
			<Protegida oque={secao ? `a vista ${secao.rotulo}` : 'esta página'}>
				{@render children()}
			</Protegida>
		{/key}
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

	.casca.apresentando {
		grid-template-columns: minmax(0, 1fr);
		grid-template-rows: minmax(0, 1fr);
		grid-template-areas: 'conteudo';
	}

	.casca.apresentando > :global(:not(main)) {
		display: none;
	}

	:global(html[data-apresentacao='sim']) {
		font-size: 125%;
	}

	.aviso-apresentacao {
		position: fixed;
		right: 1rem;
		bottom: 1rem;
		z-index: 50;
		margin: 0;
		padding: 0.4rem 0.8rem;
		border-radius: var(--raio);
		background: var(--superficie-alta);
		color: var(--texto-suave);
		font-size: 0.75rem;
		animation: sumir 4s ease forwards;
	}

	@keyframes sumir {
		0%,
		70% {
			opacity: 1;
		}
		100% {
			opacity: 0;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.aviso-apresentacao {
			animation: none;
			opacity: 0.8;
		}
	}

	.casca {
		/* quanto a coluna do conteúdo se afasta das bordas da área à direita do trilho: as barras alinham com ela */
		--sobra-lateral: max(0px, calc((100% - var(--conteudo-largura)) / 2));
		display: grid;
		grid-template-columns: var(--trilho-largura) minmax(0, 1fr);
		grid-template-rows: var(--barra-altura) auto minmax(0, 1fr);
		grid-template-areas:
			'trilho barra'
			'trilho recorte'
			'trilho conteudo';
		min-height: 100dvh;
	}

	/* nas vistas de tela cheia (o mapa), a casca tem a altura da janela, e o conteúdo fica com o que sobra */
	.casca.tela-cheia {
		height: 100dvh;
		--sobra-lateral: 0px;
	}

	.conteudo {
		grid-area: conteudo;
		width: 100%;
		max-width: var(--conteudo-largura);
		/* centrado na área que o trilho deixa, e não encostado nele */
		margin-inline: auto;
		padding: 2.25rem clamp(1.25rem, 4vw, 3.5rem) 4rem;
	}

	.conteudo:focus {
		outline: none;
	}

	/* O mapa ocupa tudo: sem margens, sem largura máxima, no espaço que sobra na janela */
	.conteudo.tela-cheia {
		max-width: none;
		padding: 0;
		min-height: 0;
		overflow: hidden;
	}

	/* Tela estreita: o trilho vira uma barra fixa embaixo (ver Trilho.svelte). */
	@media (max-width: 820px) {
		.casca {
			grid-template-columns: minmax(0, 1fr);
			grid-template-rows: auto auto minmax(0, 1fr);
			grid-template-areas:
				'barra'
				'recorte'
				'conteudo';
		}

		/* sem zerar o min-height (100dvh), ele venceria a altura, e o mapa passaria por baixo da barra */
		.casca.tela-cheia {
			min-height: 0;
			height: calc(100dvh - var(--altura-trilho, calc(4.5rem + env(safe-area-inset-bottom))));
		}

		.conteudo {
			padding: 1.5rem 1rem calc(1rem + var(--altura-trilho, calc(4.5rem + env(safe-area-inset-bottom))));
		}

		.conteudo.tela-cheia {
			padding: 0;
		}
	}
</style>
