import { describe, expect, it } from 'vitest';
import type { TabelaDocumentos } from '$lib/dados/documentos';
import { buscar, dobrar, indexar } from './busca';

const tabela = {
	n: 4,
	titulos: [
		'Coalizões e agenda legislativa no presidencialismo',
		'Eleições municipais em São Paulo',
		'Política externa brasileira e a China',
		'Presidencialismo de coalizão revisitado'
	],
	autores: ['Limongi, F.; +1', 'Silva, A.', 'Almeida, P.', 'Figueiredo, A.']
} as TabelaDocumentos;

describe('busca no mapa', () => {
	const indice = indexar(tabela);

	it('ignora acentos e maiúsculas', () => {
		expect(dobrar('Coalizões ÇÃ')).toBe('coalizoes ca');
		expect(buscar(indice, 'coalizoes').sort()).toEqual([0]);
		expect(buscar(indice, 'SAO PAULO')).toEqual([1]);
	});

	it('aceita prefixos, erros pequenos e autores, e junta os termos com E', () => {
		expect(buscar(indice, 'presid').sort()).toEqual([0, 3]);
		expect(buscar(indice, 'presidencialsmo').sort()).toEqual([0, 3]);
		expect(buscar(indice, 'limongi')).toEqual([0]);
		expect(buscar(indice, 'presidencialismo coalizão').sort()).toEqual([3]);
		expect(buscar(indice, '  ')).toEqual([]);
	});
});
