<script lang="ts">
	import PaginaDeSecao from '$lib/componentes/PaginaDeSecao.svelte';
	import { usarProjeto } from '$lib/dados/contexto';
	import { abrirCubo } from '$lib/dados/corpus';
	import { secao } from '$lib/secoes';
	import VistaTopicos from '$lib/topicos/VistaTopicos.svelte';

	const { fonte } = usarProjeto();
	// documentos.json e topicos.json só existem depois de `mapa topicos`; sem eles, nenhum pedido é feito
	const dados = abrirCubo(fonte);
</script>

{#await dados}
	<p class="aviso" role="status">Carregando os tópicos…</p>
{:then d}
	{#if d}
		<VistaTopicos topicos={d.topicos} cubo={d.cubo} />
	{:else}
		<PaginaDeSecao secao={secao('topicos')} vazio={{ titulo: 'Este projeto ainda não tem tópicos.', sobretitulo: 'Sem tópicos' }}>
			<p>Rode <code>mapa coletar</code> e depois <code>mapa topicos</code>. Em seguida, recarregue esta página.</p>
		</PaginaDeSecao>
	{/if}
{:catch erro}
	<p class="aviso" role="alert">Não foi possível abrir os tópicos: {erro.message}</p>
{/await}

<style>
	.aviso {
		color: var(--texto-suave);
	}
</style>
