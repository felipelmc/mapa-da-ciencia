import { describe, expect, it } from 'vitest';
import { aplicar, fracao, inicial, MENSAGENS_GUARDADAS, type EventoJob } from './job';

const ev = (seq: number, tipo: string, dados: Record<string, unknown> = {}): EventoJob => ({ seq, tipo, dados });

describe('job ao vivo', () => {
	const eventos = [
		ev(1, 'estado', { estado: 'rodando' }),
		ev(2, 'etapa', { nome: 'Classificando', total: 10 }),
		ev(3, 'avanco', { etapa: 'Classificando', feito: 4, total: 10 }),
		ev(4, 'mensagem', { texto: 'metade' }),
		ev(5, 'avanco', { etapa: 'Classificando', feito: 10, total: 10 }),
		ev(6, 'resumo', { frase: '10 documentos.' }),
		ev(7, 'fim', { estado: 'concluido' })
	];

	it('monta o estado a partir dos eventos', () => {
		const e = eventos.reduce(aplicar, inicial({ id: 'a', etapa: 'classificacao', estado: 'na_fila' }));
		expect(e).toMatchObject({
			estado: 'concluido',
			passo: 'Classificando',
			feito: 10,
			total: 10,
			mensagens: ['metade'],
			resumo: '10 documentos.',
			terminado: true,
			ultimoSeq: 7
		});
		expect(fracao(e)).toBe(1);
	});

	it('ignora eventos repetidos depois de uma reconexão', () => {
		const comRepeticao = [...eventos.slice(0, 4), ...eventos.slice(2, 7)];
		const a = comRepeticao.reduce(aplicar, inicial({ id: 'a', etapa: 'x', estado: 'na_fila' }));
		const b = eventos.reduce(aplicar, inicial({ id: 'a', etapa: 'x', estado: 'na_fila' }));
		expect(a).toEqual(b);
	});

	it('guarda o erro, limita as mensagens e não sabe a fração sem total', () => {
		let e = inicial({ id: 'b', etapa: 'x', estado: 'rodando' });
		e = aplicar(e, ev(1, 'etapa', { nome: 'Sem total', total: null }));
		expect(fracao(e)).toBeNull();
		for (let i = 0; i < MENSAGENS_GUARDADAS + 5; i += 1) e = aplicar(e, ev(i + 2, 'mensagem', { texto: `m${i}` }));
		expect(e.mensagens).toHaveLength(MENSAGENS_GUARDADAS);
		e = aplicar(e, ev(100, 'erro', { mensagem: 'sem corpus' }));
		e = aplicar(e, ev(101, 'fim', { estado: 'falhou' }));
		expect([e.erro, e.estado, e.terminado]).toEqual(['sem corpus', 'falhou', true]);
	});
});
