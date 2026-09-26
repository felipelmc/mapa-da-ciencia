/**
 * Escala linear mínima, com a interface que o regl-scatterplot usa (`domain` e `range`, como no d3-scale).
 *
 * Passadas ao gráfico como `xScale`/`yScale`, ele as atualiza a cada movimento da câmera: o domínio vira a
 * parte dos dados visível na tela, e a faixa, o tamanho do canvas em pixels. Chamar a escala converte uma
 * coordenada dos dados (NDC) em pixel, o que posiciona os rótulos sobre o mapa.
 */
export interface EscalaLinear {
	(valor: number): number;
	domain(): [number, number];
	domain(d: [number, number]): EscalaLinear;
	range(): [number, number];
	range(r: [number, number]): EscalaLinear;
}

export function escalaLinear(dominio: [number, number] = [-1, 1], faixa: [number, number] = [0, 1]): EscalaLinear {
	let d = dominio;
	let r = faixa;
	const escala = ((v: number) => r[0] + ((v - d[0]) / (d[1] - d[0] || 1)) * (r[1] - r[0])) as EscalaLinear;
	escala.domain = ((novo?: [number, number]) => {
		if (!novo) return [...d] as [number, number];
		d = [novo[0], novo[1]];
		return escala;
	}) as EscalaLinear['domain'];
	escala.range = ((novo?: [number, number]) => {
		if (!novo) return [...r] as [number, number];
		r = [novo[0], novo[1]];
		return escala;
	}) as EscalaLinear['range'];
	return escala;
}
