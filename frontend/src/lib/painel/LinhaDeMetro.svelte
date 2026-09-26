<script lang="ts" module>
	import type { NomeEtapa } from '$lib/dados/api';

	export interface Estacao {
		id: NomeEtapa | 'validacao';
		rotulo: string;
		frase: string;
		/** Variações da etapa (um piloto, uma estimativa...), além do "Rodar". */
		variacoes: { rotulo: string; opcoes: Record<string, unknown> }[];
	}

	export const ESTACOES: Estacao[] = [
		{
			id: 'coleta',
			rotulo: 'Coleta',
			frase: 'Artigos do SciELO e do OpenAlex',
			variacoes: [{ rotulo: 'Piloto com 20 documentos', opcoes: { limite: 20 } }]
		},
		{ id: 'topicos', rotulo: 'Tópicos', frase: 'Embeddings, agrupamento e rótulos', variacoes: [] },
		{ id: 'geografia', rotulo: 'Geografia', frase: 'Afiliações e instituições', variacoes: [] },
		{
			id: 'classificacao',
			rotulo: 'Classificação',
			frase: 'O codebook em cada resumo',
			variacoes: [
				{ rotulo: 'Estimar o tempo', opcoes: { estimar: true } },
				{ rotulo: 'Só a amostra', opcoes: { somente_amostra: true } },
				{ rotulo: 'Piloto com 20 documentos', opcoes: { limite: 20 } }
			]
		},
		{ id: 'validacao', rotulo: 'Validação', frase: 'A amostra codificada às cegas', variacoes: [] }
	];
</script>

<script lang="ts">
	/**
	 * As etapas do pipeline numa linha de metrô: cada estação mostra se a etapa nunca rodou, está em dia ou ficou
	 * para trás (o corpus, o codebook ou as correções mudaram depois), a última execução e o botão de rodar. A
	 * estação da etapa que está rodando pulsa. A validação não é um job: ela leva à codificação da amostra.
	 */
	import type { EtapasDoProjeto } from '$lib/dados/api';
	import { rota } from '$lib/estado/url';
	import { contar, formatarData, formatarDuracao, formatarInteiro } from '$lib/formato';

	let {
		etapas,
		rodando,
		ocupado,
		aoRodar,
		aoSortear
	}: {
		etapas: EtapasDoProjeto;
		/** A etapa do job em andamento, se houver. */
		rodando: string | null;
		ocupado: boolean;
		aoRodar: (etapa: NomeEtapa, opcoes: Record<string, unknown>) => void;
		aoSortear: (n: number) => void;
	} = $props();

	let tamanhoAmostra = $state(200);

	const NOMES = { pendente: 'Nunca rodou', em_dia: 'Em dia', desatualizada: 'Desatualizada' } as const;
	const acao = (estado: string) => (estado === 'pendente' ? 'Rodar' : estado === 'desatualizada' ? 'Atualizar' : 'Rodar de novo');
	const resumoContagens = (c: Record<string, number>) => {
		const [chave, n] = Object.entries(c).find(([k]) => ['documentos', 'classificados', 'vinculos', 'topicos'].includes(k)) ?? [];
		return chave ? `${formatarInteiro(n!)} ${chave}` : '';
	};
</script>

<ol class="metro" aria-label="Etapas do pipeline" data-testid="linha-metro">
	{#each ESTACOES as e (e.id)}
		{@const info = etapas[e.id]}
		{@const estado = rodando === e.id ? 'rodando' : info.estado}
		<li class="estacao" data-estado={estado} data-testid="estacao-{e.id}">
			<span class="ponto" aria-hidden="true"></span>
			<div class="corpo">
				<h3>{e.rotulo}</h3>
				<p class="frase">{e.frase}</p>
				<p class="estado" data-testid="estado-{e.id}">{estado === 'rodando' ? 'Rodando…' : NOMES[info.estado]}</p>
				{#if info.ultima}
					<p class="ultima">
						{formatarData(info.ultima.fim)} · {formatarDuracao(info.ultima.duracao_s)}{#if resumoContagens(info.ultima.contagens)}
							· {resumoContagens(info.ultima.contagens)}{/if}
					</p>
				{/if}
				{#if e.id === 'validacao'}
					{#if info.amostra}
						<p class="ultima">{contar(info.amostra.codificados, 'documento')} de {formatarInteiro(info.amostra.n)} codificados</p>
						<a class="botao" href={rota('/validacao/codificar')}>Codificar a amostra</a>
					{:else}
						<label class="tamanho">
							Documentos na amostra
							<input type="number" min="10" max="1000" bind:value={tamanhoAmostra} data-testid="tamanho-amostra" />
						</label>
						<button type="button" class="botao" disabled={ocupado} onclick={() => aoSortear(tamanhoAmostra)} data-testid="sortear-amostra">
							Sortear a amostra
						</button>
					{/if}
				{:else}
					<button type="button" class="botao" disabled={ocupado} onclick={() => aoRodar(e.id as NomeEtapa, {})} data-testid="rodar-{e.id}">
						{acao(info.estado)}
					</button>
					{#each e.variacoes as v (v.rotulo)}
						<button type="button" class="variacao" disabled={ocupado} onclick={() => aoRodar(e.id as NomeEtapa, v.opcoes)}>{v.rotulo}</button>
					{/each}
				{/if}
			</div>
		</li>
	{/each}
</ol>

<style>
	.metro {
		display: grid;
		grid-template-columns: repeat(5, minmax(0, 1fr));
		gap: 0;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.estacao {
		position: relative;
		display: grid;
		gap: 0.6rem;
		align-content: start;
		justify-items: start;
		padding-right: 1rem;
	}

	/* o trilho: uma linha que liga cada estação à seguinte */
	.estacao:not(:last-child)::after {
		content: '';
		position: absolute;
		top: 0.55rem;
		left: 1.2rem;
		right: 0;
		height: 3px;
		background: var(--linha-forte);
	}

	.estacao[data-estado='em_dia']:not(:last-child)::after {
		background: var(--acento);
	}

	.ponto {
		position: relative;
		z-index: 1;
		width: 1.2rem;
		height: 1.2rem;
		border: 3px solid var(--linha-forte);
		border-radius: 50%;
		background: var(--fundo);
	}

	[data-estado='em_dia'] .ponto {
		border-color: var(--acento);
		background: var(--acento);
	}

	[data-estado='desatualizada'] .ponto {
		border-color: var(--acento);
		border-style: dashed;
	}

	[data-estado='rodando'] .ponto {
		border-color: var(--acento);
		animation: pulsar 1.2s ease-in-out infinite;
	}

	@keyframes pulsar {
		50% {
			box-shadow: 0 0 0 0.45rem color-mix(in oklab, var(--acento) 25%, transparent);
		}
	}

	.corpo {
		display: grid;
		gap: 0.3rem;
		justify-items: start;
	}

	h3 {
		margin: 0;
		font-size: 1.05rem;
		font-weight: 500;
	}

	.frase,
	.ultima {
		margin: 0;
		font-size: 0.8rem;
		color: var(--texto-suave);
	}

	.estado {
		margin: 0;
		font-size: 0.78rem;
		font-family: var(--fonte-mono);
		color: var(--texto);
	}

	[data-estado='desatualizada'] .estado {
		color: var(--acento);
	}

	.botao {
		margin-top: 0.2rem;
		padding: 0.3rem 0.75rem;
		border: 1px solid var(--acento);
		border-radius: var(--raio-pequeno);
		background: var(--acento);
		color: var(--sobre-acento);
		font: inherit;
		font-size: 0.85rem;
		text-decoration: none;
		cursor: pointer;
	}

	.tamanho {
		display: grid;
		gap: 0.2rem;
		font-size: 0.78rem;
		color: var(--texto-suave);
	}

	.tamanho input {
		width: 6rem;
		padding: 0.2rem 0.4rem;
		border: 1px solid var(--linha-forte);
		border-radius: var(--raio-pequeno);
		background: var(--fundo);
		color: var(--texto);
		font: inherit;
	}

	.variacao {
		padding: 0;
		border: 0;
		background: none;
		color: var(--texto-suave);
		font: inherit;
		font-size: 0.78rem;
		text-decoration: underline;
		cursor: pointer;
	}

	button:disabled {
		opacity: 0.45;
		cursor: default;
	}

	@media (max-width: 900px) {
		.metro {
			grid-template-columns: minmax(0, 1fr);
			gap: 1.2rem;
		}

		.estacao {
			grid-template-columns: auto 1fr;
			align-items: start;
			gap: 0.8rem;
		}

		.estacao:not(:last-child)::after {
			top: 1.3rem;
			bottom: -1.2rem;
			left: 0.55rem;
			right: auto;
			width: 3px;
			height: auto;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		[data-estado='rodando'] .ponto {
			animation: none;
			box-shadow: 0 0 0 0.3rem color-mix(in oklab, var(--acento) 25%, transparent);
		}
	}
</style>
