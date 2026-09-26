/**
 * O projeto aberto, compartilhado com as páginas por contexto do Svelte.
 *
 * O layout raiz lê o manifesto (e as revistas, para a barra superior) antes de mostrar
 * qualquer página; daí em diante, cada página pede à fonte só o que usa.
 */
import { createContext } from 'svelte';
import type { Manifesto, Revistas } from '$lib/contrato/tipos';
import { abrirFonte, type OpcoesFonte } from './index';
import type { FonteDeDados } from './fonte';

export interface ProjetoAberto {
	fonte: FonteDeDados;
	manifesto: Manifesto;
	/** `null` se o projeto ainda não tem `revistas.json`. */
	revistas: Revistas | null;
	/** O exemplo sintético do repositório (dados fictícios), pela descrição do manifesto. */
	ehExemplo: boolean;
}

export async function abrirProjeto(opcoes: OpcoesFonte = {}): Promise<ProjetoAberto> {
	const { fonte, manifesto } = await abrirFonte(opcoes);
	const revistas = await fonte.revistas();
	return { fonte, manifesto, revistas, ehExemplo: ehExemploSintetico(manifesto) };
}

/** O gerador do exemplo escreve "Dados FICTÍCIOS…" na descrição do projeto. */
export function ehExemploSintetico(manifesto: Pick<Manifesto, 'projeto'>): boolean {
	return /fict[ií]ci/i.test(manifesto.projeto.descricao ?? '');
}

/** `usarProjeto()` nas páginas; `definirProjeto()` só no layout raiz. */
export const [usarProjeto, definirProjeto] = createContext<ProjetoAberto>();
