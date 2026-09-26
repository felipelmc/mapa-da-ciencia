/**
 * As posições das evidências no contrato contam pontos de código Unicode, como o Python conta. O JavaScript indexa
 * as strings em unidades UTF-16, e um caractere fora do plano básico (𝛽, um emoji) ocupa duas. Sem conversão, cada
 * um deles antes do trecho deslocaria a marcação em uma posição.
 */

const FORA_DO_PLANO_BASICO = /[\uD800-\uDBFF]/;

/** A posição em unidades UTF-16 correspondente à posição `pontos` (em pontos de código) do texto. */
export function emUtf16(texto: string, pontos: number): number {
	if (!FORA_DO_PLANO_BASICO.test(texto)) return pontos;
	let i = 0;
	for (let n = 0; n < pontos && i < texto.length; n += 1) i += texto.codePointAt(i)! > 0xffff ? 2 : 1;
	return i;
}

/** `inicio` e `fim` de uma evidência convertidos para o JavaScript (nulos continuam nulos). */
export function posicoesJs(
	texto: string,
	e: { inicio?: number | null; fim?: number | null }
): { inicio: number | null; fim: number | null } {
	return {
		inicio: e.inicio == null ? null : emUtf16(texto, e.inicio),
		fim: e.fim == null ? null : emUtf16(texto, e.fim)
	};
}
