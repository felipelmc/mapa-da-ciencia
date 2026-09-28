<script lang="ts" module>
	import type { DecisaoJuri } from '$lib/contrato/tipos';

	export const ETAPAS: Record<DecisaoJuri['etapa'], string> = {
		unanime: 'unânime',
		maioria: 'por maioria',
		deliberacao: 'na deliberação',
		sem_maioria: 'sem maioria'
	};
</script>

<script lang="ts">
	/**
	 * Como o júri de modelos locais decidiu cada variável deste documento (só nos documentos da amostra de validação):
	 * o estágio da decisão, o voto de cada membro com o trecho que ele citou (e a mudança na deliberação) e o que valeu:
	 * a decisão do júri, a escolha do supervisor com a justificativa ou, sem maioria e sem supervisor, o voto do
	 * primeiro membro. Fica recolhido: é o bastidor da classificação, e não a classificação.
	 */
	import type { CodebookContrato } from '$lib/contrato/tipos';

	let { juri, codebook }: { juri: Record<string, DecisaoJuri>; codebook: CodebookContrato | null } = $props();

	const ordem = $derived(
		codebook ? codebook.variaveis.map((v) => v.id).filter((id) => id in juri) : Object.keys(juri)
	);
	const membros = $derived([...new Set(Object.values(juri).flatMap((d) => (d.votos ?? []).map((v) => v.membro)))]);

	function nome(id: string): string {
		return codebook?.variaveis.find((v) => v.id === id)?.rotulo ?? id.replaceAll('_', ' ');
	}
	function valor(id: string, x: DecisaoJuri['valor']): string {
		const v = codebook?.variaveis.find((c) => c.id === id);
		const rotulo = (c: string) => v?.categorias?.find((k) => k.valor === c)?.rotulo ?? c.replaceAll('_', ' ');
		if (typeof x === 'boolean') return x ? 'Sim' : 'Não';
		if (Array.isArray(x)) return x.map(rotulo).join(' + ') || 'nenhuma';
		return x === null ? '—' : v?.tipo === 'texto' ? x : rotulo(x);
	}
	const mudancas = $derived(Object.values(juri).some((d) => (d.votos ?? []).some((v) => v.revisou)));

	function votos(d: DecisaoJuri, membro: string) {
		const r1 = (d.votos ?? []).find((v) => v.membro === membro && v.rodada === 1);
		const r2 = (d.votos ?? []).find((v) => v.membro === membro && v.rodada === 2);
		return { r1, r2 };
	}
</script>

<details class="juri" data-testid="votos-do-juri">
	<summary>
		<span class="rotulo-miudo">Júri de modelos</span>
		<span class="suave">{membros.length} membros, na amostra de validação</span>
	</summary>
	{#if mudancas}
		<p class="legenda suave">A seta (→) mostra o voto mudado na deliberação.</p>
	{/if}
	<ul>
		{#each ordem as id (id)}
			{@const d = juri[id]}
			<li data-testid="decisao-juri">
				<p class="cabeca">
					<span class="nome">{nome(id)}</span>
					<span class="etapa etapa--{d.etapa}">{ETAPAS[d.etapa]}{#if d.supervisor}, supervisor{/if}</span>
				</p>
				<ul class="votos">
					{#each membros as membro (membro)}
						{@const v = votos(d, membro)}
						{#if v.r1}
							{@const final = v.r2?.revisou ? v.r2 : v.r1}
							<li>
								<span class="membro">{membro}</span>
								<span>
									{valor(id, v.r1.valor)}
									{#if v.r2?.revisou}<span class="mudou" data-testid="mudou-na-deliberacao"
											><span aria-hidden="true">→</span><span class="visualmente-oculto">, mudou na deliberação para</span>
											{valor(id, v.r2.valor)}</span
										>{/if}
									{#if final.evidencia}<q class="trecho">{final.evidencia}</q>{/if}
								</span>
							</li>
						{/if}
					{/each}
					{#if d.supervisor}
						<li class="decisao supervisor">
							<span class="membro">{d.supervisor}</span>
							<span>
								{valor(id, d.valor)}
								{#if d.justificativa}<span class="nota">{d.justificativa}</span>{/if}
							</span>
						</li>
					{:else if d.etapa === 'sem_maioria'}
						<li class="decisao" data-testid="valeu-presidente">
							<span class="membro">valeu</span>
							<span>
								{valor(id, d.valor_sem_supervisor)}
								<span class="nota"
									>{codebook?.variaveis.find((v) => v.id === id)?.tipo === 'texto'
										? 'o voto do primeiro membro (texto livre não vai ao supervisor)'
										: 'o voto do primeiro membro, até o supervisor decidir'}</span
								>
							</span>
						</li>
					{:else}
						<li class="decisao">
							<span class="membro">decisão</span>
							<span>{valor(id, d.valor)}</span>
						</li>
					{/if}
				</ul>
			</li>
		{/each}
	</ul>
</details>

<style>
	.juri {
		border-top: 1px solid var(--linha);
		padding-top: 0.4rem;
		font-size: 0.8rem;
	}

	summary {
		display: flex;
		gap: 0.5rem;
		align-items: baseline;
		cursor: pointer;
	}

	.suave,
	.nota {
		color: var(--texto-suave);
	}

	ul {
		margin: 0.3rem 0 0;
		padding: 0;
		list-style: none;
		display: grid;
		gap: 0.35rem;
	}

	.cabeca {
		display: flex;
		justify-content: space-between;
		gap: 0.5rem;
		margin: 0;
	}

	.nome {
		color: var(--texto-suave);
	}

	.etapa {
		font-size: 0.72rem;
		color: var(--texto-suave);
	}

	.etapa--sem_maioria,
	.etapa--deliberacao {
		color: var(--texto);
	}

	.votos {
		gap: 0.1rem;
		margin: 0.1rem 0 0 0.6rem;
	}

	.votos li {
		display: grid;
		grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
		gap: 0.5rem;
	}

	.membro {
		font-family: var(--fonte-mono);
		font-size: 0.72rem;
		color: var(--texto-suave);
		overflow-wrap: anywhere;
	}

	.mudou {
		color: var(--acento);
	}

	.decisao {
		border-top: 1px dashed var(--linha);
		padding-top: 0.1rem;
	}

	.decisao .membro {
		color: var(--texto-suave);
	}

	.legenda {
		margin: 0.3rem 0 0;
		font-size: 0.72rem;
	}

	.trecho {
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
		font-size: 0.72rem;
		color: var(--texto-suave);
	}

	.nota {
		display: block;
		font-size: 0.72rem;
	}
</style>
