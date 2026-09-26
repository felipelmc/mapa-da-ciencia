import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import type { Documentos } from '$lib/contrato/tipos';
import { decodificar, deNdc, escalaDe, paraNdc, VIZINHOS, vizinhosDe } from './documentos';

const exemplo: Documentos = JSON.parse(
	readFileSync(join(import.meta.dirname, '../../../../contrato/exemplo/dados/documentos.json'), 'utf8')
);

describe('decodificar documentos.json', () => {
	const t = decodificar(exemplo);

	it('põe as coordenadas em NDC, com margem e a mesma escala nos dois eixos', () => {
		expect(t.n).toBe(exemplo.n);
		const xs = Array.from(t.x);
		const ys = Array.from(t.y);
		const [ax, ay] = [Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)];
		expect(Math.max(...xs.map(Math.abs), ...ys.map(Math.abs))).toBeLessThanOrEqual(0.9401);
		const [bx, by] = [
			Math.max(...exemplo.colunas.x) - Math.min(...exemplo.colunas.x),
			Math.max(...exemplo.colunas.y) - Math.min(...exemplo.colunas.y)
		];
		expect(ax / ay).toBeCloseTo(bx / by, 4); // a proporção do mapa é preservada
	});

	it('não deixa uma ilha de poucos pontos achatar a nuvem', () => {
		const xs = Array.from({ length: 400 }, (_, i) => (i % 20) / 19);
		const ys = Array.from({ length: 400 }, (_, i) => Math.floor(i / 20) / 19);
		const semIlha = escalaDe(xs, ys);
		const comIlha = escalaDe([...xs, 40, 40], [...ys, 0.5, 0.5]); // dois pontos longe, como um grupo desligado
		expect(comIlha.s).toBeGreaterThan(semIlha.s / 1.3); // sem a ilha, a escala seria 40 vezes menor
		expect(Math.abs(paraNdc(comIlha, 40, 0.5)[0])).toBeGreaterThan(1); // a ilha fica além da tela inicial
		// uma nuvem espalhada de verdade continua inteira na tela
		const larga = escalaDe([...xs, 1.2, -0.2], [...ys, 0.5, 0.5]);
		expect(Math.abs(paraNdc(larga, 1.2, 0.5)[0])).toBeLessThanOrEqual(0.9401);
	});

	it('converte entre dados e NDC nos dois sentidos', () => {
		const [x, y] = paraNdc(t.escala, exemplo.colunas.x[7], exemplo.colunas.y[7]);
		expect(x).toBeCloseTo(t.x[7], 5);
		const [dx, dy] = deNdc(t.escala, x, y);
		expect(dx).toBeCloseTo(exemplo.colunas.x[7], 4);
		expect(dy).toBeCloseTo(exemplo.colunas.y[7], 4);
	});

	it('guarda tópicos, vizinhos e o índice por id', () => {
		expect(t.topico[3]).toBe(exemplo.colunas.topico[3]);
		expect(Array.from(t.topico)).toContain(-1);
		expect(t.vizinhos.length).toBe(exemplo.n * VIZINHOS);
		expect(vizinhosDe(t, 0)).toEqual(exemplo.colunas.vizinhos[0]);
		expect(t.indice.get(exemplo.colunas.id[42])).toBe(42);
		expect(t.anos[0]).toBeLessThanOrEqual(t.anos[1]);
		expect(t.revistas).toEqual(exemplo.dicionarios.revista);
	});
});
