<script lang="ts">
	/**
	 * Dica flutuante de um gráfico, posicionada em pixels dentro do contêiner (que deve ser `position: relative`).
	 * Com `limites` (o tamanho do contêiner), a dica não sai dele: encosta na borda do lado e, sem espaço em cima,
	 * vai para baixo do ponto.
	 */
	let {
		x,
		y,
		linhas,
		limites = null
	}: { x: number; y: number; linhas: string[]; limites?: { largura: number; altura: number } | null } = $props();

	let largura = $state(0);
	let altura = $state(0);
	const presa = $derived.by(() => {
		if (!limites || !largura) return null;
		const esquerda = Math.min(Math.max(x - largura / 2, 4), Math.max(4, limites.largura - largura - 4));
		const acima = y - altura - 12;
		const topo = acima >= 4 ? acima : Math.min(y + 14, Math.max(4, limites.altura - altura - 4));
		return { esquerda, topo };
	});
</script>

<div
	class="dica"
	class:presa={!!presa}
	role="status"
	style:left="{presa ? presa.esquerda : x}px"
	style:top="{presa ? presa.topo : y}px"
	bind:offsetWidth={largura}
	bind:offsetHeight={altura}
>
	{#each linhas as l, i (i)}
		<span class:titulo={i === 0}>{l}</span>
	{/each}
</div>

<style>
	.dica {
		position: absolute;
		z-index: 10;
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
		max-width: 18rem;
		padding: 0.45rem 0.6rem;
		transform: translate(-50%, calc(-100% - 10px));
		pointer-events: none;
		font-size: 0.8rem;
		background: var(--superficie);
		border: 1px solid var(--linha-forte);
		border-radius: 0.45rem;
		box-shadow: 0 8px 24px rgb(0 0 0 / 0.25);
	}

	/* com os limites, a posição já vem calculada */
	.dica.presa {
		transform: none;
	}

	.titulo {
		font-weight: 600;
	}
</style>
