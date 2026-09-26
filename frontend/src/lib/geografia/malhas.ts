/**
 * As malhas da vista Geografia e as projeções delas.
 *
 * - UFs: malha do IBGE (qualidade mínima, 31 KB), em projeção cônica equivalente com os paralelos padrão no
 *   Brasil, que preserva as áreas (um coroplético não deve inflar o Norte nem encolher o Sul).
 * - Mundo: Natural Earth 1:110m, em Equal Earth, também equivalente.
 *
 * As malhas são geradas por `scripts/baixar-malhas.ts` e carregadas sob demanda (cada uma vira um pedaço separado
 * do build): a vista Geografia só as pede quando abre.
 */
import { geoConicEqualArea, geoEqualEarth, geoPath, type GeoProjection } from 'd3-geo';
import type { Feature, FeatureCollection, GeoJsonProperties, MultiPolygon, Polygon } from 'geojson';
import { feature } from 'topojson-client';
import type { GeometryCollection, Topology } from 'topojson-specification';

export type Regiao<P extends GeoJsonProperties> = Feature<Polygon | MultiPolygon, P>;
export type PropsUF = { sigla: string };
export type PropsPais = { iso: string | null; nome: string };

function colecao<P extends GeoJsonProperties>(topo: Topology, nome: string): Regiao<P>[] {
	const fc = feature(topo, topo.objects[nome] as GeometryCollection<P>) as FeatureCollection<Polygon | MultiPolygon, P>;
	return fc.features;
}

let ufs: Promise<Regiao<PropsUF>[]> | null = null;
let mundo: Promise<Regiao<PropsPais>[]> | null = null;

/** As 27 UFs, com `properties.sigla`. */
export function malhaUF(): Promise<Regiao<PropsUF>[]> {
	ufs ??= import('./malhas/br-uf.json').then((m) => colecao<PropsUF>(m.default as unknown as Topology, 'ufs'));
	return ufs;
}

/** Os países, com `properties.iso` (ISO 3166-1 alfa-2; null em Chipre do Norte e Somalilândia). */
export function malhaMundo(): Promise<Regiao<PropsPais>[]> {
	mundo ??= import('./malhas/mundo.json').then((m) => colecao<PropsPais>(m.default as unknown as Topology, 'paises'));
	return mundo;
}

/** Projeção das UFs, ajustada à área de desenho. */
export function projecaoBrasil(largura: number, altura: number, regioes: Regiao<PropsUF>[]): GeoProjection {
	return geoConicEqualArea()
		.parallels([-2, -22])
		.rotate([54, 0])
		.fitSize([largura, altura], { type: 'FeatureCollection', features: regioes });
}

/** Projeção do mundo (sem a Antártida, que só ocuparia espaço), ajustada à área de desenho. */
export function projecaoMundo(largura: number, altura: number, regioes: Regiao<PropsPais>[]): GeoProjection {
	const semAntartida = regioes.filter((r) => r.properties.iso !== 'AQ');
	return geoEqualEarth().fitSize([largura, altura], { type: 'FeatureCollection', features: semAntartida });
}

/** O `d` de um `<path>` para cada região. */
export function caminhos<P extends GeoJsonProperties>(regioes: Regiao<P>[], projecao: GeoProjection): string[] {
	const caminho = geoPath(projecao);
	return regioes.map((r) => caminho(r) ?? '');
}
