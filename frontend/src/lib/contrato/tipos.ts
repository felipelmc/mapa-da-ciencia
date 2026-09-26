/* eslint-disable */
/**
 * ARQUIVO GERADO: não edite à mão. Rode `npm run tipos` para regenerar.
 *
 * Tipos do contrato de dados v1, gerados a partir de:
 *   contrato/schema/afiliacoes.schema.json
 *   contrato/schema/agregados.schema.json
 *   contrato/schema/classificacoes.schema.json
 *   contrato/schema/codebook.schema.json
 *   contrato/schema/documentos.schema.json
 *   contrato/schema/fragmento.schema.json
 *   contrato/schema/manifesto.schema.json
 *   contrato/schema/revistas.schema.json
 *   contrato/schema/topicos.schema.json
 *   contrato/schema/validacao.schema.json
 * A fonte da verdade é src/mapa_da_ciencia/contrato/modelos.py.
 */

/**
 * Os arquivos do contrato de dados, por nome (o fragmento é cada `detalhes/{xx}.json`).
 */
export interface ContratoDeDados {
	afiliacoes: Afiliacoes;
	agregados: Agregados;
	classificacoes: Classificacoes;
	codebook: CodebookContrato;
	documentos: Documentos;
	fragmento: Fragmento;
	manifesto: Manifesto;
	revistas: Revistas;
	topicos: Topicos;
	validacao: Validacao;
}
/**
 * Afiliações com contagem fracionária, base da vista de geografia.
 */
export interface Afiliacoes {
	colunas: ColunasAfiliacoes;
	dicionarios: DicionariosAfiliacoes;
	n: number;
	/**
	 * Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x.
	 */
	versao_contrato?: string;
}
/**
 * Colunas da tabela longa de afiliações (uma linha por documento × instituição).
 */
export interface ColunasAfiliacoes {
	/**
	 * Índice do documento em documentos.json.
	 */
	doc: number[];
	instituicao: number[];
	pais: number[];
	/**
	 * Contagem fracionária: a soma por documento é 1.
	 */
	peso: number[];
	/**
	 * Índice em `dicionarios.uf` ou -1 (fora do Brasil ou desconhecida).
	 */
	uf: number[];
}
/**
 * Instituições, UFs e países por trás dos índices.
 */
export interface DicionariosAfiliacoes {
	instituicao: Instituicao[];
	/**
	 * Códigos ISO 3166-1 alfa-2.
	 */
	pais: string[];
	/**
	 * Siglas das UFs.
	 */
	uf: string[];
}
/**
 * Uma instituição de afiliação, já normalizada.
 */
export interface Instituicao {
	/**
	 * `ror:…` quando houver, senão um slug do nome normalizado.
	 */
	id: string;
	nome: string;
	pais: string;
	sigla?: string | null;
	uf?: string | null;
}
/**
 * Gabarito calculado no Python para testar o filtro cruzado do frontend.
 */
export interface Agregados {
	pais: {
		[k: string]: number;
	};
	/**
	 * (tópico, ano, revista, n).
	 */
	topico_ano_revista: [number, number, string, number][];
	uf: {
		[k: string]: number;
	};
	/**
	 * Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x.
	 */
	versao_contrato?: string;
}
/**
 * Resumo da classificação por codebook: modelo, cobertura e contagens por categoria.
 */
export interface Classificacoes {
	/**
	 * Fração dos documentos com classificação válida.
	 */
	cobertura: number;
	contagens: {
		[k: string]: {
			[k: string]: number;
		};
	};
	/**
	 * Fração das evidências encontradas literalmente no resumo.
	 */
	evidencia_literal: number;
	hash_codebook: string;
	modelo: string;
	/**
	 * Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x.
	 */
	versao_contrato?: string;
}
/**
 * Cópia publicada do codebook, com o hash que identifica a versão usada.
 */
export interface CodebookContrato {
	hash: string;
	instrucoes: string;
	nome: string;
	variaveis: VariavelContrato[];
	versao: string;
	/**
	 * Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x.
	 */
	versao_contrato?: string;
}
/**
 * Variável do codebook.
 */
export interface VariavelContrato {
	categorias?: CategoriaContrato[];
	id: string;
	pergunta: string;
	rotulo: string;
	tipo: 'categorica' | 'multipla' | 'booleana' | 'texto';
}
/**
 * Categoria de uma variável, como o codebook define.
 */
export interface CategoriaContrato {
	definicao: string;
	exemplos?: string[];
	rotulo: string;
	valor: string;
}
/**
 * Tabela principal: um documento por posição, com coordenadas no mapa, tópico e classificações.
 */
export interface Documentos {
	colunas: ColunasDocumentos;
	dicionarios: DicionariosDocumentos;
	n: number;
	/**
	 * Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x.
	 */
	versao_contrato?: string;
}
/**
 * Colunas da tabela de documentos (todas com `n` itens, na mesma ordem).
 */
export interface ColunasDocumentos {
	ano: number[];
	/**
	 * Índice em `dicionarios.atribuicao`: `cluster` (o HDBSCAN agrupou o documento) ou `vizinho` (o HDBSCAN o deixou sem tópico; os vizinhos o atribuíram, ou não, se `topico` = -1).
	 */
	atribuicao: number[];
	/**
	 * Ex.: `Limongi, F.; +2`.
	 */
	autores_curto: string[];
	/**
	 * Variável do codebook → índice em `dicionarios.cls[variavel]` ou -1.
	 */
	cls?: {
		[k: string]: number[];
	};
	doi: (string | null)[];
	id: string[];
	/**
	 * Índice em `dicionarios.idioma` (idioma do resumo exibido).
	 */
	idioma: number[];
	/**
	 * Índice em `dicionarios.revista`.
	 */
	revista: number[];
	titulo: string[];
	/**
	 * Id do tópico (ver topicos.json) ou -1.
	 */
	topico: number[];
	/**
	 * Índices (nesta tabela) dos 5 documentos mais próximos.
	 */
	vizinhos: number[][];
	x: number[];
	y: number[];
}
/**
 * Valores por trás dos índices das colunas categóricas.
 */
export interface DicionariosDocumentos {
	atribuicao?: ('cluster' | 'vizinho')[];
	cls?: {
		[k: string]: string[];
	};
	idioma: string[];
	revista: string[];
}
/**
 * Um dos 64 fragmentos de detalhes, carregados sob demanda.
 */
export interface Fragmento {
	documentos: {
		[k: string]: Detalhe;
	};
	fragmento: string;
	/**
	 * Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x.
	 */
	versao_contrato?: string;
}
/**
 * O que a interface mostra ao abrir um documento: resumo, autores, licença e evidências.
 */
export interface Detalhe {
	autores: string[];
	evidencias?: {
		[k: string]: Evidencia;
	};
	/**
	 * `resumo`: título e resumo no idioma de análise; `reserva`: resumo em outro idioma (não havia no de análise); `so_titulo`: o documento não tem resumo. O texto em si não é publicado.
	 */
	fonte_analise?: ('resumo' | 'reserva' | 'so_titulo') | null;
	idioma: string | null;
	/**
	 * Idioma do texto usado nos embeddings e nos tópicos.
	 */
	idioma_analise?: string | null;
	licenca: string;
	licenca_fonte: string;
	palavras_chave?: string[];
	/**
	 * None quando a licença não permite publicar o resumo.
	 */
	resumo: string | null;
	url: string | null;
}
/**
 * Valor de uma variável do codebook e o trecho do resumo que o justifica.
 */
export interface Evidencia {
	evidencia: string;
	fim?: number | null;
	/**
	 * Posição do trecho no resumo exibido (caracteres), se localizado.
	 */
	inicio?: number | null;
	status: 'literal' | 'aproximada' | 'ausente';
	valor: string | boolean | string[] | null;
}
/**
 * Índice do projeto publicado: o que existe, de onde veio e como foi gerado. É o primeiro arquivo que
 * a interface lê.
 */
export interface Manifesto {
	/**
	 * True no painel local (há API); False no site estático publicado.
	 */
	api: boolean;
	/**
	 * Arquivos do contrato presentes nesta pasta.
	 */
	arquivos: string[];
	contagens: Contagens;
	execucao: ExecucaoInfo;
	gerado_em: string;
	/**
	 * Licença → número de documentos.
	 */
	licencas?: {
		[k: string]: number;
	};
	projeto: ProjetoInfo;
	recorte: RecorteInfo;
	/**
	 * Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x.
	 */
	versao_contrato?: string;
}
/**
 * Números do corpus, usados na capa do painel.
 */
export interface Contagens {
	classificados?: number;
	com_afiliacao?: number;
	documentos: number;
	topicos?: number;
	validados?: number;
}
/**
 * Dados de reprodutibilidade da última execução de cada etapa.
 */
export interface ExecucaoInfo {
	/**
	 * Etapa → segundos da última execução.
	 */
	duracao_s?: {
		[k: string]: number;
	};
	hash_codebook?: string | null;
	/**
	 * Papel → `modelo@digest`.
	 */
	modelos?: {
		[k: string]: string;
	};
	sementes?: {
		[k: string]: number;
	};
	versao_pacote: string;
}
/**
 * Identificação do projeto.
 */
export interface ProjetoInfo {
	descricao?: string;
	nome: string;
	titulo: string;
}
/**
 * Recorte do corpus: período, fontes e idiomas.
 */
export interface RecorteInfo {
	/**
	 * @minItems 2
	 * @maxItems 2
	 */
	anos: [number, number];
	/**
	 * Ex.: ['scielo:scl', 'openalex'].
	 */
	fontes: string[];
	idioma_analise: string;
	idioma_exibicao: string;
}
/**
 * Revistas presentes no corpus, com o número de documentos de cada uma.
 */
export interface Revistas {
	revistas: Revista[];
	/**
	 * Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x.
	 */
	versao_contrato?: string;
}
/**
 * Uma revista do corpus.
 */
export interface Revista {
	areas?: string[];
	/**
	 * Acrônimo no SciELO, ex.: `dados`.
	 */
	id: string;
	issn: string;
	n: number;
	titulo: string;
}
/**
 * Tópicos e macrotemas do corpus, com as séries por ano.
 */
export interface Topicos {
	anos: number[];
	estabilidade_ari: number | null;
	macrotemas: Macrotema[];
	outliers: Outliers;
	parametros: {
		[k: string]: number | string;
	};
	topicos: Topico[];
	total_por_ano: number[];
	/**
	 * Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x.
	 */
	versao_contrato?: string;
}
/**
 * Agrupamento de tópicos próximos, usado para a cor e a navegação.
 */
export interface Macrotema {
	cor: string;
	id: number;
	rotulo: string;
	topicos: number[];
}
/**
 * Documentos que o agrupamento não encaixou em nenhum tópico.
 */
export interface Outliers {
	/**
	 * Documentos que o HDBSCAN deixou sem tópico.
	 */
	n: number;
	/**
	 * Documentos sem tópico no HDBSCAN, por ano, alinhado a `anos`.
	 */
	por_ano?: number[];
	/**
	 * Quantos deles foram atribuídos ao tópico mais próximo.
	 */
	reatribuidos: number;
}
/**
 * Um tópico: rótulo e descrição escritos pelo LLM, palavras-chave, cor estável e série no tempo.
 */
export interface Topico {
	/**
	 * @minItems 2
	 * @maxItems 2
	 */
	centroide: [number, number];
	cor: string;
	descricao: string;
	id: number;
	macro_id: number;
	n: number;
	/**
	 * Documentos do núcleo, que o HDBSCAN agrupou (os demais foram reatribuídos por vizinhança).
	 */
	n_nucleo?: number | null;
	palavras_chave: [string, number][];
	por_revista: {
		[k: string]: number;
	};
	/**
	 * Ids de documentos.
	 */
	representativos: string[];
	rotulo: string;
	/**
	 * Quem escreveu o rótulo: o modelo de linguagem, as palavras-chave ou você (rotulos.yaml).
	 */
	rotulo_fonte?: 'llm' | 'palavras' | 'manual';
	serie: Serie;
}
/**
 * Série temporal de um tópico.
 */
export interface Serie {
	/**
	 * Documentos por ano, alinhado a `anos`.
	 */
	n: number[];
	/**
	 * Proporção do total do ano.
	 */
	prop: number[];
}
/**
 * Resultados da validação da classificação contra codificação humana.
 */
export interface Validacao {
	amostra: AmostraInfo;
	divergencias: Divergencia[];
	metricas: MetricaVariavel[];
	modelos: string[];
	/**
	 * Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x.
	 */
	versao_contrato?: string;
}
/**
 * Como a amostra de validação foi sorteada.
 */
export interface AmostraInfo {
	estratificar_por: string;
	n: number;
	semente: number;
}
/**
 * Um caso em que humano e modelo discordam, para arbitragem.
 */
export interface Divergencia {
	doc: string;
	evidencia: string;
	humano: string;
	modelo: string;
	variavel: string;
}
/**
 * Concordância entre humano e modelo (ou entre dois modelos) numa variável.
 */
export interface MetricaVariavel {
	alfa: number | null;
	/**
	 * Ex.: `humano × qwen3.5:9b`.
	 */
	comparacao: string;
	concordancia: number;
	kappa: number | null;
	kappa_ic95: [number, number] | null;
	matriz: Matriz;
	n: number;
	pabak: number | null;
	variavel: string;
}
/**
 * Matriz de confusão entre a codificação humana e a do modelo.
 */
export interface Matriz {
	rotulos: string[];
	/**
	 * Linhas = codificação humana; colunas = modelo.
	 */
	valores: number[][];
}
