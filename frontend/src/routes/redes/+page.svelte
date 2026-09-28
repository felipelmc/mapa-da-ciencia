<script lang="ts">
	import ErroAoAbrir from '$lib/componentes/ErroAoAbrir.svelte';
	import PaginaDeSecao from '$lib/componentes/PaginaDeSecao.svelte';
	import Protegida from '$lib/componentes/Protegida.svelte';
	import { usarProjeto } from '$lib/dados/contexto';
	import { abrirCubo, reabrirCubo, type Aberto } from '$lib/dados/corpus';
	import type { FonteDeDados } from '$lib/dados/fonte';
	import { abrirCitacoes, abrirRedes } from '$lib/dados/redes';
	import VistaRedes from '$lib/redes/VistaRedes.svelte';
	import { rota } from '$lib/estado/url';
	import { secao } from '$lib/secoes';

	const { fonte, manifesto } = usarProjeto();
	// as redes existem, mas as entradas mudaram depois: o exportador as deixou de fora e marcou no manifesto
	const desatualizadas = (manifesto.desatualizadas ?? []).includes('redes');
	const mudou = (manifesto.mudancas?.redes ?? []).join(' e ');
	// no site publicado, nada de instrução de linha de comando para quem visita (o trilho nem mostra a vista)
	const publicado = !!manifesto.publicacao;

	// redes.json só existe depois de `mapa redes` (que pede os tópicos); sem ele, nenhum pedido além do manifesto
	async function abrir(cubo: Promise<Aberto | null>, f: FonteDeDados) {
		const aberto = await cubo;
		if (!aberto || !(await f.tem('redes'))) return null;
		const [redes, citacoes] = await Promise.all([abrirRedes(f, aberto.tabela.n), abrirCitacoes(f)]);
		return redes ? { aberto, redes, citacoes } : null;
	}
	let dados = $state(abrir(abrirCubo(fonte), fonte));
	const tentar = () => (dados = abrir(reabrirCubo(fonte), fonte));
</script>

<!-- o título fica na rota, fora do await: o anúncio da navegação (lido um instante depois) já o encontra -->
<svelte:head>
	<title>Redes · mapa da ciência</title>
</svelte:head>

{#await dados}
	<p class="aviso" role="status">Carregando as redes…</p>
{:then d}
	<Protegida oque="a vista Redes">
		{#if d}
			<VistaRedes aberto={d.aberto} redes={d.redes} citacoes={d.citacoes} />
		{:else if publicado}
			<PaginaDeSecao
				comTitulo={false}
				secao={secao('redes')}
				vazio={{ titulo: 'As redes não fazem parte desta publicação.', sobretitulo: 'Sem redes' }}
			>
				<p data-testid="redes-fora-da-publicacao">
					Este site foi publicado sem as redes de coautoria e de citação. As outras vistas mostram o corpus inteiro.
				</p>
			</PaginaDeSecao>
		{:else if desatualizadas}
			<PaginaDeSecao
				comTitulo={false}
				secao={secao('redes')}
				vazio={{ titulo: 'As redes deste projeto estão desatualizadas.', sobretitulo: 'Redes desatualizadas' }}
				desatualizados={['redes', 'citacoes']}
			>
				<p data-testid="redes-desatualizadas">
					{#if mudou}Mudou {mudou}{:else}As entradas mudaram{/if} depois da última <code>mapa redes</code>, e as redes
					antigas ficaram de fora para não misturar dados de momentos diferentes. Rode <code>mapa redes</code>{#if manifesto.api},
						ou a etapa Redes na vista <a href={rota('/projeto')}>Projeto</a>,{/if} e recarregue esta página.
				</p>
			</PaginaDeSecao>
		{:else}
			<PaginaDeSecao
				comTitulo={false}
				secao={secao('redes')}
				vazio={{ titulo: 'Este projeto ainda não tem redes.', sobretitulo: 'Sem redes' }}
			>
				<p>
					Rode <code>mapa coletar</code>, <code>mapa topicos</code> e <code>mapa redes</code> (com
					<code>mapa geografia</code> antes, para as redes de instituições e de estados){#if manifesto.api}, ou as etapas
						na vista <a href={rota('/projeto')}>Projeto</a>{/if}. Em seguida, recarregue esta página.
				</p>
			</PaginaDeSecao>
		{/if}
	</Protegida>
{:catch erro}
	<ErroAoAbrir oque="as redes" {erro} {tentar} />
{/await}

<style>
	.aviso {
		color: var(--texto-suave);
	}
</style>
