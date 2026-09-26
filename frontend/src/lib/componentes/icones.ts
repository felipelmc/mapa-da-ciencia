/**
 * Ícones de traço, desenhados à mão num quadro de 24×24 (sem biblioteca). Cada ícone é
 * uma lista de caminhos SVG, desenhados com `stroke="currentColor"`.
 */

/** Um círculo como caminho SVG (dois arcos). */
function circulo(cx: number, cy: number, r: number): string {
	return `M${cx - r} ${cy}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0`;
}

export const ICONES = {
	inicio: ['M12 3.5 13.7 10.3 20.5 12 13.7 13.7 12 20.5 10.3 13.7 3.5 12 10.3 10.3Z'],
	mapa: [
		circulo(6.5, 8, 1.3),
		circulo(11, 5.5, 1.3),
		circulo(9.5, 11.5, 1.3),
		circulo(17.5, 8.5, 1.3),
		circulo(15, 14, 1.3),
		circulo(6, 17, 1.3),
		circulo(12.5, 18.5, 1.3),
		circulo(18.5, 17.5, 1.3)
	],
	topicos: ['M3 17c4 0 5-6 9-6s5 4 9 2', 'M3 12.5c4 0 5-7 9-7s5 3 9 1.5', 'M3 20.5h18'],
	classificacao: [
		'M3.5 12.3V4.5a1 1 0 0 1 1-1h7.8l8.2 8.2-8.8 8.8Z',
		circulo(8, 8, 1.4)
	],
	geografia: [
		circulo(12, 12, 8.5),
		'M3.5 12h17',
		'M12 3.5c-3.5 3.5-3.5 13.5 0 17',
		'M12 3.5c3.5 3.5 3.5 13.5 0 17'
	],
	validacao: [circulo(12, 12, 8.5), 'm8 12.3 2.8 2.7 5.4-5.7'],
	redes: [
		circulo(6, 7, 2),
		circulo(18, 6, 2),
		circulo(12, 18, 2),
		'm7.9 7.9 3.1 8.3',
		'm16.8 7.6-3.8 8.6',
		'M8 6.8l8-.6'
	],
	projeto: [
		'M4 7h5m4 0h7',
		circulo(11, 7, 2),
		'M4 12h10m4 0h2',
		circulo(16, 12, 2),
		'M4 17h2m4 0h10',
		circulo(8, 17, 2)
	],
	ajuda: [circulo(12, 12, 8.5), 'M9.6 9.6a2.5 2.5 0 1 1 3.4 2.3c-.6.3-1 .9-1 1.6v.5', circulo(12, 16.9, 0.35)],
	lua: ['M19.5 14.6A7.8 7.8 0 1 1 9.4 4.5a6.2 6.2 0 0 0 10.1 10.1Z'],
	sol: [
		circulo(12, 12, 4),
		'M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M5.3 18.7l1.6-1.6M17.1 6.9l1.6-1.6'
	],
	aviso: ['M12 4 21 19.5H3Z', 'M12 10v4.2', circulo(12, 16.8, 0.35)],
	retorno: ['M9 7 4 12l5 5', 'M4.5 12H14a6 6 0 0 1 0 12h-1']
} as const satisfies Record<string, readonly string[]>;

export type NomeIcone = keyof typeof ICONES;
