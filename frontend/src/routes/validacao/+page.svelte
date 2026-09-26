<script lang="ts">
	import PaginaDeSecao from '$lib/componentes/PaginaDeSecao.svelte';
	import { usarProjeto } from '$lib/dados/contexto';
	import { rota } from '$lib/estado/url';
	import { secao } from '$lib/secoes';

	const { manifesto } = usarProjeto();
</script>

<PaginaDeSecao secao={secao('validacao')}>
	{#if manifesto.api}
		<p>
			<a href={rota('/validacao/codificar')} data-testid="link-codificar">Codificar a amostra →</a>
		</p>
	{/if}
</PaginaDeSecao>
