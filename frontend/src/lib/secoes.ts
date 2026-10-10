/**
 * As seções do app, na ordem do trilho lateral. É o lugar único para rótulo, rota, ícone, a frase que descreve
 * cada vista e os arquivos do contrato que ela usa.
 */
import type { Manifesto } from '$lib/contrato/tipos';
import type { NomeArquivo } from '$lib/dados';
import type { NomeIcone } from '$lib/componentes/icones';

export type IdSecao =
	| 'inicio'
	| 'mapa'
	| 'topicos'
	| 'classificacao'
	| 'geografia'
	| 'validacao'
	| 'redes'
	| 'projeto';

export interface Secao {
	id: IdSecao;
	rotulo: string;
	/** Caminho da rota, sem o `#` (ver `rota()`). */
	caminho: string;
	icone: NomeIcone;
	/** Uma frase: o que a vista mostra. Aparece no cabeçalho e no estado vazio. */
	resumo: string;
	/** Arquivos do contrato que a vista usa. O estado vazio mostra quais existem. */
	arquivos: NomeArquivo[];
	/** Só aparece quando `manifesto.api` é verdadeiro (painel local). */
	soNoPainel?: boolean;
	/** No site publicado (sem API), a seção aparece com outro nome e outro resumo (Projeto → Metodologia). */
	noSite?: { rotulo: string; resumo: string };
	/** A vista ocupa toda a área de conteúdo, sem margens nem largura máxima (o mapa). */
	telaCheia?: boolean;
	/** Vista de análise: recebe o recorte comum (anos, revistas, tópicos, laço, lugares) pelo trilho. */
	recorte?: boolean;
}

export const SECOES: readonly Secao[] = [
	{
		id: 'inicio',
		rotulo: 'Início',
		caminho: '/',
		icone: 'inicio',
		resumo: 'O corpus em números: documentos, tópicos, revistas, período e macrotemas.',
		arquivos: ['manifesto', 'revistas', 'topicos']
	},
	{
		id: 'mapa',
		rotulo: 'Mapa',
		caminho: '/mapa',
		icone: 'mapa',
		resumo:
			'Cada documento vira um ponto, e textos parecidos ficam perto. Dá para filtrar por ano, revista e tópico, colorir por categoria e selecionar grupos com o laço.',
		arquivos: ['documentos', 'topicos'],
		telaCheia: true,
		recorte: true
	},
	{
		id: 'topicos',
		rotulo: 'Tópicos',
		caminho: '/topicos',
		icone: 'topicos',
		resumo:
			'Os tópicos do corpus, agrupados em macrotemas, com palavras-chave, documentos representativos e a evolução de cada um ao longo dos anos.',
		arquivos: ['topicos', 'documentos'],
		recorte: true
	},
	{
		id: 'classificacao',
		rotulo: 'Classificação',
		caminho: '/classificacao',
		icone: 'classificacao',
		resumo:
			'Como os resumos foram codificados segundo o codebook: a distribuição de cada variável, os cruzamentos e o trecho literal que sustenta cada código.',
		arquivos: ['codebook', 'classificacoes', 'documentos'],
		recorte: true
	},
	{
		id: 'geografia',
		rotulo: 'Geografia',
		caminho: '/geografia',
		icone: 'geografia',
		resumo:
			'Onde a produção acontece: documentos por UF, país e instituição, com contagem fracionária das afiliações.',
		arquivos: ['afiliacoes', 'documentos'],
		recorte: true
	},
	{
		id: 'validacao',
		rotulo: 'Validação',
		caminho: '/validacao',
		icone: 'validacao',
		resumo:
			'Quanto a classificação do modelo concorda com uma codificação de referência (de uma pessoa ou de outro modelo): concordância, kappa, matrizes de confusão e as divergências para revisar.',
		arquivos: ['validacao', 'codebook']
	},
	{
		id: 'redes',
		rotulo: 'Redes',
		caminho: '/redes',
		icone: 'redes',
		resumo:
			'Quem escreve com quem: a coautoria entre pessoas, a colaboração entre instituições e entre estados, e as obras que o corpus mais cita.',
		arquivos: ['redes', 'citacoes'],
		recorte: true
	},
	{
		id: 'projeto',
		rotulo: 'Projeto',
		caminho: '/projeto',
		icone: 'projeto',
		resumo:
			'Configurar o projeto, acompanhar as etapas do pipeline e editar o codebook, direto no painel local.',
		arquivos: [],
		noSite: {
			rotulo: 'Metodologia',
			resumo:
				'Como estes dados foram gerados: fontes, recorte, modelos, sementes, durações, licenças e o que ficou de fora da publicação.'
		}
	}
];

export function secao(id: IdSecao): Secao {
	const s = SECOES.find((s) => s.id === id);
	if (!s) throw new Error(`seção desconhecida: ${id}`);
	return s;
}

/** As seções do trilho para este projeto: no site publicado, "Projeto" vira "Metodologia". */
export function secoesDoTrilho(manifesto: Pick<Manifesto, 'api'> & Partial<Pick<Manifesto, 'publicacao' | 'arquivos'>>): Secao[] {
	return SECOES.filter((s) => !s.soNoPainel || manifesto.api)
		.filter((s) => !(s.id === 'redes' && semRedesNoSite(manifesto)))
		.map((s) => (!manifesto.api && s.noSite ? { ...s, ...s.noSite } : s));
}

/**
 * Um site publicado (`mapa publicar`) sem `redes.json` (redes nunca geradas, ou desatualizadas na publicação) não
 * mostra a vista Redes: quem visita não tem o que fazer com "Rode `mapa redes`".
 */
export function semRedesNoSite(manifesto: Partial<Pick<Manifesto, 'publicacao' | 'arquivos'>>): boolean {
	return !!manifesto.publicacao && !(manifesto.arquivos ?? []).includes('redes');
}
