<script lang="ts">
	import PaginaDeSecao from '$lib/componentes/PaginaDeSecao.svelte';
	import { usarProjeto } from '$lib/dados/contexto';
	import { abrirCubo } from '$lib/dados/corpus';
	import VistaGeografia from '$lib/geografia/VistaGeografia.svelte';
	import { secao } from '$lib/secoes';

	const { fonte } = usarProjeto();
	// afiliacoes.json só existe depois de `mapa geografia` (e dos tópicos); sem ele, nenhum pedido é feito
	const dados = abrirCubo(fonte);
</script>

{#await dados}
	<p class="aviso" role="status">Carregando a geografia…</p>
{:then d}
	{#if d?.afiliacoes}
		<VistaGeografia aberto={d} afiliacoes={d.afiliacoes} />
	{:else}
		<PaginaDeSecao
			secao={secao('geografia')}
			vazio={{ titulo: 'Este projeto ainda não tem geografia.', sobretitulo: 'Sem geografia' }}
		>
			<p>
				Rode <code>mapa coletar</code>, <code>mapa topicos</code> e <code>mapa geografia</code>. Em seguida,
				recarregue esta página.
			</p>
		</PaginaDeSecao>
	{/if}
{:catch erro}
	<p class="aviso" role="alert">Não foi possível abrir a geografia: {erro.message}</p>
{/await}

<style>
	.aviso {
		color: var(--texto-suave);
	}
</style>
