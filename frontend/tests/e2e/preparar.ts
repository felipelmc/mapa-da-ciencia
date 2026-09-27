// Preparação global dos testes e2e (globalSetup do Playwright).
//
// Monta três sites numa pasta temporária, cada um com o build e uma pasta `dados/` ao lado
// do index.html, e serve cada um com o servidor estático sem reescrita:
//   raiz        build + exemplo sintético, servido em /
//   subcaminho  o mesmo, servido em /mapa-da-ciencia/demo/ (como no GitHub Pages)
//   vazio       build + só um manifesto de projeto recém-criado (`mapa novo`), com api: true
//   painel      build + exemplo sintético com api: true e as APIs falsas do painel (`api-falsa.ts`, a codificação;
//               `api-falsa-painel.ts`, etapas, jobs com SSE, modelos, configuração e codebook)
// As URLs vão para variáveis de ambiente, que os workers herdam. A função devolvida
// derruba os servidores e apaga a pasta temporária.
import { cpSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { criarApiFalsa } from './api-falsa.ts';
import { criarPainelFalso } from './api-falsa-painel.ts';
import { servir, type Servidor } from './servidor.ts';

const RAIZ = fileURLToPath(new URL('../..', import.meta.url));
const BUILD = join(RAIZ, 'build');
const EXEMPLO = join(RAIZ, '..', 'contrato', 'exemplo', 'dados');
export const SUBCAMINHO = '/mapa-da-ciencia/demo/';

/** Data de modificação mais recente entre os arquivos que entram no build. */
function modificadoEm(caminho: string): number {
	const info = statSync(caminho);
	if (!info.isDirectory()) return /\.test\.ts$/.test(caminho) ? 0 : info.mtimeMs;
	return Math.max(0, ...readdirSync(caminho).map((f) => modificadoEm(join(caminho, f))));
}

function conferirBuild() {
	const index = join(BUILD, 'index.html');
	if (!existsSync(index)) throw new Error('build/index.html não existe. Rode `npm run build` antes do `npm run e2e`.');
	const fontes = ['src', 'static', 'svelte.config.js', 'vite.config.ts'].map((f) => join(RAIZ, f));
	if (Math.max(...fontes.map(modificadoEm)) > statSync(index).mtimeMs) {
		throw new Error('O build está mais velho que o código em src/. Rode `npm run build` antes do `npm run e2e`.');
	}
}

function montarSite(destino: string, dados: (pasta: string) => void) {
	mkdirSync(destino, { recursive: true });
	cpSync(BUILD, destino, { recursive: true });
	const pasta = join(destino, 'dados');
	mkdirSync(pasta);
	dados(pasta);
}

export default async function preparar() {
	conferirBuild();
	const tmp = mkdtempSync(join(tmpdir(), 'mapa-e2e-'));
	const servidores: Servidor[] = [];
	try {
		const copiarExemplo = (pasta: string) => cpSync(EXEMPLO, pasta, { recursive: true });
		montarSite(join(tmp, 'raiz'), copiarExemplo);
		montarSite(join(tmp, 'sub', SUBCAMINHO), copiarExemplo);
		montarSite(join(tmp, 'vazio'), (pasta) => {
			const exemplo = JSON.parse(readFileSync(join(EXEMPLO, 'manifesto.json'), 'utf8'));
			const vazio = {
				...exemplo,
				api: true,
				projeto: { nome: 'novo', titulo: 'Projeto novo', descricao: '' },
				contagens: { documentos: 0, topicos: 0, classificados: 0, validados: 0, com_afiliacao: 0 },
				arquivos: ['manifesto'],
				licencas: {}
			};
			writeFileSync(join(pasta, 'manifesto.json'), JSON.stringify(vazio));
		});

		montarSite(join(tmp, 'painel'), (pasta) => {
			copiarExemplo(pasta);
			const manifesto = JSON.parse(readFileSync(join(pasta, 'manifesto.json'), 'utf8'));
			writeFileSync(join(pasta, 'manifesto.json'), JSON.stringify({ ...manifesto, api: true }));
		});

		const [raiz, sub, vazio, painel] = await Promise.all([
			servir(join(tmp, 'raiz')),
			servir(join(tmp, 'sub')),
			servir(join(tmp, 'vazio'), criarPainelFalso(JSON.parse(readFileSync(join(EXEMPLO, 'codebook.json'), 'utf8')))),
			servir(join(tmp, 'painel'), (() => {
				const validacao = criarApiFalsa(EXEMPLO);
				const painel = criarPainelFalso(JSON.parse(readFileSync(join(EXEMPLO, 'codebook.json'), 'utf8')));
				return (req, res, url) => painel(req, res, url) || validacao(req, res, url);
			})())
		]);
		servidores.push(raiz, sub, vazio, painel);
		process.env.E2E_URL_RAIZ = `${raiz.origem}/`;
		process.env.E2E_URL_SUBCAMINHO = `${sub.origem}${SUBCAMINHO}`;
		process.env.E2E_URL_VAZIO = `${vazio.origem}/`;
		process.env.E2E_URL_PAINEL = `${painel.origem}/`;
	} catch (e) {
		await Promise.all(servidores.map((s) => s.fechar()));
		rmSync(tmp, { recursive: true, force: true });
		throw e;
	}

	return async () => {
		await Promise.all(servidores.map((s) => s.fechar()));
		rmSync(tmp, { recursive: true, force: true });
	};
}
