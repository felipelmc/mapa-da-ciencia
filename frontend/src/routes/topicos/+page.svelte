<script lang="ts">
	import ErroAoAbrir from '$lib/componentes/ErroAoAbrir.svelte';
	import PaginaDeSecao from '$lib/componentes/PaginaDeSecao.svelte';
	import Protegida from '$lib/componentes/Protegida.svelte';
	import { usarProjeto } from '$lib/dados/contexto';
	import { abrirCubo, reabrirCubo } from '$lib/dados/corpus';
	import { secao } from '$lib/secoes';
	import VistaTopicos from '$lib/topicos/VistaTopicos.svelte';

	const { fonte } = usarProjeto();
	// documentos.json e topicos.json só existem depois de `mapa topicos`; sem eles, nenhum pedido é feito
	let dados = $state(abrirCubo(fonte));
</script>

<!-- o título fica na rota, fora do await: o anúncio da navegação (lido um instante depois) já o encontra -->
<svelte:head>
	<title>Tópicos · mapa da ciência</title>
</svelte:head>

{#await dados}
	<p class="aviso" role="status">Carregando os tópicos…</p>
{:then d}
	<Protegida oque="a vista Tópicos">
		{#if d}
			<VistaTopicos topicos={d.topicos} cubo={d.cubo} />
		{:else}
			<PaginaDeSecao comTitulo={false} secao={secao('topicos')} vazio={{ titulo: 'Este projeto ainda não tem tópicos.', sobretitulo: 'Sem tópicos' }}>
				<p>Rode <code>mapa coletar</code> e depois <code>mapa topicos</code>. Em seguida, recarregue esta página.</p>
			</PaginaDeSecao>
		{/if}
	</Protegida>
{:catch erro}
	<ErroAoAbrir oque="os tópicos" {erro} tentar={() => (dados = reabrirCubo(fonte))} />
{/await}

<style>
	.aviso {
		color: var(--texto-suave);
	}
</style>
