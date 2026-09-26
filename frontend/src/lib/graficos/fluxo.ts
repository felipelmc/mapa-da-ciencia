/**
 * Empilhamento das séries (tópicos ou macrotemas por ano) para o fluxo da vista Tópicos, com o d3-shape.
 *
 * Três modos, com a mesma ordem das faixas (para a transição entre eles não embaralhar as cores):
 *
 * - `fluxo`: linha de base ondulada (`stackOffsetWiggle`), que minimiza o balanço das faixas; a espessura é o
 *   número de documentos, mas o eixo vertical não tem zero fixo;
 * - `absoluto`: empilhado a partir do zero, em documentos;
 * - `proporcao`: cada ano soma 100% (`stackOffsetExpand`); anos sem documentos ficam vazios.
 *
 * A ordem vem de `ordemDentroFora` (as maiores séries no meio, alternando para fora), calculada uma vez sobre o
 * corpus inteiro e reaproveitada com qualquer filtro. A curva é `curveMonotoneX`: passa pelos pontos, sem
 * inventar picos entre os anos.
 */
import {
	area,
	curveMonotoneX,
	stack,
	stackOffsetExpand,
	stackOffsetNone,
	stackOffsetWiggle,
	stackOrderInsideOut,
	stackOrderNone
} from 'd3-shape';

export type ModoFluxo = 'fluxo' | 'absoluto' | 'proporcao';

export interface SerieEmpilhada {
	id: number;
	/** Base e topo de cada ano, na unidade do modo (documentos ou fração do ano). */
	y0: Float64Array;
	y1: Float64Array;
}

export interface Empilhado {
	series: SerieEmpilhada[];
	dominio: [number, number];
}

type Linha = Record<number, number>;

function linhas(matriz: ArrayLike<number>[], nAnos: number): Linha[] {
	return Array.from({ length: nAnos }, (_, j) => Object.fromEntries(matriz.map((s, k) => [k, s[j]])));
}

/**
 * Ordem das séries "de dentro para fora": índices em `matriz`, na ordem de baixo para cima. As séries em
 * `fixasNoFim` (ex.: "sem tópico") ficam sempre por último, no topo.
 */
export function ordemDentroFora(matriz: ArrayLike<number>[], fixasNoFim: number[] = []): number[] {
	const nAnos = matriz[0]?.length ?? 0;
	const livres = matriz.map((_, k) => k).filter((k) => !fixasNoFim.includes(k));
	const series = stack<Linha, number>()
		.keys(livres)
		.order(stackOrderInsideOut)
		.value((d, k) => d[k])(linhas(matriz, nAnos));
	const ordem = [...series].sort((a, b) => a.index - b.index).map((s) => s.key);
	return [...ordem, ...fixasNoFim];
}

/** Empilha `matriz` (uma série por linha, uma coluna por ano) na ordem dada. */
export function empilhar(
	matriz: ArrayLike<number>[],
	ids: number[],
	modo: ModoFluxo,
	ordem: number[] = matriz.map((_, k) => k)
): Empilhado {
	const nAnos = matriz[0]?.length ?? 0;
	const offset = modo === 'fluxo' ? stackOffsetWiggle : modo === 'proporcao' ? stackOffsetExpand : stackOffsetNone;
	const series = stack<Linha, number>()
		.keys(ordem)
		.order(stackOrderNone)
		.offset(offset)
		.value((d, k) => d[k])(linhas(matriz, nAnos));
	let min = Infinity;
	let max = -Infinity;
	const saida = series.map((s) => {
		const y0 = new Float64Array(nAnos);
		const y1 = new Float64Array(nAnos);
		s.forEach(([a, b], j) => {
			y0[j] = Number.isFinite(a) ? a : 0;
			y1[j] = Number.isFinite(b) ? b : 0;
			min = Math.min(min, y0[j]);
			max = Math.max(max, y1[j]);
		});
		return { id: ids[s.key], y0, y1 };
	});
	if (!Number.isFinite(min)) [min, max] = [0, 1];
	if (modo !== 'fluxo') min = 0;
	if (modo === 'proporcao') max = 1;
	return { series: saida, dominio: [min, max === min ? min + 1 : max] };
}

/** O caminho SVG de uma faixa, com `x(j)` e `y(valor)` em pixels. */
export function caminho(serie: SerieEmpilhada, x: (j: number) => number, y: (v: number) => number): string {
	return (
		area<number>()
			.x((j) => x(j))
			.y0((j) => y(serie.y0[j]))
			.y1((j) => y(serie.y1[j]))
			.curve(curveMonotoneX)(Array.from(serie.y0, (_, j) => j)) ?? ''
	);
}
