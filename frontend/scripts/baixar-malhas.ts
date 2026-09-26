// Gera as malhas da vista Geografia em src/lib/geografia/malhas/ (versionadas; o painel não baixa nada):
//
// - br-uf.json: as 27 UFs em TopoJSON, da API de malhas do IBGE (qualidade mínima, 1 requisição), com a sigla
//   de cada UF em `properties.sigla` (o IBGE dá o código, `codarea`);
// - mundo.json: os países do Natural Earth 1:110m (pacote world-atlas, versão fixa), com o código ISO 3166-1
//   alfa-2 em `properties.iso` (o world-atlas usa o numérico da ONU, que o CLDR do Node converte).
//
//   node scripts/baixar-malhas.ts            # baixa a malha do IBGE e regrava as duas
//   node scripts/baixar-malhas.ts --so-mundo # regrava só a do mundo, sem rede
//
// Fontes: IBGE, Malhas territoriais (dados públicos, citar a fonte); Natural Earth (domínio público), via world-atlas
// (ISC). Ver o ADR 0010.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const PASTA = fileURLToPath(new URL('../src/lib/geografia/malhas/', import.meta.url));
const UFS_CSV = fileURLToPath(new URL('../../src/mapa_da_ciencia/geografia/dados/ufs.csv', import.meta.url));
const MUNDO = fileURLToPath(new URL('../node_modules/world-atlas/countries-110m.json', import.meta.url));
const IBGE =
	'https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/json&qualidade=minima&intrarregiao=UF';
// os três territórios sem código numérico no world-atlas
const SEM_CODIGO: Record<string, string | null> = { Kosovo: 'XK', 'N. Cyprus': null, Somaliland: null };

type Geometria = { type: string; id?: string; arcs?: unknown; properties?: Record<string, unknown> };
type Topologia = { type: 'Topology'; objects: Record<string, { type: string; geometries: Geometria[] }>; [k: string]: unknown };

function gravar(nome: string, topo: Topologia) {
	mkdirSync(PASTA, { recursive: true });
	writeFileSync(PASTA + nome, JSON.stringify(topo));
	console.log(`${nome}: ${Object.values(topo.objects)[0].geometries.length} feições, ${(JSON.stringify(topo).length / 1024).toFixed(0)} KB`);
}

async function ufs() {
	const siglas = new Map(
		readFileSync(UFS_CSV, 'utf8')
			.trim()
			.split('\n')
			.slice(1)
			.map((linha) => linha.split(','))
			.map(([sigla, , codigo]) => [codigo, sigla])
	);
	const resposta = await fetch(IBGE);
	if (!resposta.ok) throw new Error(`IBGE respondeu ${resposta.status}`);
	const topo = (await resposta.json()) as Topologia;
	const [objeto] = Object.values(topo.objects);
	for (const g of objeto.geometries) {
		const codigo = String(g.properties?.codarea);
		const sigla = siglas.get(codigo);
		if (!sigla) throw new Error(`código de UF desconhecido: ${codigo}`);
		g.properties = { sigla };
	}
	if (objeto.geometries.length !== 27) throw new Error(`esperava 27 UFs, vieram ${objeto.geometries.length}`);
	gravar('br-uf.json', { ...topo, objects: { ufs: objeto } });
}

function mundo() {
	const topo = JSON.parse(readFileSync(MUNDO, 'utf8')) as Topologia;
	const paises = topo.objects.countries;
	for (const g of paises.geometries) {
		const nome = String(g.properties?.name);
		const iso = g.id ? Intl.getCanonicalLocales(`und-${g.id}`)[0].slice(4) : SEM_CODIGO[nome];
		if (iso === undefined || (iso && !/^[A-Z]{2}$/.test(iso))) throw new Error(`sem ISO-2: ${g.id} ${nome}`);
		g.properties = { iso, nome };
		delete g.id;
	}
	gravar('mundo.json', { type: 'Topology', arcs: topo.arcs, transform: topo.transform, objects: { paises } } as Topologia);
}

if (!process.argv.includes('--so-mundo')) await ufs();
mundo();
