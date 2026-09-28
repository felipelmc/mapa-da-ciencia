<script lang="ts">
	/**
	 * Falha ao abrir os dados de uma vista (rede instável, arquivo indisponível): a mensagem e "Tentar de novo",
	 * que pede os arquivos outra vez sem recarregar a página (a camada de dados não guarda as falhas).
	 */
	let { oque, erro, tentar }: { oque: string; erro: unknown; tentar: () => void } = $props();

	const mensagem = $derived(erro instanceof Error ? erro.message : String(erro));
</script>

<div class="falha" data-testid="falha-ao-abrir">
	<p role="alert">Não foi possível abrir {oque}: {mensagem}</p>
	<button type="button" class="botao" onclick={tentar}>Tentar de novo</button>
</div>

<style>
	.falha {
		display: grid;
		justify-items: start;
		gap: 0.75rem;
		color: var(--texto-suave);
	}
</style>
