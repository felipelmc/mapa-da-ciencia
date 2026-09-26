<script lang="ts">
	/**
	 * O job em andamento (ou o último que terminou): a parte da etapa, a barra de progresso, as mensagens mais
	 * recentes e o botão de cancelar. Quando termina, mostra o resumo (ou o erro) e o botão para recarregar o
	 * painel com os dados novos.
	 */
	import { formatarInteiro, formatarPorcentagem } from '$lib/formato';
	import { fracao, type JobAoVivo } from './job';

	let {
		job,
		rotulo,
		aoCancelar,
		aoRecarregar
	}: { job: JobAoVivo; rotulo: string; aoCancelar: () => void; aoRecarregar: () => void } = $props();

	const f = $derived(fracao(job));
	const ESTADOS = {
		na_fila: 'Na fila',
		rodando: 'Rodando',
		concluido: 'Concluído',
		falhou: 'Falhou',
		cancelado: 'Cancelado'
	} as const;
</script>

<section class="job" data-estado={job.estado} aria-labelledby="titulo-job" data-testid="job-ao-vivo">
	<header>
		<h2 id="titulo-job">{rotulo}</h2>
		<span class="selo" data-testid="estado-job">{ESTADOS[job.estado]}</span>
	</header>

	{#if job.passo}
		<p class="passo" data-testid="passo-job">
			{job.passo}{#if job.total}: {formatarInteiro(job.feito)} de {formatarInteiro(job.total)}{#if f !== null}{' '}({formatarPorcentagem(f)}){/if}{/if}
		</p>
	{/if}
	{#if !job.terminado}
		{#if f !== null}
			<progress max="1" value={f} aria-label="Progresso da etapa"></progress>
		{:else}
			<progress aria-label="Progresso da etapa"></progress>
		{/if}
	{/if}

	{#if job.mensagens.length}
		<ol class="mensagens" aria-live="polite" data-testid="mensagens-job">
			{#each job.mensagens.slice(-8) as m, i (i)}<li>{m}</li>{/each}
		</ol>
	{/if}

	{#if job.erro}<p class="erro" role="alert">{job.erro}</p>{/if}
	{#if job.resumo}<p class="resumo" data-testid="resumo-job">{job.resumo}</p>{/if}

	<div class="acoes">
		{#if !job.terminado}
			<button type="button" onclick={aoCancelar} data-testid="cancelar-job">Cancelar</button>
		{:else if job.estado === 'concluido'}
			<button type="button" class="principal" onclick={aoRecarregar} data-testid="recarregar">Ver os dados novos</button>
		{/if}
	</div>
</section>

<style>
	.job {
		display: grid;
		gap: 0.6rem;
		padding: 1rem 1.2rem;
		border: 1px solid var(--linha);
		border-left: 3px solid var(--acento);
		border-radius: var(--raio);
		background: var(--superficie);
	}

	.job[data-estado='falhou'] {
		border-left-color: var(--texto-fraco);
	}

	header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 1rem;
	}

	h2 {
		margin: 0;
		font-size: 1.1rem;
		font-weight: 500;
	}

	.selo {
		font-family: var(--fonte-mono);
		font-size: 0.78rem;
		color: var(--texto-suave);
	}

	.passo,
	.resumo {
		margin: 0;
		font-size: 0.9rem;
	}

	progress {
		width: 100%;
		accent-color: var(--acento);
	}

	.mensagens {
		max-height: 10rem;
		margin: 0;
		padding: 0.5rem 0.7rem 0.5rem 1.8rem;
		overflow-y: auto;
		border-radius: var(--raio-pequeno);
		background: var(--fundo);
		font-family: var(--fonte-mono);
		font-size: 0.76rem;
		color: var(--texto-suave);
	}

	.erro {
		margin: 0;
		color: var(--acento);
	}

	.acoes {
		display: flex;
		gap: 0.5rem;
	}

	.acoes button {
		padding: 0.3rem 0.8rem;
		border: 1px solid var(--linha-forte);
		border-radius: var(--raio-pequeno);
		background: none;
		color: var(--texto);
		font: inherit;
		font-size: 0.86rem;
		cursor: pointer;
	}

	.acoes .principal {
		border-color: var(--acento);
		background: var(--acento);
		color: var(--sobre-acento);
	}
</style>
