<script lang="ts">
	import Icone from './Icone.svelte';

	/** Aviso de que o projeto é o exemplo sintético do repositório (dados fictícios). */
	let { descricao }: { descricao: string } = $props();
</script>

<aside class="aviso" aria-labelledby="aviso-exemplo-titulo" data-testid="aviso-exemplo">
	<span class="icone-aviso"><Icone nome="aviso" tamanho={22} /></span>
	<div>
		<p class="titulo" id="aviso-exemplo-titulo">Dados fictícios</p>
		<p class="texto">{descricao}</p>
	</div>
</aside>

<style>
	.aviso {
		display: flex;
		align-items: flex-start;
		gap: 0.9rem;
		padding: 0.9rem 1.1rem 0.9rem 1.25rem;
		border: 1px solid var(--linha);
		border-left: 0;
		border-radius: var(--raio);
		/* Faixa listrada à esquerda, como a tarja de uma prancha de prova. */
		background:
			repeating-linear-gradient(
					-45deg,
					var(--acento) 0 6px,
					transparent 6px 12px
				)
				left / 6px 100% no-repeat,
			var(--superficie);
		padding-left: 1.6rem;
	}

	.icone-aviso {
		color: var(--acento);
		margin-top: 0.1rem;
	}

	.titulo {
		font-family: var(--fonte-mono);
		font-size: 0.78rem;
		font-weight: 600;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--acento);
	}

	.texto {
		color: var(--texto);
	}
</style>
