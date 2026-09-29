import { describe, expect, it } from 'vitest';
import type { Validacao } from '$lib/contrato/tipos';
import { nomesLegiveis } from './nomes';

type Entrada = Pick<Validacao, 'codificadores' | 'juri'>;
const participante = (nome: string, tipo: 'humano' | 'referencia' | 'modelo', familia: string | null = null) => ({ nome, tipo, n: 200, familia });
const juri = (supervisor: string | null, familia_supervisor: string | null) =>
	({ supervisor, familia_supervisor, membros: [], referencia: null, documentos: 200, etapas: {} }) as unknown as Validacao['juri'];

describe('nomesLegiveis', () => {
	it('dá nome aos ids reservados do júri, à referência e ao supervisor, pela família', () => {
		const v: Entrada = {
			codificadores: [
				participante('claude-opus', 'referencia', 'claude'),
				participante('qwen3.5:9b', 'modelo'),
				participante('juri', 'modelo'),
				participante('juri-r1', 'modelo'),
				participante('juri-supervisor', 'modelo', 'claude'),
				participante('Ana', 'humano')
			],
			juri: juri('opus-supervisor', 'claude')
		};
		const nomes = nomesLegiveis(v);
		expect(nomes.get('claude-opus')).toBe('Claude');
		expect(nomes.get('opus-supervisor')).toBe('Claude');
		expect(nomes.get('juri')).toBe('Júri de modelos');
		expect(nomes.get('juri-r1')).toBe('Júri (1ª votação)');
		expect(nomes.get('juri-supervisor')).toBe('Júri com supervisor');
		// os ids do júri valem mesmo fora da lista; modelos locais e pessoas ficam com o nome deles
		expect(nomesLegiveis({ codificadores: [], juri: null }).get('juri-r1')).toBe('Júri (1ª votação)');
		expect(nomes.has('qwen3.5:9b')).toBe(false);
		expect(nomes.has('Ana')).toBe(false);
	});

	it('sem família conhecida, a referência fica com o id; duas referências da mesma família também', () => {
		expect(nomesLegiveis({ codificadores: [participante('anotador-x', 'referencia')], juri: null }).get('anotador-x')).toBe('anotador-x');
		const duas = nomesLegiveis({
			codificadores: [participante('claude-opus', 'referencia', 'claude'), participante('claude-sonnet', 'referencia', 'claude')],
			juri: null
		});
		expect([duas.get('claude-opus'), duas.get('claude-sonnet')]).toEqual(['claude-opus', 'claude-sonnet']);
		expect(nomesLegiveis({ codificadores: [participante('gpt-ref', 'referencia', 'gpt')], juri: null }).get('gpt-ref')).toBe('GPT');
	});
});
