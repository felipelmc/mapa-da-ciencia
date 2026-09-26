import { describe, expect, it } from 'vitest';
import { dentro, selecionar, simplificar, type Ponto } from './geometria';

const quadrado: Ponto[] = [
	[0, 0],
	[2, 0],
	[2, 2],
	[0, 2]
];

describe('ponto no polígono', () => {
	it('quadrado e polígono côncavo', () => {
		expect(dentro(1, 1, quadrado)).toBe(true);
		expect(dentro(3, 1, quadrado)).toBe(false);
		const u: Ponto[] = [[0, 0], [3, 0], [3, 3], [2, 3], [2, 1], [1, 1], [1, 3], [0, 3]];
		expect(dentro(1.5, 2, u)).toBe(false); // no vão do "U"
		expect(dentro(0.5, 2, u)).toBe(true);
	});

	it('seleciona os índices dentro', () => {
		const xs = [0.5, 1.5, 2.5, 1, -1];
		const ys = [0.5, 1.5, 1, 3, 1];
		expect(selecionar(xs, ys, quadrado)).toEqual([0, 1]);
		expect(selecionar(xs, ys, quadrado.slice(0, 2))).toEqual([]);
	});
});

describe('simplificação do laço', () => {
	it('reduz um círculo desenhado à mão para no máximo 30 vértices, sem deformar', () => {
		const circulo: Ponto[] = Array.from({ length: 400 }, (_, i) => {
			const a = (2 * Math.PI * i) / 400;
			return [Math.cos(a) * (1 + 0.01 * Math.sin(17 * a)), Math.sin(a)];
		});
		const s = simplificar(circulo);
		expect(s.length).toBeLessThanOrEqual(30);
		expect(s.length).toBeGreaterThanOrEqual(8);
		expect(dentro(0, 0, s)).toBe(true);
		expect(dentro(0.8, 0, s)).toBe(true);
		expect(dentro(1.2, 0, s)).toBe(false);
	});

	it('deixa polígonos pequenos como estão', () => {
		expect(simplificar(quadrado)).toBe(quadrado);
	});
});
