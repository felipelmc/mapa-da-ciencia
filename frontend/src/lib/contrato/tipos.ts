/* eslint-disable */
/**
 * ARQUIVO GERADO: não edite à mão. Rode `npm run tipos` para regenerar.
 *
 * Tipos do contrato de dados v1, gerados a partir de:
 *   contrato/schema/afiliacoes.schema.json
 *   contrato/schema/agregados.schema.json
 *   contrato/schema/citacoes.schema.json
 *   contrato/schema/classificacoes.schema.json
 *   contrato/schema/codebook.schema.json
 *   contrato/schema/documentos.schema.json
 *   contrato/schema/fragmento.schema.json
 *   contrato/schema/manifesto.schema.json
 *   contrato/schema/redes.schema.json
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
	citacoes: Citacoes;
	classificacoes: Classificacoes;
	codebook: CodebookContrato;
	documentos: Documentos;
	fragmento: Fragmento;
	manifesto: Manifesto;
	redes: Redes;
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
 * Colunas da tabela longa de afiliações: uma linha por documento × (instituição, UF, país), pesos somados.
 */
export interface ColunasAfiliacoes {
	/**
	 * Índice do documento em documentos.json.
	 */
	doc: number[];
	/**
	 * Índice em `dicionarios.instituicao`, ou -1 quando o autor não informou afiliação.
	 */
	instituicao: number[];
	/**
	 * Índice em `dicionarios.pais` ou -1 (desconhecido).
	 */
	pais: number[];
	/**
	 * Contagem fracionária: 1 por documento, dividido entre os autores e depois entre as afiliações de cada um. A soma por documento é 1.
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
	 * Códigos ISO 3166-1 alfa-2 presentes nas afiliações.
	 */
	pais: string[];
	/**
	 * Siglas das UFs (as 27, em ordem alfabética, para índices estáveis).
	 */
	uf: string[];
}
/**
 * Uma instituição de afiliação, já normalizada.
 */
export interface Instituicao {
	/**
	 * `ror:…` quando houver, `openalex:I…` sem ROR, um apelido do projeto, ou `nao-identificada` (reservado: afiliação informada que não casou com nenhuma instituição).
	 */
	id: string;
	nome: string;
	/**
	 * ISO 3166-1 alfa-2; vazio em `nao-identificada`.
	 */
	pais: string;
	sigla?: string | null;
	uf?: string | null;
}
/**
 * Gabarito calculado no Python para testar o filtro cruzado do frontend.
 */
export interface Agregados {
	/**
	 * Pares de coautores no corpus inteiro.
	 */
	arestas_coautoria?: number;
	/**
	 * Documentos que citam cada obra do cânone.
	 */
	canone_n?: number[];
	/**
	 * Contagem fracionária por instituição.
	 */
	instituicao?: {
		[k: string]: number;
	};
	instituicao_inteiro?: {
		[k: string]: number;
	};
	/**
	 * Contagem fracionária por país (ISO alfa-2).
	 */
	pais: {
		[k: string]: number;
	};
	pais_inteiro?: {
		[k: string]: number;
	};
	/**
	 * Peso dos autores sem afiliação informada.
	 */
	sem_afiliacao?: number;
	/**
	 * Peso das afiliações de país desconhecido (inclui `sem_afiliacao`).
	 */
	sem_pais?: number;
	/**
	 * (tópico, ano, revista, n).
	 */
	topico_ano_revista: [number, number, string, number][];
	/**
	 * Contagem fracionária por UF (sigla).
	 */
	uf: {
		[k: string]: number;
	};
	/**
	 * Documentos com alguma afiliação na UF.
	 */
	uf_inteiro?: {
		[k: string]: number;
	};
	/**
	 * (UF, UF ou EX, peso, documentos) na colaboração entre estados.
	 */
	uf_pares?: [string, string, number, number][];
	/**
	 * Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x.
	 */
	versao_contrato?: string;
}
/**
 * A rede de citação pelas referências do OpenAlex e o cânone.
 */
export interface Citacoes {
	canone: ObraCitada[];
	canone_citantes: CitantesCanone;
	cobertura?: {
		[k: string]: number;
	};
	/**
	 * Citações internas de macrotema (linha) a macrotema.
	 */
	fluxo_macrotemas: number[][];
	internas: ArestasCitacao;
	/**
	 * Referências de cada documento no OpenAlex; -1: sem casamento.
	 */
	n_referencias: number[];
	/**
	 * Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x.
	 */
	versao_contrato?: string;
}
/**
 * Uma obra de fora do corpus entre as mais citadas (o cânone).
 */
export interface ObraCitada {
	ano: number | null;
	/**
	 * Até três autores.
	 */
	autores: string[];
	doi: string | null;
	/**
	 * Outras edições somadas a esta.
	 */
	edicoes?: string[];
	/**
	 * Id do OpenAlex (`W…`).
	 */
	id: string;
	/**
	 * Documentos do corpus que a citam.
	 */
	n: number;
	tipo: string | null;
	titulo: string | null;
	veiculo: string | null;
}
export interface CitantesCanone {
	doc: number[];
	/**
	 * Índice em `canone`.
	 */
	obra: number[];
}
/**
 * Citações dentro do corpus: índices de documentos (quem cita → quem é citado).
 */
export interface ArestasCitacao {
	de: number[];
	para: number[];
}
/**
 * Resumo da classificação por codebook: modelo, cobertura e contagens por categoria.
 */
export interface Classificacoes {
	classificados?: number;
	/**
	 * Fração dos documentos com classificação válida.
	 */
	cobertura: number;
	/**
	 * Variável → valor → documentos. Nas de múltipla escolha, cada categoria conta à parte; as de texto ficam de fora.
	 */
	contagens: {
		[k: string]: {
			[k: string]: number;
		};
	};
	/**
	 * Documentos com resumo, que podiam ser classificados.
	 */
	documentos?: number;
	/**
	 * Fração das evidências encontradas literalmente no resumo.
	 */
	evidencia_literal: number;
	hash_codebook: string;
	json_valido_na_primeira?: number | null;
	modelo: string;
	/**
	 * A classificação ainda não cobre todos os documentos com resumo.
	 */
	parcial?: boolean;
	por_variavel?: {
		[k: string]: VariavelClassificada;
	};
	sem_resumo?: number;
	/**
	 * Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x.
	 */
	versao_contrato?: string;
}
/**
 * Como uma variável saiu na classificação.
 */
export interface VariavelClassificada {
	/**
	 * Status → fração das evidências, sem as dispensadas.
	 */
	evidencia?: {
		[k: string]: number;
	};
	/**
	 * Documentos com resposta nesta variável.
	 */
	n: number;
	/**
	 * Fração das respostas sem informação (`nao_informado`, `nao_se_aplica` ou falso).
	 */
	sem_informacao: number;
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
	/**
	 * Variável → decisão do júri (só nos documentos da amostra, com júri).
	 */
	juri?: {
		[k: string]: DecisaoJuri;
	};
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
	/**
	 * Onde o trecho foi localizado; `inicio` e `fim` são posições nesse texto.
	 */
	campo?: ('titulo' | 'resumo') | null;
	evidencia: string;
	fim?: number | null;
	/**
	 * Posição do trecho no resumo exibido, se localizado, em pontos de código Unicode (como o Python conta; em JavaScript, converta para UTF-16).
	 */
	inicio?: number | null;
	/**
	 * `literal`: o trecho está no texto; `aproximada`: quase (90% dos caracteres); `ausente`: não está; `dispensada`: vazia numa resposta sem informação.
	 */
	status: 'literal' | 'aproximada' | 'ausente' | 'dispensada';
	valor: string | boolean | string[] | null;
}
/**
 * Como o júri decidiu uma variável de um documento da amostra de validação.
 */
export interface DecisaoJuri {
	etapa: 'unanime' | 'maioria' | 'deliberacao' | 'sem_maioria';
	/**
	 * A justificativa do supervisor (vazia no site publicado).
	 */
	justificativa?: string | null;
	/**
	 * Quem arbitrou, quando não houve maioria.
	 */
	supervisor?: string | null;
	/**
	 * A decisão final (com o supervisor, se ele decidiu).
	 */
	valor: string | boolean | string[] | null;
	valor_sem_supervisor: string | boolean | string[] | null;
	/**
	 * A deliberação mudou a decisão (outra maioria, ou antes não havia).
	 */
	virou?: boolean;
	votos?: VotoJuri[];
}
/**
 * O voto de um membro do júri numa variável, numa rodada (1: votação; 2: deliberação).
 */
export interface VotoJuri {
	/**
	 * Vazia no site publicado quando a licença do resumo não é aberta.
	 */
	evidencia: string;
	membro: string;
	/**
	 * Na rodada 2: o membro mudou de valor na deliberação.
	 */
	revisou?: boolean;
	rodada: 1 | 2;
	status: 'literal' | 'aproximada' | 'ausente' | 'dispensada';
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
	/**
	 * Presente só no site publicado (`mapa publicar`).
	 */
	publicacao?: PublicacaoInfo | null;
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
	/**
	 * Documentos com ao menos uma instituição identificada.
	 */
	com_instituicao?: number;
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
 * O que o `mapa publicar` fez: quando, e quantos resumos foram ou não publicados.
 */
export interface PublicacaoInfo {
	em: string;
	/**
	 * Resumos com licença Creative Commons, publicados sem alteração.
	 */
	resumos_publicados: number;
	/**
	 * Resumos que ficaram de fora (licença não aberta, desconhecida ou `--sem-resumos`).
	 */
	resumos_retirados: number;
	sem_resumos?: boolean;
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
 * Coautoria (pessoas), colaboração entre instituições e as séries da colaboração.
 */
export interface Redes {
	autorias: AutoriasRede;
	colaboracao?: ColaboracaoAno[];
	comunidades?: ComunidadeRede[];
	instituicoes?: ColunasInstituicoesRede | null;
	metricas?: {
		[k: string]: MetricasRede;
	};
	parametros?: {
		[k: string]: unknown;
	};
	pessoas: ColunasPessoas;
	/**
	 * Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x.
	 */
	versao_contrato?: string;
}
/**
 * Quem escreveu cada documento: pares (índice do documento em `documentos.json`, índice da pessoa).
 */
export interface AutoriasRede {
	doc: number[];
	pessoa: number[];
}
/**
 * A colaboração num ano, em frações dos documentos do ano.
 */
export interface ColaboracaoAno {
	ano: number;
	autores_medio: number;
	com_coautoria: number;
	/**
	 * Brasil e exterior no mesmo documento.
	 */
	com_exterior?: number | null;
	/**
	 * Duas ou mais instituições identificadas.
	 */
	com_instituicoes?: number | null;
	documentos: number;
	/**
	 * Duas ou mais UFs brasileiras.
	 */
	entre_ufs?: number | null;
}
export interface ComunidadeRede {
	documentos: number;
	id: number;
	/**
	 * Macrotema mais frequente nos documentos da comunidade.
	 */
	macro: number | null;
	/**
	 * Nós da comunidade.
	 */
	n: number;
	rede: 'coautoria' | 'instituicoes';
	/**
	 * Os dois tópicos mais frequentes (a comunidade não recebe nome de pessoa).
	 */
	rotulo: string;
	/**
	 * Os tópicos mais frequentes, em ordem.
	 */
	topicos: number[];
}
/**
 * As instituições que colaboraram com outra, com o desenho da rede (os ids são os de `afiliacoes.json`).
 */
export interface ColunasInstituicoesRede {
	comunidade: number[];
	grau: number[];
	id: string[];
	x: number[];
	y: number[];
}
export interface MetricasRede {
	agrupamento: number;
	arestas: number;
	componentes: number;
	densidade: number;
	fracao_maior: number;
	grau_medio: number;
	maior_componente: number;
	modularidade: number | null;
	nos: number;
}
/**
 * As pessoas (autores identificados), em colunas. `x` e `y` só para quem teve coautor (o desenho da rede).
 */
export interface ColunasPessoas {
	/**
	 * Índice em `comunidades` da rede de coautoria; -1 nas pequenas.
	 */
	comunidade: number[];
	documentos: number[];
	/**
	 * Coautores distintos.
	 */
	grau: number[];
	/**
	 * Id publicado (um hash curto; o site não publica ORCIDs).
	 */
	id: string[];
	nome: string[];
	x: (number | null)[];
	y: (number | null)[];
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
	metodo_tendencia?: MetodoTendencia | null;
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
	descricao?: string;
	id: number;
	rotulo: string;
	/**
	 * Soma das séries dos tópicos do macrotema.
	 */
	serie?: Serie | null;
	tendencia?: Tendencia | null;
	topicos: number[];
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
 * Tendência da participação anual no período inteiro, sem filtros (ADR 0009): o gabarito para o painel.
 */
export interface Tendencia {
	anos?: [number, number] | null;
	direcao: 'alta' | 'queda' | 'estavel' | 'insuficiente';
	/**
	 * φ de Pearson (1 na binomial pura).
	 */
	dispersao?: number | null;
	/**
	 * Erro-padrão da inclinação, já corrigido pela dispersão.
	 */
	erro_padrao?: number | null;
	ic95?: [number, number] | null;
	/**
	 * Inclinação na escala logit, por ano.
	 */
	inclinacao?: number | null;
	/**
	 * Por que não há tendência, quando é `insuficiente`.
	 */
	motivo?: ('poucos_anos' | 'poucos_documentos' | 'sem_variacao' | 'sem_convergencia') | null;
	/**
	 * Variação em pontos percentuais no período.
	 */
	pp_periodo?: number | null;
	pp_por_ano?: number | null;
	/**
	 * Participação ajustada no último ano com documentos.
	 */
	prop_fim?: number | null;
	/**
	 * Participação ajustada no primeiro ano com documentos.
	 */
	prop_inicio?: number | null;
}
/**
 * Como a tendência é calculada. O painel lê daqui os parâmetros para recalcular com os filtros.
 */
export interface MetodoTendencia {
	anos_minimos?: number;
	dispersao?: 'quase' | 'binomial';
	docs_minimos?: number;
	modelo?: 'logistica_binomial';
	nivel?: number;
	z?: number;
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
	 * Documentos que o HDBSCAN deixou de fora, por ano (inclui os reatribuídos depois), alinhado a `anos`.
	 */
	por_ano?: number[];
	/**
	 * Quantos deles foram atribuídos ao tópico mais próximo.
	 */
	reatribuidos: number;
	/**
	 * Documentos que ficaram sem tópico (−1) no fim, por ano.
	 */
	sem_topico_por_ano?: number[];
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
	tendencia?: Tendencia | null;
}
/**
 * Resultados da validação da classificação: concordância por variável e por par de participantes.
 */
export interface Validacao {
	amostra: AmostraInfo;
	/**
	 * Participantes, com o tipo.
	 */
	codificadores?: Participante[];
	comparacoes_modelos?: ComparacaoModelos[];
	divergencias: Divergencia[];
	/**
	 * Modelo → fração das evidências literais na amostra.
	 */
	evidencia_literal?: {
		[k: string]: number;
	};
	hash_codebook?: string | null;
	/**
	 * O júri de modelos locais, quando o projeto tem um.
	 */
	juri?: ResumoJuri | null;
	metricas: MetricaVariavel[];
	modelo_principal?: string | null;
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
 * Quem respondeu na amostra: um codificador (`humano` ou `referencia`, que não é uma pessoa) ou um modelo.
 */
export interface Participante {
	/**
	 * Família de modelo, quando se conhece (ver `circular`).
	 */
	familia?: string | null;
	/**
	 * Documentos da amostra com resposta.
	 */
	n: number;
	nome: string;
	tipo: 'humano' | 'referencia' | 'modelo';
}
/**
 * McNemar exato entre dois modelos, contra a mesma referência, numa variável.
 */
export interface ComparacaoModelos {
	acertos_a: number;
	acertos_b: number;
	modelo_a: string;
	modelo_b: string;
	n: number;
	p: number;
	referencia: string;
	variavel: string;
}
/**
 * Um caso em que um codificador de referência e o modelo principal discordam, para arbitragem.
 */
export interface Divergencia {
	codificador?: string;
	doc: string;
	/**
	 * Trecho que o modelo citou.
	 */
	evidencia: string;
	/**
	 * Valor dado pelo codificador (o nome do campo vem da versão 1.0).
	 */
	humano: string;
	/**
	 * O codificador marcou a resposta como incerta.
	 */
	incerto?: boolean;
	modelo: string;
	status?: ('literal' | 'aproximada' | 'ausente' | 'dispensada') | null;
	variavel: string;
}
/**
 * O júri de modelos locais na amostra: estágios, deliberação, concordância por estágio e auditoria.
 */
export interface ResumoJuri {
	auditoria?: AuditoriaJuri | null;
	/**
	 * Estágio → {n, acertos} contra a referência, com a decisão do júri sem o supervisor (no estágio `sem_maioria`, o voto do primeiro membro).
	 */
	concordancia_por_etapa?: {
		[k: string]: {
			[k: string]: number;
		};
	};
	/**
	 * Nas decisões sem maioria arbitradas, a concordância com a escolha do supervisor.
	 */
	concordancia_supervisor?: ConcordanciaSupervisor | null;
	/**
	 * Membro → {votos, mudou, para_referencia, contra}: votos revistos na deliberação e a direção.
	 */
	deliberacao?: {
		[k: string]: {
			[k: string]: number;
		};
	};
	documentos: number;
	/**
	 * Variável → estágio → decisões.
	 */
	etapas: {
		[k: string]: {
			[k: string]: number;
		};
	};
	familia_supervisor: string | null;
	membros: string[];
	/**
	 * O codificador tomado como referência nas contagens.
	 */
	referencia: string | null;
	supervisor: string | null;
	/**
	 * Variável → decisões que a deliberação mudou.
	 */
	virou?: {
		[k: string]: number;
	};
}
/**
 * A conferência, pelo supervisor, de uma amostra das decisões unânimes do júri.
 */
export interface AuditoriaJuri {
	erros: number;
	/**
	 * Intervalo de Wilson de 95% da taxa de erro.
	 */
	ic95: [number, number] | null;
	n: number;
	/**
	 * Variável → (erros, n).
	 */
	por_variavel?: {
		/**
		 * @minItems 2
		 * @maxItems 2
		 */
		[k: string]: [number, number];
	};
	taxa: number | null;
}
/**
 * A concordância com a referência nas decisões sem maioria que o supervisor arbitrou, com a escolha dele.
 */
export interface ConcordanciaSupervisor {
	acertos: number;
	/**
	 * O supervisor e a referência são da mesma família: não é medida independente.
	 */
	circular: boolean;
	n: number;
}
/**
 * Concordância entre dois participantes (codificador × modelo, codificadores ou modelos) numa variável.
 * Nas de múltipla escolha, `variavel` é `id:categoria` (uma variável sim/não por categoria).
 */
export interface MetricaVariavel {
	alfa: number | null;
	/**
	 * Os dois participantes são da mesma família de modelo (a referência e o supervisor do júri, por exemplo): um limite superior, e não uma medida independente.
	 */
	circular?: boolean;
	/**
	 * Ex.: `claude-opus × qwen3.5:9b` (referência primeiro).
	 */
	comparacao: string;
	comparado?: string;
	concordancia: number | null;
	kappa: number | null;
	kappa_ic95: [number, number] | null;
	matriz: Matriz;
	n: number;
	pabak: number | null;
	por_classe?: MetricaClasse[];
	/**
	 * Participante tomado como referência (linhas da matriz).
	 */
	referencia?: string;
	variavel: string;
}
/**
 * Matriz de confusão entre dois participantes.
 */
export interface Matriz {
	rotulos: string[];
	/**
	 * Linhas = a referência do par; colunas = o outro participante.
	 */
	valores: number[][];
}
/**
 * Precisão, revocação e F1 de uma categoria, tomando o primeiro do par como referência.
 */
export interface MetricaClasse {
	f1: number | null;
	precisao: number | null;
	revocacao: number | null;
	rotulo: string;
	/**
	 * Quantas vezes a referência deu esta categoria.
	 */
	suporte: number;
}
