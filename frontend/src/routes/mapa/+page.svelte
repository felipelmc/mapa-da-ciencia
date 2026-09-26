<script lang="ts">
	import { page } from '$app/state';
	import PaginaDeSecao from '$lib/componentes/PaginaDeSecao.svelte';
	import { lerFiltros, parametrosDoHash, temFiltros } from '$lib/estado/url';
	import { formatarPeriodo } from '$lib/formato';
	import { secao } from '$lib/secoes';

	// O estado dos filtros já vive no hash (ADR 0002). O mapa ainda não existe, mas a
	// página mostra o que o link trouxe, para quem abrir um link compartilhado.
	const filtros = $derived(lerFiltros(parametrosDoHash(page.url)));

	const NOMES_COR = { topico: 'tópico', macrotema: 'macrotema', revista: 'revista', ano: 'ano' };
	const descricao = $derived(
		[
			filtros.anos && `anos ${formatarPeriodo(filtros.anos)}`,
			filtros.revistas.length && `revistas ${filtros.revistas.join(', ')}`,
			filtros.topicos.length && `tópicos ${filtros.topicos.join(', ')}`,
			filtros.cor !== 'topico' && `cor por ${NOMES_COR[filtros.cor]}`,
			filtros.busca && `busca “${filtros.busca}”`,
			filtros.doc && `documento ${filtros.doc}`
		].filter(Boolean) as string[]
	);
</script>

<PaginaDeSecao secao={secao('mapa')}>
	{#if temFiltros(filtros)}
		<p data-testid="filtros-do-link">
			Este link traz filtros: <strong>{descricao.join(' · ')}</strong>. Eles serão aplicados quando o mapa
			chegar.
		</p>
	{/if}
</PaginaDeSecao>
