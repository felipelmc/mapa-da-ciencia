<script lang="ts">
	import PaginaDeSecao from '$lib/componentes/PaginaDeSecao.svelte';
	import { usarProjeto } from '$lib/dados/contexto';
	import { abrirCubo } from '$lib/dados/corpus';
	import { abrirCitacoes, abrirRedes } from '$lib/dados/redes';
	import VistaRedes from '$lib/redes/VistaRedes.svelte';
	import { rota } from '$lib/estado/url';
	import { secao } from '$lib/secoes';

	const { fonte, manifesto } = usarProjeto();
	// as redes existem, mas as entradas mudaram depois: o exportador as deixou de fora e marcou no manifesto
	const desatualizadas = (manifesto.desatualizadas ?? []).includes('redes');
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
		{#if desatualizadas}
			<PaginaDeSecao secao={secao('redes')} vazio={{ titulo: 'As redes deste projeto estão desatualizadas.', sobretitulo: 'Redes desatualizadas' }}>
				<p data-testid="redes-desatualizadas">
					O corpus, os tópicos, a geografia, as referências ou o <code>pessoas.yaml</code> mudaram depois da última
					<code>mapa redes</code>, e as redes antigas ficaram de fora para não misturar dados de momentos diferentes.
					Rode <code>mapa redes</code>{#if manifesto.api}, ou a etapa Redes na vista <a href={rota('/projeto')}>Projeto</a>,{/if}
					e recarregue esta página. O <code>mapa status</code> diz o que mudou.
				</p>
			</PaginaDeSecao>
		{:else}
			<PaginaDeSecao secao={secao('redes')} vazio={{ titulo: 'Este projeto ainda não tem redes.', sobretitulo: 'Sem redes' }}>
				<p>
					Rode <code>mapa coletar</code>, <code>mapa topicos</code> e <code>mapa redes</code> (com
					<code>mapa geografia</code> antes, para as redes de instituições e de estados){#if manifesto.api}, ou as
					etapas na vista <a href={rota('/projeto')}>Projeto</a>{/if}. Em seguida, recarregue esta página.
				</p>
			</PaginaDeSecao>
		{/if}
	{/if}
{:catch erro}
	<p class="aviso" role="alert">Não foi possível abrir as redes: {erro.message}</p>
{/await}

<style>
	.aviso {
		color: var(--texto-suave);
	}
</style>
