/**
 * Classes de cor dos mapas da geografia. A produção por UF é muito concentrada (no piloto, São Paulo tem quase 400
 * vezes o peso do Acre), então as classes crescem em escala logarítmica, com limites "redondos" (1, 2, 5, 10, 20,
 * 50…) para a legenda ser legível. Zero fica fora das classes (cor `--seq-vazio`).
 */

export const N_CLASSES = 6;

const REDONDOS = [1, 2, 5];

/** O número redondo (1, 2 ou 5 × 10^k) mais próximo de `x` em escala logarítmica. */
export function redondo(x: number): number {
	if (x <= 0) return 0;
	const k = Math.floor(Math.log10(x));
	const candidatos = [...REDONDOS.map((r) => r * 10 ** k), 10 ** (k + 1)];
	return candidatos.reduce((a, b) => (Math.abs(Math.log(b / x)) < Math.abs(Math.log(a / x)) ? b : a));
}

/**
 * Limites inferiores das classes 2 a `n` (a classe 1 começa no menor valor positivo), espaçados em log entre o
 * menor e o maior valor positivo e arredondados. Limites repetidos são removidos: com poucos valores, há menos
 * classes.
 */
export function quebras(valores: Iterable<number>, n = N_CLASSES): number[] {
	const positivos = [...valores].filter((v) => v > 0);
	if (positivos.length < 2) return [];
	const min = Math.min(...positivos);
	const max = Math.max(...positivos);
	if (max / min < 1.5) return [];
	const saida: number[] = [];
	for (let i = 1; i < n; i += 1) {
		const q = redondo(min * (max / min) ** (i / n));
		if (q > min && q <= max && !saida.includes(q)) saida.push(q);
	}
	return saida;
}

/** A classe de um valor: 0 para zero (ou sem dado), de 1 a `quebras.length + 1` para os positivos. */
export function classe(valor: number, limites: number[]): number {
	if (!(valor > 0)) return 0;
	let c = 1;
	for (const q of limites) if (valor >= q) c += 1;
	return c;
}

/**
 * A cor de cada classe: as classes usadas se espalham pelos 6 tons, do mais claro ao mais escuro (no tema claro;
 * o contrário no escuro), para duas classes não ficarem com tons vizinhos quando há poucas.
 */
export function corDaClasse(c: number, nClasses: number): string {
	if (c <= 0) return 'var(--seq-vazio)';
	const tom = nClasses <= 1 ? N_CLASSES : 1 + Math.round(((c - 1) * (N_CLASSES - 1)) / (nClasses - 1));
	return `var(--seq-${tom})`;
}
