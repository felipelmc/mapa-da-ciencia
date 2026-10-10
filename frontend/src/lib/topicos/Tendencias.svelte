<script lang="ts">
	/**
	 * "Em alta" e "em queda": os tópicos cuja participação cresce ou cai de forma distinguível do acaso no recorte
	 * (ADR 0009), com a sparkline (observado e ajustado), a variação em pontos percentuais e o intervalo. Uma
	 * tendência cuja marcação some sem um dos anos leva a etiqueta "frágil", com esses anos.
	 */
	import { formatarDecimal, formatarPp } from '$lib/formato';
	import Sparkline from '$lib/graficos/Sparkline.svelte';
	import { textoFragil, type TendenciaTopico } from './tendencias';

	let {
		alta,
		queda,
		cores,
		rotulos,
		destaque,
		aoAbrir
	}: {
		alta: TendenciaTopico[];
		queda: TendenciaTopico[];
		cores: Map<number, string>;
		rotulos: Map<number, string>;
		destaque: Set<number>;
		aoAbrir: (id: number) => void;
	} = $props();
</script>

<div class="colunas">
	{#each [{ titulo: 'Em alta', lista: alta, id: 'alta' }, { titulo: 'Em queda', lista: queda, id: 'queda' }] as grupo (grupo.id)}
		{@const frageis = grupo.lista.filter((t) => t.fragil).length}
		<section class="coluna" data-testid="lista-{grupo.id}">
			<h3>
				{grupo.titulo}
				<span class="numero">({grupo.lista.length}{frageis ? `, ${frageis} ${frageis === 1 ? 'frágil' : 'frágeis'}` : ''})</span>
			</h3>
			{#if grupo.lista.length}
				<ol>
					{#each grupo.lista as t (t.id)}
						<li class:destacado={destaque.has(t.id)} data-id={t.id}>
							<span class="cor" style:background={cores.get(t.id)} aria-hidden="true"></span>
							<span class="nome">
								<button type="button" onclick={() => aoAbrir(t.id)}>{rotulos.get(t.id)}</button>
								{#if t.fragil}
									<span class="fragil" data-testid="marca-fragil">frágil</span>
								{/if}
							</span>
							<Sparkline
								observado={t.observado}
								ajustado={t.ajuste}
								cor={cores.get(t.id)}
								rotulo="Participação por ano de {rotulos.get(t.id)}"
							/>
							<span class="pp numero">{formatarPp(t.pp_periodo!)}</span>
							<span class="detalhe">
								{#if t.fragil}{textoFragil(t, t.observado.filter((v) => v !== null).length)};{/if}
								de {formatarDecimal(100 * t.prop_inicio!)}% a {formatarDecimal(100 * t.prop_fim!)}%
								({t.anos![0]}–{t.anos![1]}); IC 95% da inclinação: {formatarDecimal(t.ic95![0], 3)} a {formatarDecimal(t.ic95![1], 3)}
							</span>
						</li>
					{/each}
				</ol>
			{:else}
				<p class="vazio">Nenhum tópico no recorte.</p>
			{/if}
		</section>
	{/each}
</div>

<style>
	.colunas {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(22rem, 100%), 1fr));
		gap: 1.5rem;
	}

	/* cada coluna mede a própria largura: estreita (celular, ou duas colunas numa tela média), a sparkline desce */
	.coluna {
		container-type: inline-size;
	}

	h3 {
		margin: 0 0 0.6rem;
		font-size: 1rem;
		font-weight: 600;
	}

	h3 .numero {
		color: var(--texto-suave);
		font-weight: 400;
	}

	ol {
		display: grid;
		gap: 0.7rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	li {
		display: grid;
		grid-template-columns: 0.7rem minmax(0, 1fr) auto auto;
		grid-template-areas:
			'cor nome linha pp'
			'. detalhe detalhe detalhe';
		align-items: center;
		column-gap: 0.6rem;
		row-gap: 0.15rem;
		padding: 0.45rem 0.6rem;
		border-radius: 0.5rem;
	}

	li.destacado {
		background: var(--acento-suave);
	}

	.cor {
		grid-area: cor;
		width: 0.7rem;
		height: 0.7rem;
		border-radius: 50%;
	}

	.nome {
		grid-area: nome;
	}

	.nome button {
		padding: 0;
		border: none;
		background: none;
		color: var(--texto);
		font: inherit;
		text-align: left;
		cursor: pointer;
	}

	.nome button:hover {
		text-decoration: underline;
	}

	/* texto e contorno tracejado: a marca não depende da cor */
	.fragil {
		display: inline-block;
		margin-left: 0.35rem;
		padding: 0 0.4rem;
		border: 1px dashed var(--texto-suave);
		border-radius: 0.6rem;
		font-size: 0.72rem;
		color: var(--texto-suave);
		vertical-align: 0.1em;
	}

	li :global(svg) {
		grid-area: linha;
	}

	.pp {
		grid-area: pp;
		min-width: 6.5rem;
		text-align: right;
		font-size: 0.9rem;
	}

	.detalhe {
		grid-area: detalhe;
		font-family: var(--fonte-mono);
		font-size: 0.7rem;
		color: var(--texto-suave);
	}

	.vazio {
		color: var(--texto-suave);
	}

	@container (max-width: 28rem) {
		li {
			grid-template-columns: 0.7rem minmax(0, 1fr) auto;
			grid-template-areas:
				'cor nome pp'
				'. linha linha'
				'. detalhe detalhe';
		}
	}
</style>
