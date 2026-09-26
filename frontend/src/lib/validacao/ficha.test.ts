import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import type { CodebookContrato, VariavelContrato } from '$lib/contrato/tipos';
import { escolher, faltando, ondeRetomar, opcoesDe, paraGravar, respondida } from './ficha';

const pasta = join(import.meta.dirname, '../../../../contrato/exemplo/dados');
const codebook: CodebookContrato = JSON.parse(readFileSync(join(pasta, 'codebook.json'), 'utf8'));
const por = (tipo: string) => codebook.variaveis.find((v) => v.tipo === tipo)!;
const multipla: VariavelContrato = {
	id: 'fontes',
	rotulo: 'Fontes',
	tipo: 'multipla',
	pergunta: '?',
	categorias: [
		{ valor: 'surveys', rotulo: 'Surveys', definicao: '' },
		{ valor: 'documentos', rotulo: 'Documentos', definicao: '' }
	]
};

describe('ficha', () => {
	it('numera as opções: categorias, Sim/Não, nada para texto', () => {
		expect(opcoesDe(por('categorica')).map((o) => o.valor)).toEqual(por('categorica').categorias!.map((c) => c.valor));
		expect(opcoesDe(por('booleana')).map((o) => o.rotulo)).toEqual(['Sim', 'Não']);
		expect(opcoesDe(por('texto'))).toEqual([]);
	});

	it('escolhe, troca e liga/desliga na múltipla', () => {
		const cat = por('categorica');
		const r = escolher(cat, undefined, 1);
		expect(r.valor).toBe(cat.categorias![1].valor);
		expect(escolher(cat, { ...r, incerto: true }, 0)).toMatchObject({ valor: cat.categorias![0].valor, incerto: true });
		expect(escolher(por('booleana'), undefined, 1).valor).toBe(false);
		expect(escolher(cat, r, 99)).toBe(r); // tecla sem opção
		let m = escolher(multipla, undefined, 1);
		m = escolher(multipla, m, 0);
		expect(m.valor).toEqual(['documentos', 'surveys']);
		expect(escolher(multipla, m, 1).valor).toEqual(['surveys']);
	});

	it('sabe o que falta e só grava o respondido', () => {
		const texto = por('texto');
		const vazio = { valor: '  ', evidencia: '', incerto: false, nota: '' };
		expect(respondida(texto, vazio)).toBe(false);
		expect(respondida(multipla, { ...vazio, valor: [] })).toBe(true); // "nenhuma" é resposta
		const respostas = { [por('categorica').id]: escolher(por('categorica'), undefined, 0), [texto.id]: vazio };
		expect(faltando(codebook, respostas)).toEqual(
			codebook.variaveis.map((v) => v.id).filter((id) => id !== por('categorica').id)
		);
		expect(Object.keys(paraGravar(codebook, respostas))).toEqual([por('categorica').id]);
	});

	it('retoma na primeira ficha incompleta', () => {
		expect(ondeRetomar([{ completa: true }, { completa: false }, { completa: false }])).toBe(1);
		expect(ondeRetomar([{ completa: true }, { completa: true }])).toBe(1);
		expect(ondeRetomar([])).toBe(0);
	});
});
