<script lang="ts">
	/**
	 * As redes de nós da vista Redes: a coautoria (pessoas) e as instituições. O desenho é o do Python, para o corpus
	 * inteiro; o recorte só acende e apaga (quem não tem documento nele fica esmaecido, e cada aresta ganha a faixa do
	 * peso que tem no recorte). Ao lado, a colaboração por ano, que ignora o próprio filtro de anos (mostra o período
	 * inteiro, com o intervalo do recorte em destaque), como o fluxo dos tópicos.
	 */
	import type { ComunidadeRede } from '$lib/contrato/tipos';
	import type { TabelaAfiliacoes } from '$lib/dados/afiliacoes';
	import { dobrar } from '$lib/dados/busca';
	import type { Aberto } from '$lib/dados/corpus';
	import type { TabelaRedes } from '$lib/dados/redes';
	import { mudarFiltros } from '$lib/estado/filtros';
	import { escreverFiltros, recorteDe, rota, type Filtros } from '$lib/estado/url';
	import { contar, formatarDecimal, formatarInteiro, formatarPorcentagem } from '$lib/formato';
	import Figura from '$lib/graficos/Figura.svelte';
	import { nomePais } from '$lib/geografia/lugares';
	import { untrack } from 'svelte';
	import BuscaNo, { type ItemBusca } from './BuscaNo.svelte';
	import CartaoNo, { type Parceiro } from './CartaoNo.svelte';
	import {
		arestasCoautoria,
		arestasInstituicoes,
		contarNoRecorte,
		documentosPorInstituicao,
		faixasNoRecorte,
		forcaDe,
		grauDe,
		LIMITES_FAIXAS,
		parceiros,
		renumerar,
		type Arestas,
		type Passa
	} from './calculo';
	import { recomecarDebug } from './debug';
	import Grafo, { TRACO_DAS_FAIXAS, type RotuloGrafo } from './Grafo.svelte';
	import Colaboracao from './Colaboracao.svelte';

	let {
		rede,
		aberto,
		redes: r,
		afiliacoes: af,
		filtros,
		falhas
	}: {
		rede: 'coautoria' | 'instituicoes';
		aberto: Aberto;
		redes: TabelaRedes;
		afiliacoes: TabelaAfiliacoes | null;
		filtros: Filtros;
		falhas: Uint8Array;
	} = $props();

	const em = '/redes';
	// a vista remonta este componente a cada troca de rede ({#key}): o estado da depuração recomeça aqui
	const debug = recomecarDebug(untrack(() => rede));
	const t = $derived(aberto.tabela);
	const pessoas = $derived(rede === 'coautoria');
	const RAIO = $derived(pessoas ? { min: 1.8, max: 8 } : { min: 3, max: 14 });
	const MAXIMO_ROTULOS = 8;

	const noRecorte = $derived(aberto.cubo.contar(falhas));
	const passa = $derived<Passa>(noRecorte === t.n ? null : (d) => falhas[d] === 0);

	// ---- os nós e as arestas das duas redes, numa forma só
	interface Nos {
		n: number;
		ids: string[];
		nomes: string[];
		x: Float64Array;
		y: Float64Array;
		comunidade: Int32Array;
		comunidades: Map<number, ComunidadeRede>;
		grau: Int32Array;
		docsCorpus: Int32Array;
		indice: Map<string, number>;
		/** Lugar (instituições) para a dica, o cartão e a busca. */
		lugar: (i: number) => string;
		/** Índice da instituição em `afiliacoes.json` (−1 nas pessoas). */
		naAfiliacao: Int32Array;
	}

	const nos = $derived.by((): Nos => {
		if (pessoas) {
			const p = r.pessoas;
			return { ...p, comunidades: r.comunidades.coautoria, docsCorpus: p.documentos, lugar: () => '', naAfiliacao: new Int32Array(p.n).fill(-1) };
		}
		const inst = r.instituicoes!;
		const a = af!;
		const naAfiliacao = Int32Array.from(inst.ids, (id) => a.indiceInst.get(id) ?? -1);
		const porInst = documentosPorInstituicao(a, null);
		const dicionario = (i: number) => (naAfiliacao[i] >= 0 ? a.instituicoes[naAfiliacao[i]] : null);
		return {
			...inst,
			nomes: inst.ids.map((id, i) => {
				const x = dicionario(i);
				return x ? (x.sigla ? `${x.nome} (${x.sigla})` : x.nome) : id;
			}),
			comunidades: r.comunidades.instituicoes,
			docsCorpus: Int32Array.from(naAfiliacao, (k) => (k >= 0 ? porInst[k] : 0)),
			lugar: (i) => {
				const x = dicionario(i);
				return x ? [x.uf, x.pais ? nomePais(x.pais) : null].filter(Boolean).join(', ') : '';
			},
			naAfiliacao
		};
	});

	/** Da numeração de `afiliacoes.json` para a dos nós desenhados. */
	const paraNo = $derived.by(() => {
		if (pessoas || !af) return new Int32Array(0);
		const m = new Int32Array(af.instituicoes.length).fill(-1);
		nos.naAfiliacao.forEach((k, i) => k >= 0 && (m[k] = i));
		return m;
	});
	const arestasDe = (p: Passa): Arestas => (pessoas ? arestasCoautoria(r, p) : renumerar(arestasInstituicoes(af!, p), paraNo));
	const corpus = $derived(arestasDe(null));
	const recorte = $derived(passa ? arestasDe(passa) : corpus);
	const faixas = $derived(faixasNoRecorte(corpus, recorte, nos.n));
	const docsRecorte = $derived.by(() => {
		if (pessoas) return contarNoRecorte(r.docsDaPessoa, passa);
		const porInst = documentosPorInstituicao(af!, passa);
		return Int32Array.from(nos.naAfiliacao, (k) => (k >= 0 ? porInst[k] : 0));
	});
	const ativo = $derived(Uint8Array.from(docsRecorte, (n) => (n > 0 ? 1 : 0)));

	// ---- componentes (pelas arestas do corpus): as duplas e os trios isolados ficam escondidos por padrão, para o
	// desenho enquadrar o maior componente e os grupos médios, onde estão as comunidades
	const MINIMO_VISIVEL = 4;
	const tamanhoDoComponente = $derived.by(() => {
		const pai = Int32Array.from({ length: nos.n }, (_, i) => i);
		const achar = (i: number): number => {
			while (pai[i] !== i) i = pai[i] = pai[pai[i]];
			return i;
		};
		for (let k = 0; k < corpus.n; k += 1) {
			const [a, b] = [achar(corpus.a[k]), achar(corpus.b[k])];
			if (a !== b) pai[Math.max(a, b)] = Math.min(a, b);
		}
		const tamanho = new Map<number, number>();
		for (let i = 0; i < nos.n; i += 1) tamanho.set(achar(i), (tamanho.get(achar(i)) ?? 0) + 1);
		return Int32Array.from({ length: nos.n }, (_, i) => tamanho.get(achar(i))!);
	});
	// na URL (`duplas=1`), como o resto da vista: o link reproduz a tela
	const mostrarPequenos = $derived(filtros.duplas);
	const mostrarDuplas = (sim: boolean) => mudarFiltros({ duplas: sim }, { em });
	const escondidos = $derived.by(() => {
		let n = 0;
		for (let i = 0; i < nos.n; i += 1) if (Number.isFinite(nos.x[i]) && tamanhoDoComponente[i] < MINIMO_VISIVEL) n += 1;
		return n;
	});
	// um nó aberto num grupo pequeno (pela busca ou pelo link) mostra os grupos pequenos
	$effect(() => {
		const i = selecionado;
		if (i !== null && tamanhoDoComponente[i] < MINIMO_VISIVEL && !untrack(() => filtros.duplas)) mostrarDuplas(true);
	});
	const visivel = (i: number) => mostrarPequenos || tamanhoDoComponente[i] >= MINIMO_VISIVEL;
	const xVisivel = $derived(Float64Array.from(nos.x, (v, i) => (visivel(i) ? v : NaN)));
	const yVisivel = $derived(Float64Array.from(nos.y, (v, i) => (visivel(i) ? v : NaN)));
	const grauRecorte = $derived(grauDe(recorte, nos.n));
	const forcaRecorte = $derived(forcaDe(recorte, nos.n));

	// ---- aparência: raio pela raiz dos documentos do corpus (não muda com o recorte), cor pelo macrotema da comunidade
	const raio = $derived.by(() => {
		const maximo = Math.sqrt(Math.max(1, ...nos.docsCorpus));
		return Float32Array.from(nos.docsCorpus, (n) => RAIO.min + ((RAIO.max - RAIO.min) * Math.sqrt(n)) / maximo);
	});
	const corDoMacro = $derived(new Map(aberto.topicos.macrotemas.map((m) => [m.id, m.cor])));
	const corDaComunidade = (c: number) => {
		const macro = nos.comunidades.get(c)?.macro;
		return macro !== null && macro !== undefined ? (corDoMacro.get(macro) ?? null) : null;
	};
	const cores = $derived(Array.from(nos.comunidade, corDaComunidade));
	const desenhados = $derived(Array.from(nos.x).filter(Number.isFinite).length);
	const desenhadosNoRecorte = $derived.by(() => {
		let n = 0;
		for (let i = 0; i < nos.n; i += 1) if (ativo[i] && Number.isFinite(nos.x[i])) n += 1;
		return n;
	});
	/** O rótulo da comunidade no desenho: o tópico mais frequente, curto (o rótulo inteiro fica na lista e no cartão). */
	const rotuloCurto = (rotulo: string) => {
		const primeiro = rotulo.split(' · ')[0];
		return primeiro.length > 34 ? `${primeiro.slice(0, 33).trimEnd()}…` : primeiro;
	};

	// rótulos das maiores comunidades, no centro dos seus nós
	const rotulos = $derived.by((): RotuloGrafo[] => {
		const soma = new Map<number, [number, number, number]>();
		for (let i = 0; i < nos.n; i += 1) {
			const c = nos.comunidade[i];
			if (c < 0 || !Number.isFinite(xVisivel[i])) continue;
			const [sx, sy, n] = soma.get(c) ?? [0, 0, 0];
			soma.set(c, [sx + nos.x[i], sy + nos.y[i], n + 1]);
		}
		const escolhidas = [...nos.comunidades.values()]
			.filter((c) => (soma.get(c.id)?.[2] ?? 0) >= 3)
			.sort((a, b) => b.n - a.n)
			.slice(0, MAXIMO_ROTULOS);
		// duas comunidades com o mesmo primeiro tópico levam o segundo, para os rótulos não se repetirem
		const primeiros = escolhidas.map((c) => rotuloCurto(c.rotulo));
		return escolhidas.map((c, k) => {
			const [sx, sy, n] = soma.get(c.id)!;
			const repetido = primeiros.filter((t) => t === primeiros[k]).length > 1;
			const texto = repetido ? rotuloCurto(c.rotulo.split(' · ').slice(1).join(' · ') || c.rotulo) : primeiros[k];
			return { id: String(c.id), texto, x: sx / n, y: sy / n };
		});
	});

	// ---- o nó aberto (pela URL)
	const selecionado = $derived(filtros.no !== null ? (nos.indice.get(filtros.no) ?? null) : null);
	const abrir = (i: number | null) => mudarFiltros({ no: i === null ? null : nos.ids[i] }, { em });
	const documentosDo = (i: number): number[] => {
		if (pessoas) {
			const saida: number[] = [];
			for (let k = r.docsDaPessoa.inicio[i]; k < r.docsDaPessoa.inicio[i + 1]; k += 1) {
				const d = r.docsDaPessoa.itens[k];
				if (!passa || passa(d)) saida.push(d);
			}
			return saida;
		}
		const alvo = nos.naAfiliacao[i];
		// uma instituição que afiliacoes.json não conhece não tem documentos (−1 é o autor sem afiliação)
		if (alvo < 0) return [];
		const saida = new Set<number>();
		for (let l = 0; l < af!.n; l += 1) if (af!.inst[l] === alvo && (!passa || passa(af!.doc[l]))) saida.add(af!.doc[l]);
		return [...saida];
	};
	const cartao = $derived.by(() => {
		const i = selecionado;
		if (i === null) return null;
		const comunidade = nos.comunidades.get(nos.comunidade[i]);
		const lista: Parceiro[] = parceiros(recorte, i)
			.slice(0, 6)
			.map(([j, peso, documentos]) => ({ i: j, nome: nos.nomes[j], peso, documentos }));
		const quem = pessoas ? contar(nos.grau[i], 'coautor', 'coautores') : contar(nos.grau[i], 'instituição parceira', 'instituições parceiras');
		return {
			i,
			titulo: nos.nomes[i],
			sobretitulo: pessoas ? 'Pessoa' : ['Instituição', nos.lugar(i)].filter(Boolean).join(' · '),
			comunidade: comunidade
				? `Comunidade: ${comunidade.rotulo}`
				: Number.isFinite(nos.x[i])
					? 'Fora das comunidades grandes'
					: pessoas
						? 'Sem coautores no corpus: fica fora do desenho'
						: null,
			cor: comunidade ? corDaComunidade(comunidade.id) : null,
			numeros: `${contar(nos.docsCorpus[i], 'documento')} no corpus, ${formatarInteiro(docsRecorte[i])} no recorte · ${quem} no corpus`,
			parceiros: lista,
			documentos: documentosDo(i)
		};
	});
	const linkDoc = (d: number) => rota('/mapa', escreverFiltros({ ...recorteDe(filtros), doc: t.ids[d] }));
	function alternarInstituicao(id: string) {
		const atual = filtros.inst;
		mudarFiltros({ inst: atual.includes(id) ? atual.filter((x) => x !== id) : [...atual, id] }, { em });
	}

	// ---- busca
	const itensBusca = $derived.by((): ItemBusca[] =>
		Array.from({ length: nos.n }, (_, i) => i)
			.sort((a, b) => nos.docsCorpus[b] - nos.docsCorpus[a] || nos.nomes[a].localeCompare(nos.nomes[b], 'pt-BR'))
			.map((i) => ({
				id: nos.ids[i],
				nome: nos.nomes[i],
				detalhe: [contar(nos.docsCorpus[i], 'documento'), nos.lugar(i)].filter(Boolean).join(' · '),
				chave: dobrar(`${nos.nomes[i]} ${nos.ids[i]}`)
			}))
	);

	// ---- dica
	const dica = (i: number) => [
		nos.nomes[i],
		...(pessoas ? [] : [nos.lugar(i)].filter(Boolean)),
		`${contar(nos.docsCorpus[i], 'documento')} (${formatarInteiro(docsRecorte[i])} no recorte)`,
		pessoas
			? `${contar(nos.grau[i], 'coautor', 'coautores')} no corpus, ${formatarInteiro(grauRecorte[i])} no recorte`
			: `${contar(nos.grau[i], 'parceira')} no corpus, ${formatarInteiro(grauRecorte[i])} no recorte`
	];

	// ---- frases, tabela e legenda
	const ativos = $derived(ativo.reduce((s, v) => s + v, 0));
	const nome = $derived(
		pessoas ? { no: 'pessoa', nos: 'pessoas', par: 'pares de coautores' } : { no: 'instituição', nos: 'instituições', par: 'pares de instituições' }
	);
	const resumo = $derived(
		pessoas
			? `Cada ponto é uma pessoa, do tamanho dos documentos dela no corpus, na cor do macrotema mais comum na sua comunidade. Cada linha liga duas pessoas que assinaram juntas um documento do recorte; quanto mais forte a linha, mais peso tem a parceria.`
			: `Cada ponto é uma instituição, do tamanho dos documentos com afiliação nela. Cada linha liga duas instituições que aparecem nas afiliações de um mesmo documento do recorte; quanto mais forte a linha, mais peso tem a colaboração.`
	);
	// a força (a soma dos pesos 1/(n−1)) é um inteiro: os documentos do recorte em que o nó teve parceiro
	const colunas = $derived([
		pessoas ? 'Pessoa' : 'Instituição',
		'Documentos no recorte',
		pessoas ? 'Coautores no recorte' : 'Parceiras no recorte',
		pessoas ? 'Documentos com coautor no recorte' : 'Documentos com parceira no recorte',
		'Comunidade'
	]);
	const ordemDaTabela = $derived(
		Array.from({ length: nos.n }, (_, i) => i)
			.filter((i) => docsRecorte[i] > 0)
			.sort((a, b) => docsRecorte[b] - docsRecorte[a] || forcaRecorte[b] - forcaRecorte[a] || a - b)
	);
	const comunidadeDe = (i: number) => nos.comunidades.get(nos.comunidade[i])?.rotulo ?? null;
	const linhas = $derived(
		ordemDaTabela.map((i) => [
			nos.nomes[i],
			formatarInteiro(docsRecorte[i]),
			formatarInteiro(grauRecorte[i]),
			formatarInteiro(Math.round(forcaRecorte[i])),
			comunidadeDe(i) ?? '—'
		])
	);
	const dados = $derived({
		colunas: [...colunas, 'Id', 'Documentos no corpus'],
		linhas: ordemDaTabela.map((i) => [
			nos.nomes[i],
			docsRecorte[i],
			grauRecorte[i],
			Math.round(forcaRecorte[i]),
			comunidadeDe(i),
			nos.ids[i],
			nos.docsCorpus[i]
		])
	});
	const macrosNaLegenda = $derived.by(() => {
		const usados = new Set([...nos.comunidades.values()].map((c) => c.macro));
		return aberto.topicos.macrotemas.filter((m) => usados.has(m.id));
	});
	/** As maiores comunidades da rede, com o rótulo inteiro, para a legenda (e para a figura exportada). */
	const maioresComunidades = $derived([...nos.comunidades.values()].sort((a, b) => b.n - a.n || a.id - b.id).slice(0, MAXIMO_ROTULOS));
	const faixasLegenda = [
		`até ${formatarDecimal(LIMITES_FAIXAS[0])}`,
		`${formatarDecimal(LIMITES_FAIXAS[0])} a ${formatarInteiro(LIMITES_FAIXAS[1])}`,
		`${formatarInteiro(LIMITES_FAIXAS[1])} a ${formatarInteiro(LIMITES_FAIXAS[2])}`,
		`mais de ${formatarInteiro(LIMITES_FAIXAS[2])}`
	];
	const metricas = $derived(r.metricas[rede] ?? null);
	const rotuloGrafo = $derived(
		`Rede de ${pessoas ? 'coautoria' : 'instituições'}: ${formatarInteiro(desenhados - (mostrarPequenos ? 0 : escondidos))} ${nome.nos} desenhadas, ` +
			`${formatarInteiro(ativos)} com documentos no recorte e ${formatarInteiro(recorte.n)} ${nome.par} nele. ` +
			'Use a busca para abrir o cartão de um nó, ou veja os números na tabela.'
	);

	// ---- depuração
	let grafo = $state<ReturnType<typeof Grafo> | null>(null);
	$effect(() => {
		debug.nos = desenhados;
		debug.arestas = corpus.n;
		debug.arestasNoRecorte = recorte.n;
		debug.selecionado = selecionado !== null ? nos.ids[selecionado] : null;
		debug.posicaoNaTela = (id) => {
			const i = nos.indice.get(id);
			return i === undefined ? undefined : grafo?.posicaoNaTela(i);
		};
	});
</script>

<p class="lide" data-testid="lide-redes">
	{#if pessoas}
		{contar(noRecorte, 'documento')} no recorte, com {contar(ativos, 'pessoa')}, {formatarInteiro(desenhadosNoRecorte)}
		delas desenhadas (as que têm coautor no corpus), e {formatarInteiro(recorte.n)}
		{recorte.n === 1 ? 'par de coautores' : 'pares de coautores'}. Duas pessoas ficam ligadas quando assinam juntas um
		documento; num artigo de n autores, cada par ganha 1/(n−1) de peso, e assim cada pessoa distribui no máximo 1 por
		artigo.
	{:else}
		{contar(noRecorte, 'documento')} no recorte, com {contar(ativos, 'instituição', 'instituições')} e
		{formatarInteiro(recorte.n)} {recorte.n === 1 ? 'par de instituições' : 'pares de instituições'}. Duas instituições
		ficam ligadas quando aparecem juntas nas afiliações de um documento (mesmo quando é um autor só, com duas
		afiliações), com o mesmo peso fracionário da coautoria.
	{/if}
	O maior grupo ligado fica à esquerda, com cada comunidade num espaço próprio; à direita e embaixo, os grupos menores{#if !mostrarPequenos && escondidos}, sem as duplas e os
		trios isolados{/if}.
</p>

<BuscaNo
	itens={itensBusca}
	rotulo={pessoas ? 'Buscar uma pessoa' : 'Buscar uma instituição'}
	dica={pessoas ? 'Nome da pessoa' : 'Nome ou sigla'}
	aoEscolher={(id) => mudarFiltros({ no: id }, { em })}
/>

<div class="grafo-e-lado" class:com-cartao={cartao !== null}>
	<Figura n={noRecorte} id="grafo" titulo={pessoas ? 'Quem escreve com quem' : 'Que instituições publicam juntas'} {resumo} {colunas} {linhas} {dados}>
		<Grafo
			bind:this={grafo}
			x={xVisivel}
			y={yVisivel}
			{raio}
			cor={cores}
			{ativo}
			arestas={corpus}
			{faixas}
			{selecionado}
			{rotulos}
			nomeDo={(i) => nos.nomes[i]}
			{dica}
			aoEscolher={abrir}
			rotulo={rotuloGrafo}
			aoDesenhar={(ms) => ((debug.desenhado = true), (debug.msAtePrimeiroDesenho = ms))}
		/>
		{#if escondidos}
			<label class="pequenos">
				<input
					type="checkbox"
					checked={mostrarPequenos}
					onchange={(e) => mostrarDuplas(e.currentTarget.checked)}
					data-testid="mostrar-pequenos"
				/>
				Mostrar as duplas e os trios isolados ({contar(escondidos, pessoas ? 'pessoa' : 'instituição', pessoas ? 'pessoas' : 'instituições')})
			</label>
		{/if}
		<div class="legenda" aria-label="Legenda">
			<ul class="cores" data-legenda>
				{#each macrosNaLegenda as m (m.id)}
					<li><span class="bolinha" style:background={m.cor}></span>{m.rotulo}</li>
				{/each}
				<li><span class="bolinha neutra"></span>comunidades pequenas</li>
				<li><span class="bolinha apagada"></span>sem documentos no recorte</li>
			</ul>
			<ul class="faixas" aria-label="Peso das ligações no recorte" data-legenda>
				<li class="titulo-legenda" title="Soma de 1/(n−1) em cada documento do recorte com n autores (ou instituições)">
					Peso da parceria no recorte:
				</li>
				{#each faixasLegenda as texto, k (k)}
					<li>
						<svg width="22" height="8" aria-hidden="true">
							<line x1="1" x2="21" y1="4" y2="4" style:stroke-width={TRACO_DAS_FAIXAS[k + 1].largura + 0.6} style:opacity={Math.min(1, TRACO_DAS_FAIXAS[k + 1].alfa + 0.25)} />
						</svg>
						{texto}
					</li>
				{/each}
				<li>
					<svg width="22" height="8" aria-hidden="true"><line class="fora" x1="1" x2="21" y1="4" y2="4" /></svg>
					fora do recorte
				</li>
			</ul>
			{#if maioresComunidades.length}
				<ol class="comunidades" aria-label="As maiores comunidades" data-legenda data-testid="lista-comunidades">
					<li class="titulo-legenda">As maiores comunidades (rótulo: os dois tópicos mais frequentes):</li>
					{#each maioresComunidades as c (c.id)}
						<li>
							<span class="bolinha" style:background={corDaComunidade(c.id) ?? 'var(--texto-fraco)'}></span>
							{c.rotulo} <span class="suave">({contar(c.n, nome.no, nome.nos)})</span>
						</li>
					{/each}
				</ol>
			{/if}
		</div>
		{#if metricas}
			<p class="nota" data-testid="metricas-rede">
				No corpus inteiro: {contar(metricas.nos, pessoas ? 'pessoa com coautor' : 'instituição com parceira', pessoas ? 'pessoas com coautor' : 'instituições com parceira')}
				(as desenhadas), {formatarInteiro(metricas.arestas)} pares e {contar(metricas.componentes, 'componente')}
				(grupos ligados por algum caminho; o maior junta {formatarPorcentagem(metricas.fracao_maior)} deles). Agrupamento
				{formatarDecimal(metricas.agrupamento, 2)}: a fração de trios fechados (dois parceiros de alguém que também são
				parceiros entre si).{#if metricas.modularidade !== null}{' '}Modularidade {formatarDecimal(metricas.modularidade, 2)}: quanto das ligações fica dentro das comunidades (de 0
					a 1).{/if}
				As comunidades são agrupamentos automáticos (Louvain) e levam o nome dos tópicos mais frequentes nos
				documentos delas.
			</p>
		{/if}
	</Figura>

	<aside class="lado">
		{#if cartao}
			<CartaoNo
				titulo={cartao.titulo}
				sobretitulo={cartao.sobretitulo}
				cor={cartao.cor}
				comunidade={cartao.comunidade}
				numeros={cartao.numeros}
				rotuloParceiros={pessoas ? 'Coautores no recorte' : 'Parceiras no recorte'}
				parceiros={cartao.parceiros}
				documentos={cartao.documentos}
				tabela={t}
				{linkDoc}
				aoAbrir={(j) => abrir(j)}
				aoFechar={() => abrir(null)}
				filtro={pessoas ? null : { ativo: filtros.inst.includes(nos.ids[cartao.i]), alternar: () => alternarInstituicao(nos.ids[cartao.i]) }}
			/>
		{/if}
		<Colaboracao
			quais={pessoas ? ['coautoria', 'autores'] : ['instituicoes', 'exterior']}
			{aberto}
			redes={r}
			afiliacoes={af}
			{filtros}
			{falhas}
			n={noRecorte}
		/>
	</aside>
</div>

<style>
	.lide {
		max-width: 60rem;
		margin: 0;
		color: var(--texto-suave);
	}

	.grafo-e-lado {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(16rem, 20rem);
		gap: 1.5rem;
		align-items: start;
	}

	.lado {
		display: grid;
		gap: 1rem;
		min-width: 0;
	}

	.legenda {
		display: grid;
		gap: 0.35rem;
		margin-top: 0.6rem;
	}

	.legenda ul {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 1rem;
		margin: 0;
		padding: 0;
		list-style: none;
		font-size: 0.78rem;
		color: var(--texto-suave);
	}

	.legenda li {
		display: flex;
		align-items: center;
		gap: 0.35rem;
	}

	.bolinha {
		flex: none;
		width: 0.65rem;
		height: 0.65rem;
		border-radius: 50%;
	}

	.bolinha.neutra {
		background: var(--texto-fraco);
	}

	.bolinha.apagada {
		background: var(--texto-fraco);
		opacity: 0.35;
	}

	.faixas line {
		stroke: var(--texto);
	}

	.faixas line.fora {
		stroke: var(--texto-fraco);
		stroke-width: 0.8;
		opacity: 0.5;
	}

	.pequenos {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		margin-top: 0.5rem;
		font-size: 0.82rem;
		color: var(--texto-suave);
	}

	.titulo-legenda {
		color: var(--texto);
	}

	.comunidades {
		display: grid;
		gap: 0.2rem;
		margin: 0.2rem 0 0;
		padding: 0;
		list-style: none;
		font-size: 0.78rem;
		color: var(--texto-suave);
	}

	.comunidades li {
		display: flex;
		align-items: baseline;
		gap: 0.35rem;
	}

	.comunidades .suave {
		color: var(--texto-suave);
	}

	.nota {
		margin: 0.6rem 0 0;
		max-width: 60rem;
		font-size: 0.82rem;
		color: var(--texto-suave);
	}

	@media (max-width: 1100px) {
		.grafo-e-lado {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
