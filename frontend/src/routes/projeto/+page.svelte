<script lang="ts">
	import PaginaDeSecao from '$lib/componentes/PaginaDeSecao.svelte';
	import { FonteApi } from '$lib/dados/api';
	import { usarProjeto } from '$lib/dados/contexto';
	import VistaProjeto from '$lib/painel/VistaProjeto.svelte';
	import { secao } from '$lib/secoes';

	const { fonte, manifesto } = usarProjeto();
</script>

{#if manifesto.api && fonte instanceof FonteApi}
	<VistaProjeto {fonte} {manifesto} />
{:else}
	<PaginaDeSecao secao={secao('projeto')}>
		<p>
			Esta seção só existe no painel local. No site publicado os dados são somente leitura; para rodar as etapas e
			editar o projeto, rode <code>mapa painel</code> na pasta do projeto.
		</p>
	</PaginaDeSecao>
{/if}
