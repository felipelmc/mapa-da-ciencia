/**
 * Contornos dos tópicos no mapa: a linha que envolve a região mais densa do núcleo de cada tópico.
 *
 * Densidade de núcleo (d3-contour) numa grade sobre o NDC, cortada numa fração do pico de cada tópico. Só o
 * núcleo conta (os reatribuídos ficam de fora, ADR 0007), e o cálculo acontece uma vez, ao abrir o mapa: filtros
 * e a linha do tempo não o refazem.
 */
import { contourDensity } from 'd3-contour';
import type { TabelaDocumentos } from '$lib/dados/documentos';

export type Anel = [number, number][];

// `density.contours()` existe no d3-contour 4, mas ainda não nos tipos (@types/d3-contour 3)
type Densidade = { (valor: number): { coordinates: number[][][][] }; max: number };
type GeradorComContornos = { contours: (pontos: [number, number][]) => Densidade };

const GRADE = 256;

export function calcularContornos(
	t: TabelaDocumentos,
	ids: number[],
	{ fracao = 0.3, largura = 7, minimoPontos = 5 } = {}
): Map<number, Anel[]> {
	const porTopico = new Map<number, [number, number][]>();
	for (let i = 0; i < t.n; i += 1) {
		if (t.atribuicao[i] !== 0 || t.topico[i] < 0) continue;
		const lista = porTopico.get(t.topico[i]) ?? [];
		lista.push([((t.x[i] + 1) / 2) * GRADE, ((t.y[i] + 1) / 2) * GRADE]);
		porTopico.set(t.topico[i], lista);
	}
	const saida = new Map<number, Anel[]>();
	for (const id of ids) {
		const pontos = porTopico.get(id);
		if (!pontos || pontos.length < minimoPontos) continue;
		const gerador = contourDensity<[number, number]>()
			.x((p) => p[0])
			.y((p) => p[1])
			.size([GRADE, GRADE])
			.cellSize(2)
			.bandwidth(largura) as unknown as GeradorComContornos;
		const densidade = gerador.contours(pontos);
		const poligonos = densidade(densidade.max * fracao).coordinates;
		const aneis: Anel[] = poligonos
			.map((poligono) => poligono[0].map(([gx, gy]): [number, number] => [(gx / GRADE) * 2 - 1, (gy / GRADE) * 2 - 1]))
			.filter((anel) => anel.length >= 4);
		if (aneis.length) saida.set(id, aneis);
	}
	return saida;
}

/** O centro (NDC) de cada grupo de tópicos, pesado pelo tamanho, para o rótulo do macrotema. */
export function centroDePeso(itens: { x: number; y: number; peso: number }[]): [number, number] {
	const total = itens.reduce((s, i) => s + i.peso, 0) || 1;
	return [itens.reduce((s, i) => s + i.x * i.peso, 0) / total, itens.reduce((s, i) => s + i.y * i.peso, 0) / total];
}
