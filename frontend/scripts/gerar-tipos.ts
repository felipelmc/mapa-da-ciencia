// Gera src/lib/contrato/tipos.ts a partir dos JSON Schemas do contrato (../contrato/schema).
//
// Uso (em frontend/):
//   npm run tipos           # regenera o arquivo
//   npm run tipos:checar    # não escreve; sai com 1 se o arquivo estiver desatualizado
//
// A fonte da verdade são os modelos Pydantic em src/mapa_da_ciencia/contrato/modelos.py.
// Deles saem os schemas (`uv run python scripts/gerar_contrato.py`) e, destes, os tipos.
//
// Os schemas são juntados num só antes de compilar, para que cada tipo apareça uma vez.
// Dois ajustes preparam o schema para o json-schema-to-typescript:
// - `prefixItems` (tuplas do JSON Schema 2020-12, que o Pydantic emite) vira `items` em
//   lista, a forma de tupla que a biblioteca entende;
// - o `title` de cada propriedade é removido. O Pydantic põe títulos como "Titulo" ou "N"
//   em todo campo, e a biblioteca transformaria cada um num tipo exportado, com colisões
//   entre arquivos. Ficam só os títulos dos modelos (raiz e `$defs`).
import { existsSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { compile, type JSONSchema } from 'json-schema-to-typescript';

const RAIZ = fileURLToPath(new URL('..', import.meta.url));
const PASTA_SCHEMAS = join(RAIZ, '..', 'contrato', 'schema');
const DESTINO = join(RAIZ, 'src', 'lib', 'contrato', 'tipos.ts');

type Schema = { [chave: string]: unknown };

const ehObjeto = (v: unknown): v is Schema => typeof v === 'object' && v !== null && !Array.isArray(v);

/** Aplica os dois ajustes descritos no topo, recursivamente. */
function ajustar(no: unknown, ehModelo: boolean): unknown {
	if (Array.isArray(no)) return no.map((v) => ajustar(v, false));
	if (!ehObjeto(no)) return no;
	const saida: Schema = {};
	for (const [chave, valor] of Object.entries(no)) {
		if (chave === 'title' && !ehModelo) continue;
		if (chave === 'prefixItems') {
			saida.items = ajustar(valor, false);
			saida.additionalItems = false;
			continue;
		}
		if (chave === '$defs' && ehObjeto(valor)) {
			saida.$defs = Object.fromEntries(Object.entries(valor).map(([k, v]) => [k, ajustar(v, true)]));
			continue;
		}
		if (chave === 'properties' && ehObjeto(valor)) {
			saida.properties = Object.fromEntries(Object.entries(valor).map(([k, v]) => [k, ajustar(v, false)]));
			continue;
		}
		saida[chave] = ajustar(valor, false);
	}
	return saida;
}

/** Junta os schemas num só: cada arquivo vira um `$defs` com o título do modelo raiz. */
function juntar(): { schema: JSONSchema; arquivos: string[] } {
	if (!existsSync(PASTA_SCHEMAS)) throw new Error(`pasta de schemas não encontrada: ${PASTA_SCHEMAS}`);
	const arquivos = readdirSync(PASTA_SCHEMAS)
		.filter((a) => a.endsWith('.schema.json'))
		.sort();
	const defs: Schema = {};
	const propriedades: Schema = {};
	for (const arquivo of arquivos) {
		const bruto = JSON.parse(readFileSync(join(PASTA_SCHEMAS, arquivo), 'utf8')) as Schema;
		const { $defs, ...raiz } = ajustar(bruto, true) as Schema;
		const titulo = raiz.title;
		if (typeof titulo !== 'string') throw new Error(`${arquivo}: schema sem "title" na raiz`);
		for (const [nome, def] of Object.entries(($defs as Schema | undefined) ?? {})) {
			if (nome in defs && JSON.stringify(defs[nome]) !== JSON.stringify(def)) {
				throw new Error(`o modelo "${nome}" aparece com formas diferentes em mais de um schema (${arquivo})`);
			}
			defs[nome] = def;
		}
		if (titulo in defs) throw new Error(`${arquivo}: o título "${titulo}" colide com um $defs`);
		defs[titulo] = raiz;
		propriedades[arquivo.replace('.schema.json', '')] = { $ref: `#/$defs/${titulo}` };
	}
	const schema = {
		title: 'ContratoDeDados',
		description:
			'Os arquivos do contrato de dados, por nome (o fragmento é cada `detalhes/{xx}.json`).',
		type: 'object',
		additionalProperties: false,
		required: Object.keys(propriedades),
		properties: propriedades,
		$defs: defs
	};
	return { schema: schema as JSONSchema, arquivos };
}

async function gerar(): Promise<string> {
	const { schema, arquivos } = juntar();
	const cabecalho = [
		'/* eslint-disable */',
		'/**',
		' * ARQUIVO GERADO: não edite à mão. Rode `npm run tipos` para regenerar.',
		' *',
		' * Tipos do contrato de dados v1, gerados a partir de:',
		...arquivos.map((a) => ` *   contrato/schema/${a}`),
		' * A fonte da verdade é src/mapa_da_ciencia/contrato/modelos.py.',
		' */'
	].join('\n');
	const ts = await compile(schema, 'ContratoDeDados', {
		bannerComment: cabecalho,
		additionalProperties: false,
		unreachableDefinitions: true,
		strictIndexSignatures: false,
		format: true,
		style: { useTabs: true, singleQuote: true, printWidth: 100 }
	});
	// A biblioteca anota cada tipo com "This interface was referenced by ...", que só
	// repete o nome do tipo. Tira a nota e o comentário que ficar vazio.
	return ts
		.replace(/\n \*\n \* This (?:interface|type) was referenced by [^\n]*\n \* via the `definition` "[^"]+"\./g, '')
		.replace(/\/\*\*\n \* This (?:interface|type) was referenced by [^\n]*\n \* via the `definition` "[^"]+"\.\n \*\/\n/g, '');
}

const checar = process.argv.includes('--checar');
const novo = await gerar();
const atual = existsSync(DESTINO) ? readFileSync(DESTINO, 'utf8') : null;

if (checar) {
	if (atual !== novo) {
		console.error(
			'src/lib/contrato/tipos.ts está desatualizado em relação a contrato/schema/.\n' +
				'Rode `npm run tipos` (em frontend/) e versione o resultado.'
		);
		process.exit(1);
	}
	console.log('Tipos do contrato em dia.');
} else {
	writeFileSync(DESTINO, novo);
	console.log(`${DESTINO.replace(RAIZ, '')} ${atual === novo ? 'já estava em dia' : 'regenerado'}.`);
}
