/**
 * A lógica de uma ficha de codificação, sem interface: as opções de cada variável (numeradas para o teclado),
 * escolher uma opção, o que falta responder e onde retomar a fila.
 */
import type { CodebookContrato, VariavelContrato } from '$lib/contrato/tipos';
import type { Ficha, RespostaVariavel, Valor } from './api';

export interface Opcao {
	valor: string | boolean;
	rotulo: string;
	definicao: string;
}

/** As opções que as teclas 1–9 escolhem. Booleana: 1 = Sim, 2 = Não. Texto: nenhuma (a resposta é digitada). */
export function opcoesDe(v: VariavelContrato): Opcao[] {
	if (v.tipo === 'booleana')
		return [
			{ valor: true, rotulo: 'Sim', definicao: '' },
			{ valor: false, rotulo: 'Não', definicao: '' }
		];
	if (v.tipo === 'texto') return [];
	return (v.categorias ?? []).map((c) => ({ valor: c.valor, rotulo: c.rotulo || c.valor, definicao: c.definicao }));
}

export const RESPOSTA_VAZIA: RespostaVariavel = { valor: null, evidencia: '', incerto: false, nota: '' };

/** A resposta com a opção `n` (0 = a primeira) escolhida. Múltipla: liga ou desliga a categoria. */
export function escolher(v: VariavelContrato, atual: RespostaVariavel | undefined, n: number): RespostaVariavel {
	const base = atual ?? RESPOSTA_VAZIA;
	const opcao = opcoesDe(v)[n];
	if (!opcao) return base;
	if (v.tipo === 'multipla') {
		const lista = Array.isArray(base.valor) ? base.valor : [];
		const c = opcao.valor as string;
		const nova = lista.includes(c) ? lista.filter((x) => x !== c) : [...lista, c];
		return { ...base, valor: nova };
	}
	return { ...base, valor: opcao.valor };
}

export function respondida(v: VariavelContrato, r: RespostaVariavel | undefined): boolean {
	const valor: Valor | undefined = r?.valor;
	if (valor === null || valor === undefined) return false;
	if (v.tipo === 'texto') return typeof valor === 'string' && valor.trim() !== '';
	if (v.tipo === 'multipla') return Array.isArray(valor);
	return true;
}

/** Os ids das variáveis ainda sem resposta, na ordem do codebook. */
export function faltando(codebook: CodebookContrato, respostas: Record<string, RespostaVariavel>): string[] {
	return codebook.variaveis.filter((v) => !respondida(v, respostas[v.id])).map((v) => v.id);
}

/**
 * O que vai para a API: as variáveis respondidas e, com o valor nulo, as que a pessoa tocou mas deixou sem resposta
 * (um texto apagado, uma marca antes do valor): o painel apaga a resposta antiga delas, em vez de ela voltar no reload.
 */
export function paraGravar(
	codebook: CodebookContrato,
	respostas: Record<string, RespostaVariavel>
): Record<string, RespostaVariavel> {
	return Object.fromEntries(
		codebook.variaveis
			.filter((v) => respostas[v.id] !== undefined)
			.map((v) => [v.id, respondida(v, respostas[v.id]) ? respostas[v.id] : { ...respostas[v.id], valor: null }])
	);
}

/** Onde retomar: a primeira ficha incompleta (ou a última, se todas estiverem completas). */
export function ondeRetomar(fila: Pick<Ficha, 'completa'>[]): number {
	const i = fila.findIndex((f) => !f.completa);
	return i >= 0 ? i : Math.max(0, fila.length - 1);
}
