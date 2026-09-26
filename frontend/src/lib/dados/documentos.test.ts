import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import type { Documentos } from '$lib/contrato/tipos';
import { decodificar, deNdc, paraNdc, VIZINHOS, vizinhosDe } from './documentos';

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
