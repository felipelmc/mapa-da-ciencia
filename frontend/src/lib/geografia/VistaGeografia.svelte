<script lang="ts">
	/**
	 * A vista Geografia: onde a produção acontece. Três gráficos no filtro cruzado, todos com a contagem fracionária
	 * (cada documento vale 1, dividido entre os autores e as afiliações de cada um):
	 *
	 * - o coroplético das UFs, que ignora o próprio filtro de UF (as outras continuam clicáveis);
	 * - o mapa-múndi, com o Brasil fora da escala (senão ele achataria todos os outros países);
	 * - o ranking das instituições.
	 *
	 * Clicar numa UF, num país ou numa instituição põe o lugar no recorte, que vale para as outras vistas (um
	 * documento passa se tiver alguma afiliação ali).
	 */
	import type { Aberto } from '$lib/dados/corpus';
	import type { TabelaAfiliacoes } from '$lib/dados/afiliacoes';
	import { D } from '$lib/dados/cubo';
	import { filtrosDaPagina, mudarFiltros } from '$lib/estado/filtros';
	import { formatarDecimal, formatarInteiro, formatarPorcentagem } from '$lib/formato';
	import Figura from '$lib/graficos/Figura.svelte';
	import { NOME_UF, nomePais } from './lugares';
	import { malhaMundo, malhaUF, projecaoBrasil, projecaoMundo, type PropsPais, type PropsUF, type Regiao } from './malhas';
	import CoberturaAnos, { anosFracos, LIMIAR_AVISO, type CoberturaAno } from './CoberturaAnos.svelte';
	import MapaRegioes from './MapaRegioes.svelte';
	import RankingInstituicoes, { type ItemRanking } from './RankingInstituicoes.svelte';

	let { aberto, afiliacoes: a }: { aberto: Aberto; afiliacoes: TabelaAfiliacoes } = $props();

	const cubo = $derived(aberto.cubo);
	const filtros = $derived(filtrosDaPagina());
	const em = '/geografia';
	const falhas = $derived(cubo.falhas(filtros));

	// ---- somas por lugar (cada gráfico ignora o próprio filtro)
	function porChave(chaves: string[], soma: Float64Array): Map<string, number> {
		return new Map(chaves.map((k, i) => [k, soma[i]] as [string, number]).filter(([, v]) => v > 0));
	}
	const ufs = $derived(porChave(a.ufs, cubo.somarAfiliacoesPor(falhas, D.UF, a.ufs.length, (l) => a.uf[l])));
	const docsUf = $derived(porChave(a.ufs, cubo.documentosPorLugar(falhas, D.UF, a.ufs.length, (l) => a.uf[l])));
	const paises = $derived(
		porChave(a.paises, cubo.somarAfiliacoesPor(falhas, D.PAIS, a.paises.length, (l) => a.pais[l]))
	);
	const docsPais = $derived(
		porChave(a.paises, cubo.documentosPorLugar(falhas, D.PAIS, a.paises.length, (l) => a.pais[l]))
	);
	const ids = $derived(a.instituicoes.map((i) => i.id));
	const insts = $derived(cubo.somarAfiliacoesPor(falhas, D.INST, ids.length, (l) => a.inst[l]));
	const docsInst = $derived(cubo.documentosPorLugar(falhas, D.INST, ids.length, (l) => a.inst[l]));
	const ranking = $derived(
		a.instituicoes
			.map(
				(inst, i): ItemRanking => ({
					id: inst.id,
					nome: inst.nome,
					sigla: inst.sigla ?? null,
					lugar: [inst.uf, inst.pais ? nomePais(inst.pais) : null].filter(Boolean).join(', '),
					peso: insts[i],
					documentos: docsInst[i]
				})
			)
			.filter((x, i) => x.peso > 0 && i !== a.naoIdentificada)
			.sort((x, y) => y.peso - x.peso)
	);

	// ---- totais do recorte (todos os filtros valem)
	const total = $derived(cubo.contar(falhas));
	const semAfiliacao = $derived(cubo.somarAfiliacoesPor(falhas, 0, 1, (l) => (a.inst[l] < 0 ? 0 : -1))[0]);
	const naoIdentificada = $derived(
		a.naoIdentificada >= 0 ? cubo.somarAfiliacoesPor(falhas, 0, 1, (l) => (a.inst[l] === a.naoIdentificada ? 0 : -1))[0] : 0
	);
	const noBrasil = $derived(paises.get('BR') ?? 0);
	const comPais = $derived([...paises.values()].reduce((s, v) => s + v, 0));

	// ---- cobertura por ano (o período inteiro: ignora o filtro de anos, como o fluxo dos tópicos)
	const anos = $derived(aberto.topicos.anos);
	const cobertura = $derived.by((): CoberturaAno[] => {
		const primeiro = anos[0];
		const t = cubo.t;
		const somas = cubo.somarAfiliacoesPor(falhas, D.ANO, anos.length * 3, (l) => {
			const j = t.ano[a.doc[l]] - primeiro;
			if (j < 0 || j >= anos.length) return -1;
			const categoria = a.inst[l] < 0 ? 2 : a.inst[l] === a.naoIdentificada ? 1 : 0;
			return j * 3 + categoria;
		});
		return anos.map((ano, j) => ({
			ano,
			identificada: somas[j * 3],
			naoIdentificada: somas[j * 3 + 1],
			semAfiliacao: somas[j * 3 + 2]
		}));
	});
	const fracos = $derived(anosFracos(cobertura));
	const resumoCobertura = $derived(
		fracos.length
			? `Em ${fracos.map(([x, y]) => (x === y ? `${x}` : `${x}–${y}`)).join(', ')}, mais de ` +
					`${formatarPorcentagem(LIMIAR_AVISO)} do peso de cada ano fica com autores sem afiliação informada: ` +
					'a geografia desses anos é mais incompleta, e comparações com os outros pedem cuidado.'
			: `Em todos os anos, pelo menos ${formatarPorcentagem(1 - LIMIAR_AVISO)} do peso tem afiliação informada.`
	);
	const linhasCobertura = $derived(
		cobertura.map((c) => {
			const soma = c.identificada + c.naoIdentificada + c.semAfiliacao || 1;
			return [String(c.ano), ...[c.identificada, c.naoIdentificada, c.semAfiliacao].map((v) => formatarPorcentagem(v / soma))];
		})
	);

	// ---- malhas (carregadas quando a vista abre)
	let malhaUfs = $state<Regiao<PropsUF>[] | null>(null);
	let malhaPaises = $state<Regiao<PropsPais>[] | null>(null);
	let erroMalha = $state<string | null>(null);
	$effect(() => {
		Promise.all([malhaUF(), malhaMundo()])
			.then(([u, p]) => ((malhaUfs = u), (malhaPaises = p.filter((r) => r.properties.iso !== 'AQ'))))
			.catch((e: Error) => (erroMalha = e.message));
	});

	function alternar(chave: 'uf' | 'pais' | 'inst', valor: string) {
		const atual = filtros[chave];
		mudarFiltros({ [chave]: atual.includes(valor) ? atual.filter((x) => x !== valor) : [...atual, valor] }, { em });
	}

	// ---- frases e tabelas
	const maiores = (m: Map<string, number>, n: number, nome: (k: string) => string) =>
		[...m.entries()]
			.sort((x, y) => y[1] - x[1])
			.slice(0, n)
			.map(([k, v]) => `${nome(k)} (${formatarDecimal(v)})`)
			.join(', ');
	const resumoUf = $derived.by(() => {
		const soma = [...ufs.values()].reduce((s, v) => s + v, 0);
		if (!soma) return 'No recorte, nenhum documento tem afiliação no Brasil com UF conhecida.';
		const top3 = [...ufs.values()].sort((x, y) => y - x).slice(0, 3).reduce((s, v) => s + v, 0);
		return (
			`${formatarDecimal(soma)} de peso nas UFs, em ${formatarInteiro(ufs.size)} delas. As três maiores ` +
			`(${maiores(ufs, 3, (k) => k)}) somam ${formatarPorcentagem(top3 / soma)}.`
		);
	});
	const foraDoBrasil = $derived(new Map([...paises].filter(([k]) => k !== 'BR')));
	const resumoMundo = $derived(
		comPais
			? `${formatarPorcentagem(noBrasil / comPais)} do peso com país conhecido é do Brasil. Fora dele, ` +
					(foraDoBrasil.size
						? `${foraDoBrasil.size === 1 ? 'o único é' : 'os maiores são'} ${maiores(foraDoBrasil, 3, nomePais)}.`
						: 'nenhum país.')
			: 'No recorte, nenhum documento tem afiliação com país conhecido.'
	);
	const resumoRanking = $derived(
		ranking.length
			? `${formatarInteiro(ranking.length)} instituições no recorte. As maiores: ` +
					ranking
						.slice(0, 3)
						.map((i) => `${i.sigla ?? i.nome} (${formatarDecimal(i.peso)})`)
						.join(', ') +
					'.'
			: 'No recorte, nenhuma instituição identificada.'
	);
	const tabela = (m: Map<string, number>, docs: Map<string, number>, nome: (k: string) => string) =>
		[...m.entries()].sort((x, y) => y[1] - x[1]).map(([k, v]) => [nome(k), formatarDecimal(v, 2), formatarInteiro(docs.get(k) ?? 0)]);
	const nomeUf = (k: string) => NOME_UF[k] ?? k;
	const selUf = $derived(new Set(filtros.uf));
	const selPais = $derived(new Set(filtros.pais));
	const selInst = $derived(new Set(filtros.inst));
</script>

<svelte:head>
	<title>Geografia · mapa da ciência</title>
</svelte:head>

<div class="vista surgir">
	<header class="cabecalho">
		<h1>Geografia</h1>
		<p class="lide" data-testid="lide-geografia">
			{formatarInteiro(total)} documentos no recorte. Cada um vale 1, dividido entre os autores e, para cada autor,
			entre as afiliações dele: {formatarDecimal(semAfiliacao)} vão para autores sem afiliação informada e
			{formatarDecimal(naoIdentificada)} para afiliações que não casaram com nenhuma instituição.
		</p>
	</header>

	{#if erroMalha}
		<p class="aviso" role="alert">Não foi possível carregar as malhas: {erroMalha}</p>
	{/if}

	<div class="lado-a-lado">
		<Figura
		n={total}
			id="ufs"
			titulo="Por UF"
			resumo={resumoUf}
			colunas={['UF', 'Peso fracionário', 'Documentos']}
			linhas={tabela(ufs, docsUf, nomeUf)}
			pronto={!!malhaUfs}
		>
			{#if malhaUfs}
				<MapaRegioes
					id="uf"
					regioes={malhaUfs}
					chave={(r) => r.properties.sigla}
					projetar={projecaoBrasil}
					valores={ufs}
					documentos={docsUf}
					selecionados={selUf}
					nome={nomeUf}
					aoEscolher={(k) => alternar('uf', k)}
					proporcao={0.95}
					rotulo="Mapa das UFs; cada UF é um botão que filtra o recorte"
				/>
			{/if}
		</Figura>

		<Figura
		n={total}
			id="instituicoes"
			titulo="Instituições"
			resumo={resumoRanking}
			colunas={['Instituição', 'Lugar', 'Peso fracionário', 'Documentos']}
			linhas={ranking.map((i) => [i.sigla ? `${i.nome} (${i.sigla})` : i.nome, i.lugar, formatarDecimal(i.peso, 2), formatarInteiro(i.documentos)])}
		>
			<RankingInstituicoes itens={ranking} selecionados={selInst} aoEscolher={(id) => alternar('inst', id)} />
		</Figura>
	</div>

	<Figura
		n={total}
		id="mundo"
		titulo="No mundo"
		resumo={resumoMundo}
		colunas={['País', 'Peso fracionário', 'Documentos']}
		linhas={tabela(paises, docsPais, nomePais)}
		pronto={!!malhaPaises}
	>
		{#if malhaPaises}
			<MapaRegioes
				id="pais"
				regioes={malhaPaises}
				chave={(r) => r.properties.iso}
				projetar={projecaoMundo}
				valores={paises}
				documentos={docsPais}
				selecionados={selPais}
				fora={new Set(noBrasil ? ['BR'] : [])}
				nome={nomePais}
				aoEscolher={(k) => alternar('pais', k)}
				proporcao={0.48}
				rotulo="Mapa-múndi; cada país com documentos é um botão que filtra o recorte"
			/>
		{/if}
	</Figura>

	<Figura
		n={total}
		id="cobertura"
		titulo="Cobertura por ano"
		resumo={resumoCobertura}
		colunas={['Ano', 'Instituição identificada', 'Afiliação não identificada', 'Sem afiliação']}
		linhas={linhasCobertura}
	>
		<CoberturaAnos anos={cobertura} />
		<p class="nota">
			Nos artigos mais antigos, as fontes trazem menos afiliações, e as que trazem vêm como texto livre. Os
			mapas acima contam só o peso com lugar conhecido; o "sem afiliação" não entra em nenhuma UF nem país.
		</p>
	</Figura>

	<p class="creditos">
		Malhas: UFs do <a href="https://www.ibge.gov.br/geociencias/organizacao-do-territorio/malhas-territoriais.html">IBGE</a>,
		países do <a href="https://www.naturalearthdata.com">Natural Earth</a>. Projeções que preservam as áreas.
		Instituições casadas com o <a href="https://openalex.org">OpenAlex</a> e o <a href="https://ror.org">ROR</a>.
	</p>
</div>

<style>
	.vista {
		display: grid;
		gap: 1.5rem;
		max-width: 76rem;
	}

	.cabecalho {
		display: grid;
		gap: 0.5rem;
	}

	h1 {
		margin: 0;
		font-size: clamp(2.2rem, 4.5vw, 3.2rem);
		font-weight: 380;
	}

	.lide {
		max-width: 60rem;
		margin: 0;
		color: var(--texto-suave);
	}

	.lado-a-lado {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
		gap: 1.5rem;
		align-items: start;
	}

	.aviso {
		color: var(--texto-suave);
	}

	.nota {
		margin: 0.6rem 0 0;
		font-size: 0.85rem;
		color: var(--texto-suave);
	}

	.creditos {
		margin: 0;
		font-size: 0.78rem;
		color: var(--texto-fraco);
	}

	.creditos a {
		color: inherit;
	}

	@media (max-width: 980px) {
		.lado-a-lado {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
