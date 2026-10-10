import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import type { MetricaVariavel, Validacao } from '$lib/contrato/tipos';
import { celulaSubconjunto, colunasSubconjuntos, composicaoDaAmostra } from './subconjuntos';

const raiz = join(import.meta.dirname, '../../../../contrato/exemplo/dados');
const validacao = JSON.parse(readFileSync(join(raiz, 'validacao.json'), 'utf8')) as Validacao;
const doPar = validacao.metricas.filter((m) => m.comparado === 'exemplo');

describe('subconjuntos da validação', () => {
	it('as colunas: os idiomas e as respostas informativas', () => {
		expect(colunasSubconjuntos(doPar).map((c) => c.rotulo)).toEqual(['Português', 'Inglês', 'Respostas informativas']);
	});

	it('as células: kappa e n, "—" abaixo do mínimo, e "não se aplica" onde o subconjunto não existe', () => {
		const abordagem = doPar.find((m) => m.variavel === 'abordagem')!;
		const pt = abordagem.subconjuntos!.find((s) => s.idioma === 'pt')!;
		expect(celulaSubconjunto(abordagem, 'idioma:pt')).toBe(`${pt.kappa!.toFixed(2).replace('.', ',')} (${pt.n})`);
		expect(celulaSubconjunto(abordagem, 'idioma:en')).toBe('— (18)');
		const booleana = doPar.find((m) => m.variavel === 'brasil_como_caso')!;
		expect(celulaSubconjunto(booleana, 'informativas:')).toBe('não se aplica');
		expect(celulaSubconjunto(abordagem, null)).toMatch(/^\d,\d\d \(60\)$/); // "Todos"
	});

	it('dados até a 1.6, sem subconjuntos, não têm colunas', () => {
		const antigos = doPar.map(({ subconjuntos: _, ...m }) => m as MetricaVariavel);
		expect(colunasSubconjuntos(antigos)).toEqual([]);
	});
});

describe('composicaoDaAmostra', () => {
	it('dá os idiomas e, quando a soma não bate, os sem resumo', () => {
		expect(composicaoDaAmostra(200, { pt: 159, en: 40 })).toEqual([['em português', 159], ['em inglês', 40], ['sem resumo', 1]]);
		expect(composicaoDaAmostra(60, { pt: 42, en: 18 })).toEqual([['em português', 42], ['em inglês', 18]]);
		expect(composicaoDaAmostra(60, undefined)).toEqual([]);
	});
});
