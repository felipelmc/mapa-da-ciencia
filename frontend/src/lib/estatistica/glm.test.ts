import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import type { Topicos } from '$lib/contrato/tipos';
import { ajustados, tendencia } from './glm';

const raiz = join(import.meta.dirname, '../../../../contrato');
const casos = JSON.parse(readFileSync(join(raiz, 'casos/tendencia.json'), 'utf8')) as {
	nome: string;
	entrada: { n: number[]; total: number[]; anos: number[]; dispersao: 'quase' | 'binomial' };
	saida: Record<string, unknown>;
}[];
const topicos = JSON.parse(readFileSync(join(raiz, 'exemplo/dados/topicos.json'), 'utf8')) as Topicos;

function comparar(obtido: ReturnType<typeof tendencia>, esperado: Record<string, unknown>) {
	expect(obtido.direcao).toBe(esperado.direcao);
	expect(obtido.motivo).toBe(esperado.motivo);
	expect(obtido.anos).toEqual(esperado.anos);
	for (const campo of ['inclinacao', 'erro_padrao', 'dispersao', 'prop_inicio', 'prop_fim', 'pp_periodo', 'pp_por_ano'] as const) {
		const e = esperado[campo] as number | null;
		if (e === null) expect(obtido[campo]).toBeNull();
		else expect(obtido[campo]).toBeCloseTo(e, 5);
	}
	const ic = esperado.ic95 as [number, number] | null;
	if (ic) {
		expect(obtido.ic95![0]).toBeCloseTo(ic[0], 5);
		expect(obtido.ic95![1]).toBeCloseTo(ic[1], 5);
	} else expect(obtido.ic95).toBeNull();
}

describe('tendência no navegador = referência em Python', () => {
	for (const c of casos) {
		it(`caso ${c.nome}`, () => {
			const { n, total, anos, dispersao } = c.entrada;
			comparar(tendencia(n, total, anos, { dispersao }), c.saida);
		});
	}

	it('bate com o gabarito do topicos.json do exemplo, tópico a tópico e macrotema a macrotema', () => {
		const metodo = topicos.metodo_tendencia ?? {};
		for (const t of [...topicos.topicos, ...topicos.macrotemas]) {
			if (!t.tendencia || !t.serie) continue;
			const obtido = tendencia(t.serie.n, topicos.total_por_ano, topicos.anos, metodo);
			// o gabarito é arredondado em 6 casas
			expect(obtido.direcao).toBe(t.tendencia.direcao);
			if (t.tendencia.pp_periodo !== null && t.tendencia.pp_periodo !== undefined)
				expect(obtido.pp_periodo!).toBeCloseTo(t.tendencia.pp_periodo, 4);
			if (t.tendencia.inclinacao !== null && t.tendencia.inclinacao !== undefined)
				expect(obtido.inclinacao!).toBeCloseTo(t.tendencia.inclinacao, 5);
		}
	});

	it('as participações ajustadas vão de prop_inicio a prop_fim', () => {
		const c = casos.find((x) => x.nome === 'subida')!;
		const t = tendencia(c.entrada.n, c.entrada.total, c.entrada.anos);
		const curva = ajustados(t, c.entrada.anos)!;
		expect(curva[0]).toBeCloseTo(t.prop_inicio!, 9);
		expect(curva[curva.length - 1]).toBeCloseTo(t.prop_fim!, 9);
		expect(ajustados(tendencia([1, 2], [10, 10], [2010, 2011]), [2010, 2011])).toBeNull();
	});
});
