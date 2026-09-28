<script lang="ts">
	import PaginaDeSecao from '$lib/componentes/PaginaDeSecao.svelte';
	import { usarProjeto } from '$lib/dados/contexto';
	import { abrirCubo } from '$lib/dados/corpus';
	import { abrirCitacoes, abrirRedes } from '$lib/dados/redes';
	import VistaRedes from '$lib/redes/VistaRedes.svelte';
	import { secao } from '$lib/secoes';

	const { fonte } = usarProjeto();
	// redes.json só existe depois de `mapa redes` (que pede os tópicos); sem ele, nenhum pedido além do manifesto
	const dados = abrirCubo(fonte).then(async (aberto) => {
		if (!aberto || !(await fonte.tem('redes'))) return null;
		const [redes, citacoes] = await Promise.all([abrirRedes(fonte, aberto.tabela.n), abrirCitacoes(fonte)]);
		return redes ? { aberto, redes, citacoes } : null;
	});
</script>

{#await dados}
	<p class="aviso" role="status">Carregando as redes…</p>
{:then d}
	{#if d}
		<VistaRedes aberto={d.aberto} redes={d.redes} citacoes={d.citacoes} />
	{:else}
		<PaginaDeSecao secao={secao('redes')} vazio={{ titulo: 'Este projeto ainda não tem redes.', sobretitulo: 'Sem redes' }}>
			<p>
				Rode <code>mapa coletar</code>, <code>mapa topicos</code> e <code>mapa redes</code> (com <code>mapa geografia</code>
				antes, para as redes de instituições e de estados). Em seguida, recarregue esta página.
			</p>
		</PaginaDeSecao>
	{/if}
{:catch erro}
	<p class="aviso" role="alert">Não foi possível abrir as redes: {erro.message}</p>
{/await}

<style>
	.aviso {
		color: var(--texto-suave);
	}
</style>
