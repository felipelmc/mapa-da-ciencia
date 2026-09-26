<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		titulo: string;
		/** Sobretítulo curto, em versaletes. */
		sobretitulo?: string;
		children?: Snippet;
		/** Nível do título (a página já tem um h1). */
		nivel?: 2 | 3;
	}

	let { titulo, sobretitulo, children, nivel = 2 }: Props = $props();
</script>

<!--
	Estado vazio com a ilustração de um campo de visão de telescópio sem nada à vista:
	retículo, marcas de grau e uma estrela apagada fora do centro.
-->
<section class="vazio transicao-tema">
	<svg class="reticulo" viewBox="0 0 120 120" aria-hidden="true">
		<circle class="anel" cx="60" cy="60" r="54" />
		<circle class="anel-fino" cx="60" cy="60" r="38" />
		<circle class="anel-fino" cx="60" cy="60" r="20" />
		{#each Array.from({ length: 36 }, (_, i) => i * 10) as grau (grau)}
			<line
				class="marca"
				x1="60"
				y1={grau % 90 === 0 ? 1 : 3}
				x2="60"
				y2="8"
				transform="rotate({grau} 60 60)"
			/>
		{/each}
		<line class="cruz" x1="60" y1="14" x2="60" y2="50" />
		<line class="cruz" x1="60" y1="70" x2="60" y2="106" />
		<line class="cruz" x1="14" y1="60" x2="50" y2="60" />
		<line class="cruz" x1="70" y1="60" x2="106" y2="60" />
		<circle class="astro" cx="81" cy="41" r="2.2" />
	</svg>

	<div class="texto">
		{#if sobretitulo}<p class="rotulo-miudo">{sobretitulo}</p>{/if}
		<svelte:element this={`h${nivel}`} class="titulo">{titulo}</svelte:element>
		{#if children}<div class="corpo">{@render children()}</div>{/if}
	</div>
</section>

<style>
	.vazio {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		align-items: center;
		gap: clamp(1.25rem, 4vw, 3rem);
		padding: clamp(1.5rem, 4vw, 2.75rem);
		border: 1px solid var(--linha);
		border-radius: var(--raio);
		background:
			radial-gradient(28rem 16rem at 0% 0%, var(--acento-suave), transparent 70%),
			var(--superficie);
		box-shadow: var(--sombra);
	}

	.reticulo {
		width: clamp(6.5rem, 14vw, 9.5rem);
		height: auto;
		overflow: visible;
	}

	.anel,
	.anel-fino,
	.marca,
	.cruz {
		fill: none;
		stroke: var(--linha-forte);
		vector-effect: non-scaling-stroke;
	}

	.anel {
		stroke-width: 1.25;
	}

	.anel-fino {
		stroke-width: 1;
		stroke-dasharray: 2 4;
	}

	.cruz {
		stroke: var(--acento);
		stroke-opacity: 0.55;
	}

	.astro {
		fill: var(--acento);
		opacity: 0.8;
	}

	.texto {
		display: grid;
		gap: 0.6rem;
		max-width: 44rem;
	}

	.titulo {
		font-size: clamp(1.5rem, 2.6vw, 2rem);
	}

	.corpo {
		display: grid;
		gap: 0.75rem;
		color: var(--texto-suave);
	}

	.corpo :global(strong) {
		color: var(--texto);
		font-weight: 600;
	}

	@media (max-width: 560px) {
		.vazio {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
