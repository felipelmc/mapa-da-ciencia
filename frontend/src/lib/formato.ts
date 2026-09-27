/** Formatação de números e datas em português do Brasil. */

const inteiro = new Intl.NumberFormat('pt-BR');
const porcentagem = new Intl.NumberFormat('pt-BR', { style: 'percent', maximumFractionDigits: 0 });
const porcentagemDecimal = new Intl.NumberFormat('pt-BR', { style: 'percent', maximumFractionDigits: 1 });
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

/** `400.7499` → `400,7` (casas decimais fixas). */
export function formatarDecimal(n: number, casas = 1): string {
	return n.toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas });
}

/** `0.0421` → `4,2%`. */
export const formatarPorcentagemDecimal = (fracao: number): string => porcentagemDecimal.format(fracao);

/** Pontos percentuais com sinal: `0.31` → `+0,31 p.p.`; `-1.2` → `−1,20 p.p.` (com o sinal de menos tipográfico). */
export function formatarPp(v: number, casas = 2): string {
	const texto = formatarDecimal(Math.abs(v), casas);
	return `${v > 0 ? '+' : v < 0 ? '\u2212' : ''}${texto} p.p.`;
}

/** Duração em segundos → `45 s`, `3 min`, `2 h 10 min`. */
export function formatarDuracao(segundos: number): string {
	if (segundos < 90) return `${Math.round(segundos)} s`;
	const minutos = Math.round(segundos / 60);
	if (minutos < 90) return `${minutos} min`;
	const h = Math.floor(minutos / 60);
	const m = minutos % 60;
	return m ? `${h} h ${m} min` : `${h} h`;
}
