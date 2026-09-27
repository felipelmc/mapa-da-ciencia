<script lang="ts" module>
	import type { Evidencia } from '$lib/contrato/tipos';
	import { posicoesJs } from './posicoes';

	/** Quantos caracteres de contexto mostrar antes e depois do trecho. */
	export const CONTEXTO = 110;

	export interface PartesDoTrecho {
		antes: string;
		marcado: string;
		depois: string;
		cortadoAntes: boolean;
		cortadoDepois: boolean;
	}

	/** O trecho da evidência dentro do texto, com um pouco de contexto (cortado em espaços, sem partir palavras). */
	export function partesDoTrecho(texto: string, e: Pick<Evidencia, 'inicio' | 'fim'>, contexto = CONTEXTO): PartesDoTrecho | null {
		const { inicio, fim } = posicoesJs(texto, e);
		if (inicio == null || fim == null || inicio < 0 || fim > texto.length || fim <= inicio) return null;
		let a = Math.max(0, inicio - contexto);
		let b = Math.min(texto.length, fim + contexto);
		if (a > 0) a = texto.indexOf(' ', a) + 1 || a;
		if (b < texto.length) b = texto.lastIndexOf(' ', b) > fim ? texto.lastIndexOf(' ', b) : b;
		return {
			antes: texto.slice(a, inicio),
			marcado: texto.slice(inicio, fim),
			depois: texto.slice(fim, b),
			cortadoAntes: a > 0,
			cortadoDepois: b < texto.length
		};
	}
</script>

<script lang="ts">
	/**
	 * A evidência de uma resposta do modelo, lida no texto: o trecho marcado dentro do resumo (ou do título), com
	 * contexto. Quando o trecho não foi localizado, mostra o que o modelo citou, com o aviso; numa resposta "sem
	 * informação", diz que não havia trecho a citar. Sem licença para mostrar o resumo, fica só a citação.
	 */
	let {
		evidencia,
		resumo,
		titulo,
		completo = false
	}: {
		evidencia: Evidencia;
		resumo: string | null;
		titulo?: string;
		/** Mostra o resumo inteiro com o trecho marcado, em vez de só o contexto. */
		completo?: boolean;
	} = $props();

	const texto = $derived(evidencia.campo === 'titulo' ? (titulo ?? null) : resumo);
	const partes = $derived(
		texto && evidencia.status !== 'ausente' ? partesDoTrecho(texto, evidencia, completo ? Infinity : CONTEXTO) : null
	);
	const AVISOS: Record<string, string> = {
		aproximada: 'trecho quase igual ao do resumo',
		ausente: 'trecho não encontrado no resumo'
	};
</script>

<blockquote class="trecho" data-status={evidencia.status} data-testid="trecho">
	{#if evidencia.status === 'dispensada'}
		<p class="suave">Sem trecho: o modelo respondeu que o resumo não informa.</p>
	{:else if partes}
		{#if evidencia.campo === 'titulo'}<span class="onde">No título:</span>{/if}
		<p>
			{#if partes.cortadoAntes}…{/if}{partes.antes}<mark>{partes.marcado}</mark>{partes.depois}{#if partes.cortadoDepois}…{/if}
		</p>
	{:else}
		<p>«{evidencia.evidencia}»</p>
	{/if}
	{#if AVISOS[evidencia.status]}<span class="selo-status">{AVISOS[evidencia.status]}</span>{/if}
</blockquote>

<style>
	.trecho {
		margin: 0;
		padding: 0.1rem 0 0.1rem 0.75rem;
		border-left: 2px solid var(--linha-forte);
		font-size: 0.9rem;
		line-height: 1.5;
		color: var(--texto-suave);
	}

	.trecho p {
		margin: 0;
	}

	mark {
		background: var(--acento-suave);
		color: var(--texto);
		padding: 0 0.1em;
		border-radius: 2px;
	}

	.onde {
		font-size: 0.78rem;
		color: var(--texto-fraco);
	}

	.suave {
		color: var(--texto-fraco);
	}

	.selo-status {
		display: inline-block;
		margin-top: 0.25rem;
		font-size: 0.75rem;
		color: var(--texto-fraco);
	}

	.trecho[data-status='ausente'] {
		border-left-style: dashed;
	}
</style>
