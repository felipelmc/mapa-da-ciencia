import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import type { Documentos, Topicos } from '$lib/contrato/tipos';
import { decodificar } from '$lib/dados/documentos';
import { colorir, DEGRADE_ANOS } from './cores';

const pasta = join(import.meta.dirname, '../../../../contrato/exemplo/dados');
const docs: Documentos = JSON.parse(readFileSync(join(pasta, 'documentos.json'), 'utf8'));
const topicos: Topicos = JSON.parse(readFileSync(join(pasta, 'topicos.json'), 'utf8'));
const t = decodificar(docs);

describe('colorir', () => {
	it('tópicos: categorias densas na ordem do contrato, sem tópico em cinza no fim', () => {
		const c = colorir(t, topicos, 'topico', '#777777');
		expect(c.cores).toHaveLength(topicos.topicos.length + 1);
		expect(c.cores.at(-1)).toBe('#777777');
		const i = Array.from(t.topico).findIndex((id) => id === topicos.topicos[2].id);
		expect(c.valores[i]).toBe(2);
		const semTopico = Array.from(t.topico).indexOf(-1);
		expect(c.valores[semTopico]).toBe(topicos.topicos.length);
		expect(Math.max(...c.valores)).toBeLessThan(c.cores.length);
	});

	it('macrotemas agrupam os tópicos', () => {
		const c = colorir(t, topicos, 'macrotema', '#777777');
		expect(c.cores.slice(0, -1)).toEqual(topicos.macrotemas.map((m) => m.cor));
		const m = topicos.macrotemas[1];
		const i = Array.from(t.topico).findIndex((id) => m.topicos.includes(id));
		expect(c.valores[i]).toBe(1);
	});

	it('anos num degradê de 0 a 1, revistas na ordem do dicionário', () => {
		const anos = colorir(t, topicos, 'ano', '#777777');
		expect(anos.tipo).toBe('continuous');
		expect(Math.min(...anos.valores)).toBe(0);
		expect(Math.max(...anos.valores)).toBe(1);
		expect(anos.cores).toEqual(DEGRADE_ANOS);
		const revistas = colorir(t, topicos, 'revista', '#777777');
		expect(revistas.legenda.map((l) => l.rotulo)).toEqual(t.revistas);
		expect(revistas.valores[0]).toBe(t.revista[0]);
	});
});
