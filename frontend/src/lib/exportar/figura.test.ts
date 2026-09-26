import { describe, expect, it } from 'vitest';
import { larguraPx, nomeDeArquivo, paraCsv, PRESETS } from './figura';

describe('exportar', () => {
	it('CSV com BOM, aspas quando precisa e CRLF', () => {
		const csv = paraCsv(['Nome', 'n'], [['Dados, Rio', 3], ['Diz "oi"', 4]]);
		expect(csv).toBe('﻿Nome,n\r\n"Dados, Rio",3\r\n"Diz ""oi""",4\r\n');
	});

	it('larguras dos presets em pixels', () => {
		const px = Object.fromEntries(PRESETS.map((p) => [p.id, larguraPx(p)]));
		expect(px).toEqual({ 'artigo-1': 1004, 'artigo-2': 2055, 'artigo-2-600': 4110, slide: 1920, telao: 3840 });
		expect(PRESETS.filter((p) => p.id.startsWith('artigo')).every((p) => p.tema === 'prancha')).toBe(true);
	});

	it('nome de arquivo sem acentos nem espaços', () => {
		expect(nomeDeArquivo('Por ano')).toBe('por-ano');
		expect(nomeDeArquivo('Concordância × referência')).toBe('concordancia-referencia');
		expect(nomeDeArquivo('?!')).toBe('figura');
	});
});
