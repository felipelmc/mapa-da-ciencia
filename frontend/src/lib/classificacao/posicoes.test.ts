import { describe, expect, it } from 'vitest';
import { emUtf16, posicoesJs } from './posicoes';

describe('posições das evidências', () => {
	it('sem caracteres fora do plano básico, nada muda', () => {
		expect(emUtf16('coeficiente β = 0,4', 12)).toBe(12);
	});

	it('um caractere de dois códigos antes do trecho desloca a posição', () => {
		// em Python: "𝛽 é o efeito"[4:8] == "o ef"
		const texto = '𝛽 é o efeito';
		const { inicio, fim } = posicoesJs(texto, { inicio: 4, fim: 8 });
		expect(texto.slice(inicio!, fim!)).toBe('o ef');
		expect(posicoesJs(texto, { inicio: null, fim: null })).toEqual({ inicio: null, fim: null });
	});
});
