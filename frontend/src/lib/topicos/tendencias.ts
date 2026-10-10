/**
 * Tendências de todos os tópicos no recorte: a mesma regra do Python (ADR 0009), sobre as contagens do cubo.
 * O denominador de cada ano é o total de documentos do recorte no ano (com os sem tópico); anos fora do intervalo
 * do recorte ficam com total zero e saem da regressão.
 */
import type { MetodoTendencia, Topicos } from '$lib/contrato/tipos';
import type { TopicoPorAno } from '$lib/dados/cubo';
import { ajustados, tendencia, type Tendencia } from '$lib/estatistica/glm';

export interface TendenciaTopico extends Tendencia {
	id: number;
	/** Participação observada em cada ano (`null` em anos sem documentos no recorte). */
	observado: (number | null)[];
	/** Participação ajustada em cada ano (para a curva tracejada). */
	ajuste: number[] | null;
}

export function tendencias(porAno: TopicoPorAno, ids: number[], metodo: Partial<MetodoTendencia> = {}): TendenciaTopico[] {
	const nAnos = porAno.anos.length;
	const linha = new Map(porAno.ids.map((id, i) => [id, i]));
	const saida: TendenciaTopico[] = [];
	for (const id of ids) {
		const i = linha.get(id);
		if (i === undefined) continue;
		const n = porAno.n.subarray(i * nAnos, (i + 1) * nAnos);
		const t = tendencia(n, porAno.total, porAno.anos, metodo);
		const observado = Array.from(n, (v, j) => (porAno.total[j] > 0 ? v / porAno.total[j] : null));
		saida.push({ ...t, id, observado, ajuste: ajustados(t, porAno.anos) });
	}
	return saida;
}

/** Em alta (maior variação primeiro), em queda (maior queda primeiro) e o resto. */
export function separar(lista: TendenciaTopico[]) {
	const alta = lista.filter((t) => t.direcao === 'alta').sort((a, b) => b.pp_periodo! - a.pp_periodo!);
	const queda = lista.filter((t) => t.direcao === 'queda').sort((a, b) => a.pp_periodo! - b.pp_periodo!);
	const estaveis = lista.filter((t) => t.direcao === 'estavel').length;
	const insuficientes = lista.filter((t) => t.direcao === 'insuficiente').length;
	const frageis = [...alta, ...queda].filter((t) => t.fragil).length;
	return { alta, queda, estaveis, insuficientes, frageis, testados: lista.length - insuficientes };
}

/** De que anos uma tendência frágil depende: "depende de 2011", "depende de 2010 e 2012" ou, com mais de três,
 * "depende de 11 dos 16 anos". `null` para uma tendência que não é frágil. */
export function textoFragil(t: Pick<Tendencia, 'fragil' | 'anos_decisivos'>, anosUsados: number): string | null {
	if (!t.fragil) return null;
	const anos = t.anos_decisivos;
	if (anos.length > 3) return `depende de ${anos.length} dos ${anosUsados} anos`;
	const lista = anos.length > 1 ? `${anos.slice(0, -1).join(', ')} e ${anos[anos.length - 1]}` : String(anos[0]);
	return `depende de ${lista}`;
}

/** O método do gabarito. Os dados até a 1.6 não dizem o quantil e usavam o da normal: sem ele, vale a normal,
 * para que um site publicado antes continue batendo com o próprio gabarito. */
export function metodoDe(topicos: Topicos): Partial<MetodoTendencia> {
	const m = topicos.metodo_tendencia;
	return m ? { ...m, quantil: m.quantil ?? 'normal' } : { quantil: 'normal' };
}
