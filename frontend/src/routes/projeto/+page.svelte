<script lang="ts">
	import { FonteApi } from '$lib/dados/api';
	import { usarProjeto } from '$lib/dados/contexto';
	import VistaMetodologia from '$lib/painel/VistaMetodologia.svelte';
	import VistaProjeto from '$lib/painel/VistaProjeto.svelte';

	const { fonte, manifesto } = usarProjeto();
</script>

{#if manifesto.api && fonte instanceof FonteApi}
	<VistaProjeto {fonte} {manifesto} />
{:else}
	<!-- no site publicado (sem API), a seção Projeto vira a Metodologia -->
	<VistaMetodologia {manifesto} />
{/if}
