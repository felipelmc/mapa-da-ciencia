import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import type { Documentos, Fragmento } from '$lib/contrato/tipos';
import { fragmentoDe, N_FRAGMENTOS } from './fragmentos';

const EXEMPLO = join(import.meta.dirname, '..', '..', '..', '..', 'contrato', 'exemplo', 'dados');
const ler = <T>(caminho: string): T => JSON.parse(readFileSync(join(EXEMPLO, caminho), 'utf8')) as T;

describe('fragmentoDe', () => {
	it('dá o mesmo resultado que fragmento_de do Python', () => {
		// Calculado com mapa_da_ciencia.contrato.modelos.fragmento_de. Os ids com acento e
		// emoji conferem a codificação UTF-8 (bytes, não caracteres).
		const doPython: Record<string, string> = {
			'': '05',
			a: '2c',
			'exemplo:00000': '35',
			'doi:10.1590/1807-019120243011': '27',
			ação: '09',
			'São Paulo — ñ': '34',
			'🔭 observatório': '27',
			'openalex:W2741809807': '0e'
		};
		for (const [id, esperado] of Object.entries(doPython)) {
			expect(fragmentoDe(id), JSON.stringify(id)).toBe(esperado);
		}
	});

	it('cobre os 64 fragmentos, sempre com dois dígitos hexadecimais', () => {
		const vistos = new Set(Array.from({ length: 5000 }, (_, i) => fragmentoDe(`doc:${i}`)));
		expect(vistos.size).toBe(N_FRAGMENTOS);
		for (const f of vistos) expect(f).toMatch(/^[0-3][0-9a-f]$/);
	});

	it('põe cada documento do exemplo no fragmento que o Python gravou', () => {
		const documentos = ler<Documentos>('documentos.json');
		const fragmentos = new Map<string, Fragmento>();
		for (const arquivo of readdirSync(join(EXEMPLO, 'detalhes'))) {
			const f = ler<Fragmento>(join('detalhes', arquivo));
			expect(`${f.fragmento}.json`).toBe(arquivo);
			fragmentos.set(f.fragmento, f);
		}

		const ids = documentos.colunas.id;
		expect(ids.length).toBe(documentos.n);
		expect(ids.length).toBeGreaterThan(0);
		const fora = ids.filter((id) => !(id in (fragmentos.get(fragmentoDe(id))?.documentos ?? {})));
		expect(fora).toEqual([]);

		// E o contrário: nenhum fragmento guarda documento que não seja dele.
		const total = [...fragmentos.values()].reduce((s, f) => s + Object.keys(f.documentos).length, 0);
		expect(total).toBe(ids.length);
	});
});
