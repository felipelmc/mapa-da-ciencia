<script lang="ts">
	/**
	 * A vista Redes: quem escreve com quem, que instituições e que estados publicam juntos, e o que o corpus cita.
	 * Cada rede é um modo na URL
	 * (`rede=`), e o nó aberto no cartão também (`no=`), para um link reproduzir a tela. O recorte comum (anos,
	 * revistas, tópicos, busca, laço e lugares) vale para todas: as redes são recalculadas com os documentos que passam
	 * nele (`calculo.ts`), sobre o desenho fixo do corpus inteiro.
	 */
	import type { Aberto } from '$lib/dados/corpus';
	import type { TabelaCitacoes, TabelaRedes } from '$lib/dados/redes';
	import { filtrosDaPagina, mudarFiltros } from '$lib/estado/filtros';
	import type { Rede } from '$lib/estado/url';
	import ModoCitacoes from './ModoCitacoes.svelte';
	import ModoEstados from './ModoEstados.svelte';
	import ModoGrafo from './ModoGrafo.svelte';

	let { aberto, redes, citacoes }: { aberto: Aberto; redes: TabelaRedes; citacoes: TabelaCitacoes | null } = $props();

	const filtros = $derived(filtrosDaPagina());
	const em = '/redes';
	const falhas = $derived(aberto.cubo.falhas(filtros));

	const MODOS: { id: Rede; rotulo: string }[] = [
		{ id: 'coautoria', rotulo: 'Coautoria' },
		{ id: 'instituicoes', rotulo: 'Instituições' },
		{ id: 'estados', rotulo: 'Estados' },
		{ id: 'citacoes', rotulo: 'Citações' }
	];
	const modo = $derived(MODOS.some((m) => m.id === filtros.rede) ? filtros.rede : 'coautoria');
	const comInstituicoes = $derived(!!redes.instituicoes && !!aberto.afiliacoes);
</script>

<svelte:head>
	<title>Redes · mapa da ciência</title>
</svelte:head>

<div class="vista surgir">
	<header class="cabecalho">
		<h1>Redes</h1>
		<div class="modos" role="group" aria-label="Rede">
			{#each MODOS as m (m.id)}
				<button
					type="button"
					class="botao"
					aria-pressed={modo === m.id}
					data-testid="rede-{m.id}"
					onclick={() => mudarFiltros({ rede: m.id, no: null }, { em })}
				>
					{m.rotulo}
				</button>
			{/each}
		</div>
	</header>

	{#key modo}
		{#if modo === 'coautoria'}
			<ModoGrafo rede="coautoria" {aberto} {redes} afiliacoes={aberto.afiliacoes} {filtros} {falhas} />
		{:else if modo === 'instituicoes'}
			{#if comInstituicoes}
				<ModoGrafo rede="instituicoes" {aberto} {redes} afiliacoes={aberto.afiliacoes} {filtros} {falhas} />
			{:else}
				<p class="aviso" data-testid="rede-indisponivel">
					Sem a geografia, a rede de instituições fica de fora. Rode <code>mapa geografia</code> e depois
					<code>mapa redes</code>.
				</p>
			{/if}
		{:else if modo === 'estados'}
			{#if aberto.afiliacoes}
				<ModoEstados {aberto} {redes} afiliacoes={aberto.afiliacoes} {filtros} {falhas} />
			{:else}
				<p class="aviso" data-testid="rede-indisponivel">
					Sem a geografia, a colaboração entre estados fica de fora. Rode <code>mapa geografia</code> e depois
					<code>mapa redes</code>.
				</p>
			{/if}
		{:else if citacoes}
			<ModoCitacoes {aberto} {citacoes} {falhas} />
		{:else}
			<p class="aviso" data-testid="rede-indisponivel">
				Sem as referências do OpenAlex, as citações ficam de fora. Rode <code>mapa coletar</code> (que busca as
				referências) e depois <code>mapa redes</code>.
			</p>
		{/if}
	{/key}
</div>

<style>
	.vista {
		display: grid;
		/* sem isso, um SVG largo (antes de medir a tela) alarga a coluna e a página rola para o lado */
		grid-template-columns: minmax(0, 1fr);
		gap: 1.25rem;
		max-width: 84rem;
	}

	.cabecalho {
		display: grid;
		gap: 0.6rem;
	}

	h1 {
		margin: 0;
		font-size: clamp(2.2rem, 4.5vw, 3.2rem);
		font-weight: 380;
	}

	.modos {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
	}

	.aviso {
		max-width: 60rem;
		color: var(--texto-suave);
	}
</style>
