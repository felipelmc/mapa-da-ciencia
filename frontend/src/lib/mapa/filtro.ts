/** Quais documentos o recorte (anos, revistas, tópicos) deixa visíveis no mapa. */
import type { TabelaDocumentos } from '$lib/dados/documentos';
import type { Filtros } from '$lib/estado/url';

/** Índices visíveis, ou `null` quando nada é filtrado (todos visíveis). */
export function visiveis(t: TabelaDocumentos, f: Pick<Filtros, 'anos' | 'revistas' | 'topicos'>): number[] | null {
	if (!f.anos && !f.revistas.length && !f.topicos.length) return null;
	const revistas = new Set(f.revistas.map((r) => t.revistas.indexOf(r)).filter((i) => i >= 0));
	const topicos = new Set(f.topicos);
	const saida: number[] = [];
	for (let i = 0; i < t.n; i += 1) {
		if (f.anos && (t.ano[i] < f.anos[0] || t.ano[i] > f.anos[1])) continue;
		if (f.revistas.length && !revistas.has(t.revista[i])) continue;
		if (f.topicos.length && !topicos.has(t.topico[i])) continue;
		saida.push(i);
	}
	return saida;
}
