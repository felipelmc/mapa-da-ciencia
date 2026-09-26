<script lang="ts">
	import { NOMES_TEMA, tema } from '$lib/estado/tema.svelte';
	import Icone from './Icone.svelte';

	const outro = $derived(tema.atual === 'observatorio' ? 'prancha' : 'observatorio');
	const rotulo = $derived(`Tema ${NOMES_TEMA[tema.atual]}. Mudar para ${NOMES_TEMA[outro]}`);
</script>

<button type="button" class="alternar" onclick={() => tema.alternar()} aria-label={rotulo} title={rotulo}>
	<span class="astro" data-tema={tema.atual}>
		<Icone nome={tema.atual === 'observatorio' ? 'lua' : 'sol'} tamanho={18} />
	</span>
	<span class="nome">{NOMES_TEMA[tema.atual]}</span>
</button>

<style>
	.alternar {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		height: 2.25rem;
		padding: 0 0.85rem 0 0.6rem;
		border: 1px solid var(--linha);
		border-radius: 999px;
		background: var(--superficie);
		color: var(--texto);
		font-size: 0.85rem;
		font-weight: 500;
		cursor: pointer;
	}

	.alternar:hover {
		border-color: var(--linha-forte);
	}

	.astro {
		display: grid;
		place-items: center;
		color: var(--acento);
	}

	@media (prefers-reduced-motion: no-preference) {
		.astro {
			transition: transform 400ms var(--curva);
		}

		.alternar:hover .astro {
			transform: rotate(-20deg);
		}
	}

	@media (max-width: 560px) {
		.nome {
			display: none;
		}

		.alternar {
			width: 2.25rem;
			padding: 0;
			justify-content: center;
		}
	}
</style>
