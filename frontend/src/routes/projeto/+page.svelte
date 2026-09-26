<script lang="ts">
	import PaginaDeSecao from '$lib/componentes/PaginaDeSecao.svelte';
	import { usarProjeto } from '$lib/dados/contexto';
	import { secao } from '$lib/secoes';

	const { manifesto } = usarProjeto();
</script>

<PaginaDeSecao secao={secao('projeto')}>
	{#if !manifesto.api}
		<p>
			Esta seção só existe no painel local. No site publicado os dados são somente leitura; para editar,
			rode <code>mapa painel</code> na pasta do projeto.
		</p>
	{/if}
</PaginaDeSecao>
