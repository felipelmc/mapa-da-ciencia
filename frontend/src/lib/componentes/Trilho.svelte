<script lang="ts">
	import { page } from '$app/state';
	import { MediaQuery } from 'svelte/reactivity';
	import type { ProjetoAberto } from '$lib/dados/contexto';
	import { filtrosDaPagina } from '$lib/estado/filtros';
	import { escreverFiltros, recorteDe, rota } from '$lib/estado/url';
	import { formatarData } from '$lib/formato';
	import type { Secao } from '$lib/secoes';
	import Icone from './Icone.svelte';

	let { secoes, projeto }: { secoes: Secao[]; projeto: ProjetoAberto } = $props();

	const manifesto = $derived(projeto.manifesto);
	// a seção e as subrotas dela (Validação › Codificar)
	const ativa = (s: Secao) => page.route.id === s.caminho || (s.caminho !== '/' && !!page.route.id?.startsWith(`${s.caminho}/`));
	// as vistas de análise recebem o recorte atual (anos, revistas, tópicos, laço, lugares); as outras, não
	const recorte = $derived(escreverFiltros(recorteDe(filtrosDaPagina())));
	const destino = (s: Secao) => rota(s.caminho, s.recorte ? recorte : undefined);

	// Na tela estreita, o trilho é uma barra fixa embaixo, e a casca desconta a altura dela (`--altura-trilho`):
	// o mapa e os painéis sobre ele terminam onde a barra começa. A altura muda com a letra e a área segura.
	const estreita = new MediaQuery('(max-width: 820px)');
	let altura = $state(0);
	$effect(() => {
		const estilo = document.documentElement.style;
		if (estreita.current && altura) estilo.setProperty('--altura-trilho', `${altura}px`);
		else estilo.removeProperty('--altura-trilho');
	});
</script>

<aside class="lateral transicao-tema" bind:offsetHeight={altura}>
	<a class="marca" href={rota('/')}>
		<svg class="marca-astro" viewBox="0 0 24 24" aria-hidden="true">
			<circle cx="12" cy="12" r="10.5" />
			<path d="M12 3.2 13.8 10.2 20.8 12 13.8 13.8 12 20.8 10.2 13.8 3.2 12 10.2 10.2Z" />
		</svg>
		<span class="marca-nome">mapa <em>da</em> ciência</span>
	</a>

	<nav aria-label="Seções">
		<ul>
			{#each secoes as s (s.id)}
				<li class:separado={s.selo || s.soNoPainel || s.noSite}>
					{#if s.selo}
						<span class="item desativado" title="Chega {s.chegada}">
							<Icone nome={s.icone} />
							<span class="rotulo">{s.rotulo}</span>
							<span class="selo" aria-hidden="true">{s.selo}</span>
							<span class="visualmente-oculto">(desativada; chega {s.chegada})</span>
						</span>
					{:else}
						<a class="item" href={destino(s)} aria-current={ativa(s) ? 'page' : undefined}>
							<Icone nome={s.icone} />
							<span class="rotulo">{s.rotulo}</span>
						</a>
					{/if}
				</li>
			{/each}
		</ul>
	</nav>

	<dl class="rodape">
		<div>
			<dt>modo</dt>
			<dd>{manifesto.api ? 'painel local' : 'site estático'}</dd>
		</div>
		<div>
			<dt>contrato</dt>
			<dd class="numero">{manifesto.versao_contrato ?? '1.0'}</dd>
		</div>
		<div>
			<dt>pacote</dt>
			<dd class="numero">{manifesto.execucao.versao_pacote}</dd>
		</div>
		<div>
			<dt>gerado</dt>
			<dd>{formatarData(manifesto.gerado_em)}</dd>
		</div>
	</dl>
</aside>

<style>
	.lateral {
		grid-area: trilho;
		position: sticky;
		top: 0;
		height: 100dvh;
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
		padding: 0 0.75rem 1.25rem;
		border-right: 1px solid var(--linha);
		background: color-mix(in srgb, var(--superficie) 72%, transparent);
	}

	.marca {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		height: var(--barra-altura);
		padding: 0 0.6rem;
		margin: 0 -0.75rem;
		padding-left: 1.35rem;
		border-bottom: 1px solid var(--linha);
		text-decoration: none;
	}

	.marca-astro {
		width: 1.6rem;
		height: 1.6rem;
		flex: none;
	}

	.marca-astro circle {
		fill: none;
		stroke: var(--linha-forte);
		stroke-width: 1;
	}

	.marca-astro path {
		fill: var(--acento);
	}

	.marca-nome {
		font-family: var(--fonte-titulo);
		font-size: 1.2rem;
		font-weight: 480;
		letter-spacing: -0.01em;
		white-space: nowrap;
	}

	.marca-nome em {
		font-weight: 350;
		color: var(--texto-suave);
	}

	ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.15rem;
	}

	li.separado {
		margin-top: 0.9rem;
		padding-top: 0.9rem;
		border-top: 1px dashed var(--linha);
	}

	li.separado + li.separado {
		margin-top: 0;
		padding-top: 0;
		border-top: 0;
	}

	.item {
		position: relative;
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.55rem 0.75rem;
		border-radius: var(--raio);
		color: var(--texto-suave);
		text-decoration: none;
		font-size: 0.95rem;
		font-weight: 500;
	}

	a.item:hover {
		color: var(--texto);
		background: var(--superficie-alta);
	}

	a.item[aria-current='page'] {
		color: var(--texto);
		background: var(--acento-suave);
	}

	a.item[aria-current='page'] :global(.icone) {
		color: var(--acento);
	}

	a.item[aria-current='page']::before {
		content: '';
		position: absolute;
		left: -0.75rem;
		top: 0.45rem;
		bottom: 0.45rem;
		width: 2px;
		border-radius: 2px;
		background: var(--acento);
	}

	.desativado {
		color: var(--texto-fraco);
		cursor: not-allowed;
	}

	.selo {
		margin-left: auto;
		padding: 0.05rem 0.4rem;
		border: 1px solid var(--linha-forte);
		border-radius: 999px;
		font-family: var(--fonte-mono);
		font-size: 0.68rem;
		letter-spacing: 0.06em;
	}

	.rodape {
		margin: auto 0 0;
		padding: 0.9rem 0.6rem 0;
		border-top: 1px solid var(--linha);
		display: grid;
		gap: 0.2rem;
		font-family: var(--fonte-mono);
		font-size: 0.7rem;
		font-weight: 500;
		color: var(--texto-suave);
	}

	.rodape div {
		display: flex;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.rodape dd {
		margin: 0;
		text-align: right;
		color: var(--texto);
	}

	@media (prefers-reduced-motion: no-preference) {
		.item {
			transition:
				background-color var(--duracao) ease,
				color var(--duracao) ease;
		}
	}

	/* Tela estreita: barra fixa embaixo, só com os itens, rolando na horizontal se faltar espaço. */
	@media (max-width: 820px) {
		.lateral {
			position: fixed;
			inset: auto 0 0 0;
			z-index: 20;
			height: auto;
			padding: 0.35rem 0.5rem calc(0.35rem + env(safe-area-inset-bottom));
			border-right: 0;
			border-top: 1px solid var(--linha);
			background: color-mix(in srgb, var(--superficie) 94%, transparent);
		}

		.marca,
		.rodape {
			display: none;
		}

		nav {
			overflow-x: auto;
			scrollbar-width: none;
		}

		ul {
			grid-auto-flow: column;
			grid-auto-columns: minmax(4.4rem, 1fr);
			gap: 0.25rem;
		}

		li.separado {
			margin: 0;
			padding: 0;
			border: 0;
		}

		.item {
			flex-direction: column;
			gap: 0.2rem;
			padding: 0.45rem 0.35rem;
			font-size: 0.7rem;
			text-align: center;
		}

		a.item[aria-current='page']::before {
			left: 25%;
			right: 25%;
			top: -0.36rem;
			bottom: auto;
			width: auto;
			height: 2px;
		}

		.selo {
			position: absolute;
			top: 0.15rem;
			right: 0.35rem;
			margin: 0;
			font-size: 0.58rem;
		}
	}
</style>
