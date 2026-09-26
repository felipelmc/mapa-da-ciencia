// Gera src/mapa_da_ciencia/geografia/dados/paises.csv: os nomes de cada país (ISO 3166-1 alfa-2) em português,
// inglês e espanhol, a partir do `Intl.DisplayNames` do Node (dados do CLDR, sem download).
//
//   node scripts/gerar_paises.ts            # grava
//   node scripts/gerar_paises.ts --checar   # falha se o arquivo estiver diferente
//
// As variantes que o CLDR não traz (EUA, Holanda, Inglaterra…) ficam à mão em variantes_paises.csv.
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const DESTINO = fileURLToPath(new URL('../src/mapa_da_ciencia/geografia/dados/paises.csv', import.meta.url));
const IDIOMAS = ['pt', 'en', 'es'] as const;

// Códigos que o CLDR nomeia mas que não são países da ISO 3166-1 (ou são reservados para outros usos).
const FORA = new Set(['AC', 'CP', 'CQ', 'DG', 'EA', 'EU', 'EZ', 'IC', 'QO', 'TA', 'UN', 'XA', 'XB', 'ZZ']);

const nomes = Object.fromEntries(IDIOMAS.map((l) => [l, new Intl.DisplayNames([l], { type: 'region', fallback: 'none' })]));
const letras = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
const linhas: string[] = [];
for (const a of letras) {
	for (const b of letras) {
		const codigo = a + b;
		if (FORA.has(codigo)) continue;
		// códigos antigos (DD, SU, YU, UK…) são apelidos de outro código no CLDR
		if (Intl.getCanonicalLocales(`und-${codigo}`)[0] !== `und-${codigo}`) continue;
		const pt = nomes.pt.of(codigo);
		// sem nome, o código não existe; o CLDR devolve o próprio código em alguns casos
		if (!pt || pt === codigo) continue;
		linhas.push([codigo, ...IDIOMAS.map((l) => nomes[l].of(codigo)!)].map(csv).join(','));
	}
}

function csv(valor: string): string {
	return /[",\n]/.test(valor) ? `"${valor.replaceAll('"', '""')}"` : valor;
}

const conteudo =
	`# gerado por scripts/gerar_paises.ts (Node ${process.versions.node}, CLDR ${process.versions.cldr}); não editar à mão\n` +
	`iso2,pt,en,es\n${linhas.join('\n')}\n`;

if (process.argv.includes('--checar')) {
	const atual = readFileSync(DESTINO, 'utf8');
	// a linha do cabeçalho muda com a versão do Node; o que importa são os nomes
	const semCabecalho = (s: string) => s.split('\n').slice(1).join('\n');
	if (semCabecalho(atual) !== semCabecalho(conteudo)) {
		console.error('paises.csv desatualizado: rode node scripts/gerar_paises.ts');
		process.exit(1);
	}
} else {
	writeFileSync(DESTINO, conteudo);
	console.log(`${linhas.length} países em ${DESTINO}`);
}
