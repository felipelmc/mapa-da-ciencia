/**
 * As seções do app, na ordem do trilho lateral. É o lugar único para rótulo, rota, ícone,
 * a frase que descreve cada vista e o marco em que ela chega.
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
	/** Quando a vista fica pronta, para o estado vazio ("Chega no marco M3"). */
	chegada: string;
	/** Arquivos do contrato que a vista usa. O estado vazio mostra quais existem. */
	arquivos: NomeArquivo[];
	/** Aparece no trilho, mas desativada, com um selo (ex.: "v2"). */
	selo?: string;
	/** Só aparece quando `manifesto.api` é verdadeiro (painel local). */
	soNoPainel?: boolean;
	/** A vista ocupa toda a área de conteúdo, sem margens nem largura máxima (o mapa). */
	telaCheia?: boolean;
}

// Os marcos seguem o plano do projeto (docs/desenvolvimento/index.md): mapa no M3;
// tópicos no tempo e geografia no M4; classificação e validação no M5.
export const SECOES: readonly Secao[] = [
	{
		id: 'inicio',
		rotulo: 'Início',
		caminho: '/',
		icone: 'inicio',
		resumo: 'O corpus em números: documentos, tópicos, revistas, período e macrotemas.',
		chegada: 'no marco M1',
		arquivos: ['manifesto', 'revistas', 'topicos']
	},
	{
		id: 'mapa',
		rotulo: 'Mapa',
		caminho: '/mapa',
		icone: 'mapa',
		resumo:
			'Cada documento vira um ponto, e textos parecidos ficam perto. Dá para filtrar por ano, revista e tópico, colorir por categoria e selecionar grupos com o laço.',
		chegada: 'no marco M3',
		arquivos: ['documentos', 'topicos'],
		telaCheia: true
	},
	{
		id: 'topicos',
		rotulo: 'Tópicos',
		caminho: '/topicos',
		icone: 'topicos',
		resumo:
			'Os tópicos do corpus, agrupados em macrotemas, com palavras-chave, documentos representativos e a evolução de cada um ao longo dos anos.',
		chegada: 'no marco M4',
		arquivos: ['topicos', 'documentos']
	},
	{
		id: 'classificacao',
		rotulo: 'Classificação',
		caminho: '/classificacao',
		icone: 'classificacao',
		resumo:
			'Como os resumos foram codificados segundo o codebook: a distribuição de cada variável, os cruzamentos e o trecho literal que sustenta cada código.',
		chegada: 'no marco M5',
		arquivos: ['codebook', 'classificacoes', 'documentos']
	},
	{
		id: 'geografia',
		rotulo: 'Geografia',
		caminho: '/geografia',
		icone: 'geografia',
		resumo:
			'Onde a produção acontece: documentos por UF, país e instituição, com contagem fracionária das afiliações.',
		chegada: 'no marco M4',
		arquivos: ['afiliacoes', 'documentos']
	},
	{
		id: 'validacao',
		rotulo: 'Validação',
		caminho: '/validacao',
		icone: 'validacao',
		resumo:
			'Quanto a classificação do modelo concorda com a codificação humana: concordância, kappa, matrizes de confusão e as divergências para revisar.',
		chegada: 'no marco M5',
		arquivos: ['validacao', 'codebook']
	},
	{
		id: 'redes',
		rotulo: 'Redes',
		caminho: '/redes',
		icone: 'redes',
		resumo: 'Redes de coautoria e de citação entre documentos, autores e instituições.',
		chegada: 'na versão 2',
		arquivos: [],
		selo: 'v2'
	},
	{
		id: 'projeto',
		rotulo: 'Projeto',
		caminho: '/projeto',
		icone: 'projeto',
		resumo:
			'Configurar o projeto, acompanhar as etapas do pipeline e editar o codebook, direto no painel local.',
		chegada: 'no marco M6',
		arquivos: [],
		soNoPainel: true
	}
];

export function secao(id: IdSecao): Secao {
	const s = SECOES.find((s) => s.id === id);
	if (!s) throw new Error(`seção desconhecida: ${id}`);
	return s;
}

/** As seções do trilho para este projeto: "Projeto" só existe no painel local. */
export function secoesDoTrilho(manifesto: Pick<Manifesto, 'api'>): Secao[] {
	return SECOES.filter((s) => !s.soNoPainel || manifesto.api);
}
