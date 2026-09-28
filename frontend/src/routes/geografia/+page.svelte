<script lang="ts">
	import ErroAoAbrir from '$lib/componentes/ErroAoAbrir.svelte';
	import PaginaDeSecao from '$lib/componentes/PaginaDeSecao.svelte';
	import { usarProjeto } from '$lib/dados/contexto';
	import { abrirCubo, reabrirCubo } from '$lib/dados/corpus';
	import VistaGeografia from '$lib/geografia/VistaGeografia.svelte';
	import { secao } from '$lib/secoes';

	const { fonte } = usarProjeto();
	// afiliacoes.json só existe depois de `mapa geografia` (e dos tópicos); sem ele, nenhum pedido é feito
	let dados = $state(abrirCubo(fonte));
	const tentar = () => (dados = reabrirCubo(fonte));
</script>

<!-- o título fica na rota, fora do await: o anúncio da navegação (lido um instante depois) já o encontra -->
<svelte:head>
	<title>Geografia · mapa da ciência</title>
</svelte:head>

{#await dados}
	<p class="aviso" role="status">Carregando a geografia…</p>
{:then d}
	{#if d?.afiliacoes}
		<VistaGeografia aberto={d} afiliacoes={d.afiliacoes} />
	{:else if d?.erroAfiliacoes}
		<ErroAoAbrir oque="as afiliações" erro={d.erroAfiliacoes} {tentar} />
	{:else}
		<PaginaDeSecao
			comTitulo={false}
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
	<ErroAoAbrir oque="a geografia" {erro} {tentar} />
{/await}

<style>
	.aviso {
		color: var(--texto-suave);
	}
</style>
