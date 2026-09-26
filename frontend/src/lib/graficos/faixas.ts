/**
 * Rótulos dentro das faixas do fluxo: para cada faixa, o lugar onde o texto cabe com mais folga. Uma faixa fina
 * demais fica sem rótulo (a legenda e a dica cobrem). Nada é recalculado durante o play.
 */
import type { SerieEmpilhada } from './fluxo';

export interface RotuloFaixa {
	id: number;
	x: number;
	y: number;
	texto: string;
}

/** Valor da série na coluna fracionária `t` (interpolação linear entre os anos). */
function em(v: Float64Array, t: number): number {
	const i = Math.max(0, Math.min(v.length - 1, Math.floor(t)));
	const j = Math.min(v.length - 1, i + 1);
	const f = t - i;
	return v[i] * (1 - f) + v[j] * f;
}

export function rotularFaixas(
	series: SerieEmpilhada[],
	textos: Map<number, string>,
	x: (coluna: number) => number,
	y: (valor: number) => number,
	medir: (texto: string) => number,
	{ fonte = 12, folga = 4, amostras = 9 }: { fonte?: number; folga?: number; amostras?: number } = {}
): RotuloFaixa[] {
	const saida: RotuloFaixa[] = [];
	const nAnos = series[0]?.y0.length ?? 0;
	if (nAnos < 2) return saida;
	const larguraColuna = x(1) - x(0);
	for (const s of series) {
		const texto = textos.get(s.id);
		if (!texto) continue;
		const w = medir(texto) + 2 * folga;
		const meio = w / 2 / larguraColuna; // meia largura do texto, em colunas
		let melhor: { t: number; espaco: number; centro: number } | null = null;
		for (let passo = 0; passo <= (nAnos - 1) * 4; passo += 1) {
			const t = passo / 4;
			if (t - meio < 0 || t + meio > nAnos - 1) continue;
			let espaco = Infinity;
			let soma = 0;
			for (let k = 0; k < amostras; k += 1) {
				const u = t - meio + (2 * meio * k) / (amostras - 1);
				const topo = y(em(s.y1, u));
				const base = y(em(s.y0, u));
				espaco = Math.min(espaco, base - topo);
				soma += (base + topo) / 2;
			}
			if (!melhor || espaco > melhor.espaco) melhor = { t, espaco, centro: soma / amostras };
		}
		if (melhor && melhor.espaco >= fonte * 1.2) saida.push({ id: s.id, x: x(melhor.t), y: melhor.centro, texto });
	}
	return saida;
}
