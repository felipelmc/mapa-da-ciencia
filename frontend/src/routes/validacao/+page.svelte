<script lang="ts">
	import ErroAoAbrir from '$lib/componentes/ErroAoAbrir.svelte';
	import PaginaDeSecao from '$lib/componentes/PaginaDeSecao.svelte';
	import Protegida from '$lib/componentes/Protegida.svelte';
	import type { Validacao } from '$lib/contrato/tipos';
	import { usarProjeto } from '$lib/dados/contexto';
	import { abrirCorpus } from '$lib/dados/corpus';
	import { rota } from '$lib/estado/url';
	import { secao } from '$lib/secoes';
	import { ErroDaApi, lerMetricas } from '$lib/validacao/api';
	import VistaValidacao from '$lib/validacao/VistaValidacao.svelte';

	const { fonte, manifesto } = usarProjeto();
	// no painel local, as métricas vêm da API (calculadas agora, com as divergências de todos); no site, do contrato.
	// Sem conexão com o painel, o validacao.json exportado; sem amostra (404), o estado vazio; um erro do painel
	// aparece (com "Tentar de novo"), em vez de a vista mostrar em silêncio as métricas antigas do arquivo
	const abrir = () => {
		const metricas: Promise<Validacao | null> = manifesto.api
			? lerMetricas().catch((e) => {
					if (e instanceof ErroDaApi) {
						if (e.status === 404) return null;
						throw e;
					}
					return fonte.validacao();
				})
			: fonte.validacao();
		return Promise.all([metricas, fonte.codebook(), abrirCorpus(fonte)]);
	};
	let dados = $state(abrir());
</script>

<!-- o título fica na rota, fora do await: o anúncio da navegação (lido um instante depois) já o encontra -->
<svelte:head>
	<title>Validação · mapa da ciência</title>
</svelte:head>

{#await dados}
	<p class="aviso" role="status">Carregando a validação…</p>
{:then [validacao, codebook, corpus]}
	<Protegida oque="a vista Validação">
		{#if validacao && validacao.metricas.length}
			<VistaValidacao {validacao} {codebook} tabela={corpus?.tabela ?? null} api={manifesto.api} />
		{:else}
			<PaginaDeSecao
				comTitulo={false}
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
	</Protegida>
{:catch erro}
	<ErroAoAbrir oque="a validação" {erro} tentar={() => (dados = abrir())} />
{/await}

<style>
	.aviso {
		color: var(--texto-suave);
	}
</style>
