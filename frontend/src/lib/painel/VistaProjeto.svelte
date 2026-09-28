<script lang="ts">
	/**
	 * A vista Projeto, só no painel local: as etapas do pipeline numa linha de metrô, o job em andamento ao vivo
	 * (com cancelar), a estimativa da classificação, os modelos do projeto no Ollama (com o download do que falta)
	 * e as últimas execuções.
	 *
	 * Ao abrir, retoma o acompanhamento de um job que já estava rodando (outra aba, ou antes de um reload).
	 */
	import { onDestroy, onMount } from 'svelte';
	import type { Manifesto } from '$lib/contrato/tipos';
	import type { EtapasDoProjeto, Estimativa, FonteApi, InfoModelos, NomeEtapa } from '$lib/dados/api';
	import { ErroDaApi } from '$lib/dados/pedir';
	import { formatarData, formatarDuracao, formatarInteiro } from '$lib/formato';
	import Assistente from './Assistente.svelte';
	import JobAoVivo from './JobAoVivo.svelte';
	import LinhaDeMetro, { ESTACOES } from './LinhaDeMetro.svelte';
	import type { Job, JobAoVivo as EstadoJob } from './job';

	let { fonte, manifesto }: { fonte: FonteApi; manifesto: Manifesto } = $props();

	let etapas = $state<EtapasDoProjeto | null>(null);
	let estimativa = $state<Estimativa | null>(null);
	let modelos = $state<InfoModelos | null>(null);
	let historico = $state<Job[]>([]);
	let aoVivo = $state<EstadoJob | null>(null);
	let aviso = $state<string | null>(null);
	let configurando = $state(false);
	let salvo = $state(false);
	let parar: (() => void) | null = null;

	const ocupado = $derived(!!aoVivo && !aoVivo.terminado);
	const NOMES: Record<string, string> = {
		...Object.fromEntries(ESTACOES.map((e) => [e.id, e.rotulo])),
		modelo: 'Download do modelo'
	};
	const rotuloJob = (j: { etapa: string }) =>
		j.etapa === 'modelo' ? 'Download do modelo' : `Etapa: ${NOMES[j.etapa] ?? j.etapa}`;

	async function atualizar() {
		[etapas, estimativa, historico] = await Promise.all([
			fonte.etapas(),
			fonte.estimativaClassificacao(),
			fonte.jobs()
		]);
		fonte
			.modelos()
			.then((m) => (modelos = m))
			.catch(() => (modelos = null));
	}

	function acompanhar(job: Job) {
		parar?.();
		parar = fonte.acompanhar(job, (e) => {
			const terminou = e.terminado && !aoVivo?.terminado;
			aoVivo = e;
			if (terminou) void atualizar();
		});
	}

	async function rodar(etapa: NomeEtapa | 'modelo', opcoes: Record<string, unknown> = {}) {
		aviso = null;
		try {
			const job =
				etapa === 'modelo' ? await fonte.baixarModelo(String(opcoes.modelo)) : await fonte.iniciarEtapa(etapa, opcoes);
			acompanhar(job);
			historico = [job, ...historico];
		} catch (e) {
			aviso = e instanceof ErroDaApi ? e.message : `Não foi possível começar: ${(e as Error).message}`;
		}
	}

	async function aoSortear(n: number) {
		aviso = null;
		try {
			await fonte.sortearAmostra(n);
			etapas = await fonte.etapas();
		} catch (e) {
			aviso = e instanceof ErroDaApi ? e.message : `Não foi possível sortear a amostra: ${(e as Error).message}`;
		}
	}

	onMount(async () => {
		try {
			await atualizar();
		} catch (e) {
			aviso = `Não foi possível falar com o painel: ${(e as Error).message}. Confira se o \`mapa painel\` ainda está rodando.`;
			return;
		}
		const ativo = historico.find((j) => j.estado === 'na_fila' || j.estado === 'rodando');
		if (ativo) acompanhar(ativo);
	});
	onDestroy(() => parar?.());

	const faltando = $derived(
		modelos ? Object.entries(modelos.projeto).filter(([, m]) => !m.instalado) : []
	);
	const PAPEIS = { embeddings: 'Embeddings', classificacao: 'Classificação', rotulos: 'Rótulos' } as const;
	const ESTADOS = { na_fila: 'na fila', rodando: 'rodando', concluido: 'concluído', falhou: 'falhou', cancelado: 'cancelado' } as const;
	const PERFIS: Record<string, string> = { leve: 'leve', padrao: 'padrão', forte: 'forte' };
	const gb = (x: number | null | undefined) => (x == null ? '' : `${x.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} GB`);
</script>

<svelte:head>
	<title>Projeto · mapa da ciência</title>
</svelte:head>

<div class="vista surgir">
	<header class="cabecalho">
		<h1>Projeto</h1>
		<p class="lide">
			<strong>{manifesto.projeto.titulo}</strong>. Rode cada etapa daqui, na ordem da linha; as que ficaram para trás
			(depois de uma coleta nova, ou de uma mudança no codebook) aparecem tracejadas.
		</p>
	</header>

	{#if aviso}<p class="aviso" role="alert" data-testid="aviso-projeto">{aviso}</p>{/if}
	{#if salvo}<p class="ok-salvo" role="status" data-testid="projeto-salvo">Projeto salvo. As etapas afetadas aparecem desatualizadas na linha.</p>{/if}

	{#if configurando}
		<Assistente
			{fonte}
			aoFechar={(salvou) => {
				configurando = false;
				salvo = salvou;
				if (salvou) void atualizar();
			}}
			aoPiloto={() => rodar('coleta', { limite: 20 })}
		/>
	{:else}
		<button type="button" class="configurar" disabled={ocupado} onclick={() => ((configurando = true), (salvo = false))} data-testid="configurar">
			Configurar o projeto
		</button>
	{/if}

	{#if etapas}
		<LinhaDeMetro {etapas} rodando={ocupado ? (aoVivo?.etapa ?? null) : null} {ocupado} aoRodar={(e, o) => rodar(e, o)} {aoSortear} />
	{:else}
		<p class="suave" role="status">Carregando as etapas…</p>
	{/if}

	{#if aoVivo}
		<JobAoVivo
			job={aoVivo}
			rotulo={rotuloJob(aoVivo)}
			aoCancelar={() => aoVivo && fonte.cancelarJob(aoVivo.id)}
			aoRecarregar={() => location.reload()}
		/>
	{/if}

	<div class="lado-a-lado">
		<section class="bloco" aria-labelledby="titulo-estimativa">
			<h2 id="titulo-estimativa">Classificação</h2>
			{#if estimativa}
				<p data-testid="estimativa">
					{formatarInteiro(estimativa.classificados)} de {formatarInteiro(estimativa.documentos)} documentos com resumo
					classificados por <code>{estimativa.modelo}</code>.
					{#if estimativa.pendentes && estimativa.estimativa_s !== null}
						Faltam {formatarInteiro(estimativa.pendentes)}, cerca de <strong>{formatarDuracao(estimativa.estimativa_s)}</strong>
						neste computador.
					{:else if estimativa.pendentes}
						Faltam {formatarInteiro(estimativa.pendentes)}: use "Estimar o tempo" para medir quanto isso leva aqui.
					{/if}
				</p>
			{/if}
		</section>

		<section class="bloco" aria-labelledby="titulo-modelos" data-testid="modelos">
			<h2 id="titulo-modelos">Modelos</h2>
			{#if modelos}
				{#if !modelos.ollama.no_ar}
					<p class="aviso">{modelos.ollama.erro}</p>
				{/if}
				<ul>
					{#each Object.entries(modelos.projeto) as [papel, m] (papel)}
						<li>
							<span class="papel">{PAPEIS[papel as keyof typeof PAPEIS]}</span>
							<code>{m.modelo}</code>
							{#if m.instalado}
								<span class="ok">instalado</span>
							{:else}
								<button type="button" disabled={ocupado || !modelos.ollama.no_ar} onclick={() => rodar('modelo', { modelo: m.modelo })} data-testid="baixar-{papel}">
									Baixar{m.download_gb ? ` (${gb(m.download_gb)})` : ''}
								</button>
							{/if}
						</li>
					{/each}
				</ul>
				<p class="suave">
					{gb(modelos.ram_gb)} de memória; perfil sugerido: {PERFIS[modelos.perfil_sugerido] ?? modelos.perfil_sugerido}.
					{#if faltando.length}Os modelos que faltam precisam ser baixados antes das etapas que os usam.{/if}
				</p>
			{:else}
				<p class="suave">Carregando os modelos…</p>
			{/if}
		</section>
	</div>

	{#if historico.length}
		<section class="bloco" aria-labelledby="titulo-historico">
			<h2 id="titulo-historico">Últimas execuções</h2>
			<ol class="historico" data-testid="historico">
				{#each historico.slice(0, 6) as j (j.id)}
					<li>
						<span>{NOMES[j.etapa] ?? j.etapa}</span>
						<span class="suave">{formatarData(j.criado)}</span>
						<span class="estado-{j.estado}">{ESTADOS[j.estado]}</span>
						{#if j.resumo?.frase}<span class="suave frase">{j.resumo.frase}</span>{/if}
						{#if j.erro}<span class="suave frase">{j.erro}</span>{/if}
					</li>
				{/each}
			</ol>
		</section>
	{/if}
</div>

<style>
	.vista {
		display: grid;
		gap: 1.8rem;
	}

	.cabecalho {
		display: grid;
		gap: 0.5rem;
	}

	h1 {
		margin: 0;
		font-size: clamp(2.2rem, 4.5vw, 3.2rem);
		font-weight: 380;
	}

	h2 {
		margin: 0 0 0.5rem;
		font-size: 1.05rem;
		font-weight: 500;
	}

	.lide {
		max-width: 60rem;
		margin: 0;
		color: var(--texto-suave);
	}

	.aviso {
		margin: 0;
		color: var(--acento);
	}

	.suave {
		color: var(--texto-suave);
		font-size: 0.85rem;
	}

	.configurar {
		justify-self: start;
		padding: 0.4rem 0.9rem;
		border: 1px solid var(--linha-forte);
		border-radius: var(--raio-pequeno);
		background: none;
		color: var(--texto);
		font: inherit;
		cursor: pointer;
	}

	.configurar:disabled {
		opacity: 0.45;
	}

	.ok-salvo {
		margin: 0;
		color: var(--texto-suave);
	}

	.lado-a-lado {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
		gap: 1.5rem;
	}

	.bloco p {
		margin: 0.3rem 0;
	}

	.bloco ul {
		display: grid;
		gap: 0.35rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.bloco li {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		align-items: baseline;
		font-size: 0.9rem;
	}

	.papel {
		min-width: 7rem;
		color: var(--texto-suave);
	}

	.ok {
		color: var(--texto-suave);
		font-size: 0.8rem;
	}

	.bloco button {
		padding: 0.15rem 0.6rem;
		border: 1px solid var(--acento);
		border-radius: var(--raio-pequeno);
		background: none;
		color: var(--acento);
		font: inherit;
		font-size: 0.8rem;
		cursor: pointer;
	}

	.bloco button:disabled {
		opacity: 0.45;
		cursor: default;
	}

	.historico {
		display: grid;
		gap: 0.3rem;
		margin: 0;
		padding-left: 1.2rem;
		font-size: 0.88rem;
	}

	.historico li {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem;
	}

	.frase {
		flex-basis: 100%;
	}

	.estado-falhou,
	.estado-cancelado {
		color: var(--texto-suave);
	}

	@media (max-width: 900px) {
		.lado-a-lado {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
