/**
 * Fragmentos de detalhes: resumos e evidências ficam fora de `documentos.json`, divididos
 * em 64 arquivos `detalhes/{00..3f}.json`, carregados sob demanda.
 *
 * `fragmentoDe` é a mesma função que `fragmento_de` em
 * src/mapa_da_ciencia/contrato/modelos.py: FNV-1a de 32 bits sobre os bytes UTF-8 do id,
 * módulo 64, em dois dígitos hexadecimais. Se uma mudar, a outra tem que mudar junto;
 * `fragmentos.test.ts` confere contra valores calculados no Python e contra o exemplo.
 */

export const N_FRAGMENTOS = 64;

const BASE_FNV = 0x811c9dc5;
const PRIMO_FNV = 0x01000193;
const codificador = new TextEncoder();

/** Nome do fragmento (`"00"`…`"3f"`) onde está o detalhe do documento `id`. */
export function fragmentoDe(id: string): string {
	let h = BASE_FNV;
	for (const byte of codificador.encode(id)) {
		h ^= byte;
		// Math.imul multiplica em 32 bits, como o `& 0xFFFFFFFF` do Python; `>>> 0` deixa sem sinal.
		h = Math.imul(h, PRIMO_FNV) >>> 0;
	}
	return (h % N_FRAGMENTOS).toString(16).padStart(2, '0');
}
