<script lang="ts">
	import ErroAoAbrir from '$lib/componentes/ErroAoAbrir.svelte';
	import PaginaDeSecao from '$lib/componentes/PaginaDeSecao.svelte';
	import type { Validacao } from '$lib/contrato/tipos';
	import { usarProjeto } from '$lib/dados/contexto';
	import { abrirCorpus } from '$lib/dados/corpus';
	import { rota } from '$lib/estado/url';
	import { secao } from '$lib/secoes';
	import { lerMetricas } from '$lib/validacao/api';
	import VistaValidacao from '$lib/validacao/VistaValidacao.svelte';

	const { fonte, manifesto } = usarProjeto();
	// no painel local, as métricas vêm da API (calculadas agora, com as divergências de todos); no site, do contrato
	const abrir = () => {
		const metricas: Promise<Validacao | null> = manifesto.api
			? lerMetricas().catch(() => fonte.validacao())
			: fonte.validacao();
		return Promise.all([metricas, fonte.codebook(), abrirCorpus(fonte)]);
	};
	let dados = $state(abrir());
</script>

{#await dados}
	<p class="aviso" role="status">Carregando a validação…</p>
{:then [validacao, codebook, corpus]}
	{#if validacao && validacao.metricas.length}
		<VistaValidacao {validacao} {codebook} tabela={corpus?.tabela ?? null} api={manifesto.api} />
	{:else}
		<PaginaDeSecao
			secao={secao('validacao')}
			vazio={{ titulo: 'Este projeto ainda não tem validação.', sobretitulo: 'Sem validação' }}
		>
			<p>
				Sorteie a amostra com <code>mapa validar amostra</code>, classifique-a com
				<code>mapa classificar --somente-amostra</code> e codifique-a
				{#if manifesto.api}(<a href={rota('/validacao/codificar')} data-testid="link-codificar">Codificar a amostra →</a>){:else}no painel local{/if}.
			</p>
		</PaginaDeSecao>
	{/if}
{:catch erro}
	<ErroAoAbrir oque="a validação" {erro} tentar={() => (dados = abrir())} />
{/await}

<style>
	.aviso {
		color: var(--texto-suave);
	}
</style>
