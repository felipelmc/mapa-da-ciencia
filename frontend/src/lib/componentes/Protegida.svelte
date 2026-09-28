<script lang="ts">
	/**
	 * Uma vista protegida contra erro ao desenhar: em vez de a página parar (em "Carregando…", ou em branco), aparece o
	 * aviso com "Tentar de novo", que desenha a vista outra vez.
	 *
	 * Vai dentro do `{:then}` de cada rota: o Svelte só entrega a um `<svelte:boundary>` o erro que acontece na
	 * criação dos filhos dele, e a do `{#await}` acontece quando a promessa resolve, fora da proteção da casca (que
	 * cobre o resto).
	 */
	import type { Snippet } from 'svelte';
	import ErroAoAbrir from './ErroAoAbrir.svelte';

	let { oque, children }: { oque: string; children: Snippet } = $props();
</script>

<svelte:boundary onerror={(erro) => console.error(erro)}>
	{@render children()}
	{#snippet failed(erro, recomecar)}
		<ErroAoAbrir {oque} {erro} tentar={recomecar} />
	{/snippet}
</svelte:boundary>
