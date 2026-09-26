/** Formatação de números e datas em português do Brasil. */

const inteiro = new Intl.NumberFormat('pt-BR');
const porcentagem = new Intl.NumberFormat('pt-BR', { style: 'percent', maximumFractionDigits: 0 });
const data = new Intl.DateTimeFormat('pt-BR', { day: 'numeric', month: 'short', year: 'numeric' });

/** `1500` → `1.500`. */
export const formatarInteiro = (n: number): string => inteiro.format(n);

/** `0.4213` → `42%`. */
export const formatarPorcentagem = (fracao: number): string => porcentagem.format(fracao);

/** `[2010, 2025]` → `2010–2025`; um ano só → `2015`. */
export function formatarPeriodo([inicio, fim]: readonly [number, number]): string {
	return inicio === fim ? `${inicio}` : `${inicio}–${fim}`;
}

/** Data ISO → `26 de set. de 2026`. Devolve o texto original se não for uma data. */
export function formatarData(iso: string): string {
	const d = new Date(iso);
	return Number.isNaN(d.getTime()) ? iso : data.format(d);
}

/** `1` → `1 documento`; `2` → `2 documentos` (com o número formatado). */
export function contar(n: number, singular: string, plural = `${singular}s`): string {
	return `${formatarInteiro(n)} ${n === 1 ? singular : plural}`;
}
