/** Quais documentos o recorte (anos, revistas, tópicos, busca e laço) deixa visíveis no mapa. */
import type { TabelaDocumentos } from '$lib/dados/documentos';
import type { Filtros } from '$lib/estado/url';
import { dentro, type Ponto } from '$lib/graficos/geometria';

export interface Extras {
	/** Documentos que respondem à busca (`null` = sem busca). */
	buscados?: Set<number> | null;
	/** Laço em NDC (`null` = sem laço). */
	laco?: Ponto[] | null;
}

/** Índices visíveis, ou `null` quando nada é filtrado (todos visíveis). */
export function visiveis(
	t: TabelaDocumentos,
	f: Pick<Filtros, 'anos' | 'revistas' | 'topicos'>,
	{ buscados = null, laco = null }: Extras = {}
): number[] | null {
	if (!f.anos && !f.revistas.length && !f.topicos.length && !buscados && !laco) return null;
	const revistas = new Set(f.revistas.map((r) => t.revistas.indexOf(r)).filter((i) => i >= 0));
	const topicos = new Set(f.topicos);
	const saida: number[] = [];
	for (let i = 0; i < t.n; i += 1) {
		if (f.anos && (t.ano[i] < f.anos[0] || t.ano[i] > f.anos[1])) continue;
		if (f.revistas.length && !revistas.has(t.revista[i])) continue;
		if (f.topicos.length && !topicos.has(t.topico[i])) continue;
		if (buscados && !buscados.has(i)) continue;
		if (laco && !dentro(t.x[i], t.y[i], laco)) continue;
		saida.push(i);
	}
	return saida;
}
