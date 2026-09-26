<script lang="ts">
	/** Dica flutuante de um gráfico, posicionada em pixels dentro do contêiner (que deve ser `position: relative`). */
	let { x, y, linhas }: { x: number; y: number; linhas: string[] } = $props();
</script>

<div class="dica" role="status" style:left="{x}px" style:top="{y}px">
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

	.titulo {
		font-weight: 600;
	}
</style>
