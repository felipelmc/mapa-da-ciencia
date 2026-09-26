/**
 * Busca por título e autores (minisearch), sem diferença de acentos nem de maiúsculas: "coalizao" encontra
 * "Coalizões". Aceita prefixos ("presid" → "presidencialismo") e pequenos erros de digitação. O índice é
 * montado na primeira busca e compartilhado pelas vistas (`indiceDe`).
 */
import MiniSearch from 'minisearch';
import type { TabelaDocumentos } from '$lib/dados/documentos';

export type IndiceBusca = MiniSearch<{ id: number; titulo: string; autores: string }>;

export const dobrar = (termo: string): string =>
	termo
		.normalize('NFD')
		.replace(/\p{Mn}/gu, '')
		.toLowerCase();

export function indexar(t: TabelaDocumentos): IndiceBusca {
	const indice: IndiceBusca = new MiniSearch({
		fields: ['titulo', 'autores'],
		processTerm: (termo) => (termo.length > 1 ? dobrar(termo) : null)
	});
	indice.addAll(Array.from({ length: t.n }, (_, i) => ({ id: i, titulo: t.titulos[i], autores: t.autores[i] })));
	return indice;
}

/** Índices dos documentos que respondem ao texto, do mais ao menos relevante. */
export function buscar(indice: IndiceBusca, texto: string): number[] {
	if (!texto.trim()) return [];
	return indice
		.search(texto, { prefix: true, fuzzy: (termo) => (termo.length > 4 ? 0.2 : false), combineWith: 'AND', boost: { titulo: 2 } })
		.map((r) => r.id as number);
}

const indices = new WeakMap<TabelaDocumentos, IndiceBusca>();

/** O índice da tabela, montado uma vez e compartilhado pelo mapa, pela barra de recorte e pelas vistas. */
export function indiceDe(t: TabelaDocumentos): IndiceBusca {
	let indice = indices.get(t);
	if (!indice) {
		indice = indexar(t);
		indices.set(t, indice);
	}
	return indice;
}
