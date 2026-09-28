<script lang="ts">
	import VistaClassificacao from '$lib/classificacao/VistaClassificacao.svelte';
	import ErroAoAbrir from '$lib/componentes/ErroAoAbrir.svelte';
	import PaginaDeSecao from '$lib/componentes/PaginaDeSecao.svelte';
	import { usarProjeto } from '$lib/dados/contexto';
	import { abrirCubo, reabrirCubo } from '$lib/dados/corpus';
	import { secao } from '$lib/secoes';

	const { fonte } = usarProjeto();
	// classificacoes.json só existe depois de `mapa classificar`; sem ele, a vista explica o que falta
	const abrir = (cubo: typeof abrirCubo) =>
		Promise.all([fonte.classificacoes(), fonte.codebook(), fonte.validacao()]).then(
			async ([classificacoes, codebook, validacao]) =>
				classificacoes && codebook ? { classificacoes, codebook, validacao, aberto: await cubo(fonte) } : null
		);
	let dados = $state(abrir(abrirCubo));
</script>

{#await dados}
	<p class="aviso" role="status">Carregando a classificação…</p>
{:then d}
	{#if d?.aberto && Object.keys(d.aberto.tabela.cls).length}
		<VistaClassificacao aberto={d.aberto} codebook={d.codebook} classificacoes={d.classificacoes} validacao={d.validacao} />
	{:else}
		<PaginaDeSecao
			secao={secao('classificacao')}
			vazio={{ titulo: 'Este projeto ainda não tem classificação.', sobretitulo: 'Sem classificação' }}
		>
			<p>
				Rode <code>mapa coletar</code>, <code>mapa topicos</code> e <code>mapa classificar</code> (veja o guia
				"Classificar os resumos"). Em seguida, recarregue esta página.
			</p>
		</PaginaDeSecao>
	{/if}
{:catch erro}
	<ErroAoAbrir oque="a classificação" {erro} tentar={() => (dados = abrir(reabrirCubo))} />
{/await}

<style>
	.aviso {
		color: var(--texto-suave);
	}
</style>
