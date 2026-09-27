<script lang="ts" module>
	export const PASSOS = ['Fontes', 'Recorte', 'Modelo', 'Codebook', 'Revisão'] as const;
</script>

<script lang="ts">
	/**
	 * O assistente do projeto, em 5 passos, sobre o projeto aberto no painel: as fontes (revistas do SciELO), o
	 * recorte (anos, tipos, idiomas), os modelos (perfil pela memória da máquina, o que está instalado e o que falta
	 * baixar), o codebook e a revisão, com o que muda e o que isso refaz. Nada é gravado antes da revisão; ao
	 * salvar, o `mapa.yaml` e o `codebook.yaml` mudam só no que mudou, sem perder os comentários.
	 */
	import { onMount } from 'svelte';
	import type {
		CodebookEditavel,
		Configuracao,
		Estimativa,
		FonteApi,
		InfoModelos,
		RevistaDoRetrato
	} from '$lib/dados/api';
	import { ErroDaApi } from '$lib/dados/pedir';
	import { formatarDuracao, formatarInteiro, formatarPeriodo } from '$lib/formato';
	import EditorCodebook from './EditorCodebook.svelte';

	let {
		fonte,
		aoFechar,
		aoPiloto
	}: {
		fonte: FonteApi;
		aoFechar: (salvou: boolean) => void;
		/** Depois de salvar, roda um piloto (coleta de 20 documentos). */
		aoPiloto: () => void;
	} = $props();

	const TIPOS_DOC = [
		['research-article', 'Artigos'],
		['review-article', 'Artigos de revisão'],
		['brief-report', 'Comunicações breves'],
		['book-review', 'Resenhas']
	] as const;
	const IDIOMAS = [
		['pt', 'Português'],
		['en', 'Inglês'],
		['es', 'Espanhol']
	] as const;
	const PAPEIS = [
		['embeddings', 'Embeddings (tópicos e mapa)'],
		['classificacao', 'Classificação'],
		['rotulos', 'Rótulos dos tópicos']
	] as const;

	let passo = $state(0);
	let original = $state<Configuracao | null>(null);
	let revistas = $state<string[]>([]);
	let titulos = $state<Record<string, RevistaDoRetrato>>({});
	let enriquecer = $state(true);
	let anos = $state<[number, number]>([2010, 2025]);
	let tipos = $state<string[]>([]);
	let idiomaAnalise = $state('en');
	let idiomaExibicao = $state('pt');
	let modelos = $state({ embeddings: '', classificacao: '', rotulos: '' });
	let codebook = $state<CodebookEditavel | null>(null);
	let codebookOriginal = '';
	let info = $state<InfoModelos | null>(null);
	let estimativa = $state<Estimativa | null>(null);
	let busca = $state('');
	let achadas = $state<RevistaDoRetrato[]>([]);
	let erro = $state<string | null>(null);
	let salvando = $state(false);

	onMount(async () => {
		try {
			const [c, cb] = await Promise.all([fonte.configuracao(), fonte.codebookEditavel()]);
			original = c;
			revistas = [...(c.fontes.scielo?.revistas ?? [])];
			tipos = [...(c.fontes.scielo?.tipos ?? ['research-article', 'review-article'])];
			enriquecer = Boolean((c.fontes as Record<string, { enriquecer?: boolean }>).openalex?.enriquecer ?? true);
			anos = [c.recorte.anos[0], c.recorte.anos[1]];
			idiomaAnalise = c.recorte.idioma_analise;
			idiomaExibicao = c.recorte.idioma_exibicao;
			modelos = {
				embeddings: c.modelos.embeddings.modelo,
				classificacao: c.modelos.classificacao.modelo,
				rotulos: c.modelos.rotulos.modelo
			};
			const { hash: _, ...semHash } = cb;
			void _;
			codebook = semHash;
			codebookOriginal = JSON.stringify(semHash);
			if (revistas.length)
				titulos = Object.fromEntries((await fonte.buscarRevistas('', revistas)).map((r) => [r.issn, r]));
			fonte.modelos().then((m) => (info = m)).catch(() => (info = null));
			fonte.estimativaClassificacao().then((e) => (estimativa = e)).catch(() => {});
		} catch (e) {
			erro = `Não foi possível ler o projeto: ${(e as Error).message}`;
		}
	});

	let temporizador: ReturnType<typeof setTimeout> | null = null;
	function procurar() {
		if (temporizador) clearTimeout(temporizador);
		temporizador = setTimeout(async () => {
			achadas = busca.trim().length >= 2 ? await fonte.buscarRevistas(busca) : [];
		}, 200);
	}
	function incluir(r: RevistaDoRetrato) {
		if (!revistas.includes(r.issn)) revistas = [...revistas, r.issn];
		titulos = { ...titulos, [r.issn]: r };
	}

	function usarPerfil(nome: string) {
		const p = info?.perfis.find((x) => x.nome === nome);
		if (p) modelos = { embeddings: p.embeddings, classificacao: p.classificacao, rotulos: p.rotulos };
	}
	const instalado = (m: string) => !!info?.instalados.some((x) => x.nome.replace(/:latest$/, '') === m.replace(/:latest$/, ''));
	const perfilAtual = $derived(
		info?.perfis.find(
			(p) => p.embeddings === modelos.embeddings && p.classificacao === modelos.classificacao && p.rotulos === modelos.rotulos
		)?.nome ?? null
	);

	// ---- o que muda
	const mudancas = $derived.by(() => {
		if (!original || !codebook) return [];
		const saida: { texto: string; refaz: string }[] = [];
		const antes = original.fontes.scielo?.revistas ?? [];
		const mais = revistas.filter((r) => !antes.includes(r));
		const menos = antes.filter((r) => !revistas.includes(r));
		const nome = (issn: string) => titulos[issn]?.titulo ?? issn;
		if (mais.length) saida.push({ texto: `Revistas incluídas: ${mais.map(nome).join(', ')}.`, refaz: 'coleta e as etapas seguintes' });
		if (menos.length) saida.push({ texto: `Revistas retiradas: ${menos.map(nome).join(', ')}.`, refaz: 'coleta e as etapas seguintes' });
		if (anos[0] !== original.recorte.anos[0] || anos[1] !== original.recorte.anos[1])
			saida.push({
				texto: `Período: ${formatarPeriodo(original.recorte.anos)} → ${formatarPeriodo(anos)}.`,
				refaz: 'coleta e as etapas seguintes'
			});
		if (JSON.stringify([...tipos].sort()) !== JSON.stringify([...(original.fontes.scielo?.tipos ?? [])].sort()))
			saida.push({ texto: `Tipos de documento: ${tipos.join(', ')}.`, refaz: 'coleta e as etapas seguintes' });
		if (idiomaAnalise !== original.recorte.idioma_analise)
			saida.push({ texto: `Idioma de análise: ${idiomaAnalise}.`, refaz: 'tópicos (embeddings novos)' });
		if (idiomaExibicao !== original.recorte.idioma_exibicao)
			saida.push({ texto: `Idioma de exibição: ${idiomaExibicao}.`, refaz: 'classificação (o texto classificado muda)' });
		for (const [papel, nomePapel] of PAPEIS) {
			const antesM = original.modelos[papel].modelo;
			if (antesM !== modelos[papel])
				saida.push({
					texto: `${nomePapel}: ${antesM} → ${modelos[papel]}${instalado(modelos[papel]) ? '' : ' (ainda não instalado)'}.`,
					refaz: papel === 'classificacao' ? 'classificação' : 'tópicos'
				});
		}
		if (JSON.stringify(codebook) !== codebookOriginal)
			saida.push({ texto: 'O codebook mudou.', refaz: 'classificação, se as definições mudaram' });
		return saida;
	});

	function validarPasso(): string | null {
		if (passo === 0 && !revistas.length) return 'Escolha pelo menos uma revista.';
		if (passo === 1 && (!Number.isInteger(anos[0]) || !Number.isInteger(anos[1]) || anos[0] > anos[1]))
			return 'O período precisa de dois anos, o primeiro antes do segundo.';
		if (passo === 1 && !tipos.length) return 'Escolha pelo menos um tipo de documento.';
		return null;
	}
	function avancar() {
		erro = validarPasso();
		if (!erro) passo = Math.min(PASSOS.length - 1, passo + 1);
	}

	async function salvar(piloto: boolean) {
		if (!original || !codebook) return;
		salvando = true;
		erro = null;
		try {
			await fonte.mudarConfiguracao({
				fontes: {
					scielo: { ...(original.fontes.scielo ?? { colecao: 'scl' }), revistas, tipos },
					openalex: { enriquecer }
				},
				recorte: { anos, idioma_analise: idiomaAnalise, idioma_exibicao: idiomaExibicao },
				modelos: {
					embeddings: { modelo: modelos.embeddings },
					classificacao: { modelo: modelos.classificacao },
					rotulos: { modelo: modelos.rotulos }
				}
			});
			if (JSON.stringify(codebook) !== codebookOriginal) await fonte.salvarCodebook(codebook);
			if (piloto) aoPiloto();
			aoFechar(true);
		} catch (e) {
			erro = e instanceof ErroDaApi ? e.message : `Não foi possível salvar: ${(e as Error).message}`;
		} finally {
			salvando = false;
		}
	}
</script>

<section class="assistente" aria-labelledby="titulo-assistente" data-testid="assistente">
	<header>
		<h2 id="titulo-assistente">Configurar o projeto</h2>
		<button type="button" class="fechar" onclick={() => aoFechar(false)}>Cancelar</button>
	</header>

	<ol class="passos" aria-label="Passos">
		{#each PASSOS as nome, i (nome)}
			<li class:atual={i === passo} class:feito={i < passo}>
				<button type="button" onclick={() => (i < passo || !validarPasso()) && (passo = i)} aria-current={i === passo ? 'step' : undefined}>
					<span class="numero">{i + 1}</span>{nome}
				</button>
			</li>
		{/each}
	</ol>

	{#if !original || !codebook}
		<p class="suave" role="status">{erro ?? 'Lendo o projeto…'}</p>
	{:else}
		<div class="conteudo" data-testid="passo-{passo + 1}">
			{#if passo === 0}
				<h3>As revistas do SciELO Brasil</h3>
				<ul class="escolhidas" data-testid="revistas-escolhidas">
					{#each revistas as issn (issn)}
						<li>
							<span>{titulos[issn]?.titulo ?? issn}</span>
							<code>{issn}</code>
							<button type="button" aria-label="Tirar {titulos[issn]?.titulo ?? issn}" onclick={() => (revistas = revistas.filter((r) => r !== issn))}>×</button>
						</li>
					{/each}
				</ul>
				<label>
					Procurar uma revista (nome, sigla, ISSN ou área)
					<input type="search" bind:value={busca} oninput={procurar} placeholder="ciência política" data-testid="busca-revista" />
				</label>
				{#if achadas.length}
					<ul class="achadas">
						{#each achadas as r (r.issn)}
							<li>
								<button type="button" onclick={() => incluir(r)} disabled={revistas.includes(r.issn)} data-testid="incluir-revista">
									+ {r.titulo} <code>{r.issn}</code>
								</button>
							</li>
						{/each}
					</ul>
				{/if}
				<label class="caixa"><input type="checkbox" bind:checked={enriquecer} /> Completar com o OpenAlex (citações, licenças, instituições)</label>
			{:else if passo === 1}
				<h3>O recorte</h3>
				<div class="linha">
					<label>De <input type="number" min="1900" max="2100" bind:value={anos[0]} data-testid="ano-inicio" /></label>
					<label>Até <input type="number" min="1900" max="2100" bind:value={anos[1]} data-testid="ano-fim" /></label>
				</div>
				<fieldset>
					<legend>Tipos de documento</legend>
					{#each TIPOS_DOC as [t, nome] (t)}
						<label class="caixa"><input type="checkbox" value={t} bind:group={tipos} /> {nome}</label>
					{/each}
				</fieldset>
				<div class="linha">
					<label>
						Idioma de análise (tópicos)
						<select bind:value={idiomaAnalise}>{#each IDIOMAS as [c, n] (c)}<option value={c}>{n}</option>{/each}</select>
					</label>
					<label>
						Idioma de exibição (e da classificação)
						<select bind:value={idiomaExibicao}>{#each IDIOMAS as [c, n] (c)}<option value={c}>{n}</option>{/each}</select>
					</label>
				</div>
			{:else if passo === 2}
				<h3>Os modelos</h3>
				{#if info}
					<p class="suave">
						Esta máquina tem {info.ram_gb.toLocaleString('pt-BR')} GB de memória; o perfil sugerido é o
						<strong>{info.perfil_sugerido === 'padrao' ? 'padrão' : info.perfil_sugerido}</strong>.
					</p>
					<div class="perfis">
						{#each info.perfis as p (p.nome)}
							<button type="button" class="perfil" aria-pressed={perfilAtual === p.nome} onclick={() => usarPerfil(p.nome)} data-testid="perfil-{p.nome}">
								<strong>{p.nome === 'padrao' ? 'Padrão' : p.nome[0].toUpperCase() + p.nome.slice(1)}</strong>
								{#if p.nome === info.perfil_sugerido}<span class="selo">sugerido</span>{/if}
								<span class="suave">{p.descricao}</span>
								<span class="suave">Classificação: {p.classificacao}; rótulos: {p.rotulos}. Download: {p.download_gb.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} GB.</span>
							</button>
						{/each}
					</div>
					<ul class="modelos">
						{#each PAPEIS as [papel, nome] (papel)}
							<li>
								<span>{nome}</span>
								<code>{modelos[papel]}</code>
								{#if instalado(modelos[papel])}
									<span class="suave">instalado</span>
								{:else}
									<span class="falta">falta baixar{info.tamanhos_gb[modelos[papel]] ? ` (${info.tamanhos_gb[modelos[papel]].toLocaleString('pt-BR')} GB)` : ''}</span>
								{/if}
							</li>
						{/each}
					</ul>
				{:else}
					<p class="suave">Lendo os modelos do Ollama…</p>
				{/if}
			{:else if passo === 3}
				<h3>O codebook</h3>
				<p class="suave">
					O modelo lê as instruções, as perguntas, as definições e os exemplos: mudar uma definição refaz a
					classificação. Os rótulos só mudam o que o painel mostra.
				</p>
				<EditorCodebook bind:codebook />
			{:else}
				<h3>Revisão</h3>
				{#if mudancas.length}
					<ul class="mudancas" data-testid="mudancas">
						{#each mudancas as m (m.texto)}<li>{m.texto} <span class="suave">Refaz: {m.refaz}.</span></li>{/each}
					</ul>
				{:else}
					<p>Nada mudou.</p>
				{/if}
				{#if estimativa && estimativa.segundos_por_documento}
					<p class="suave">
						Hoje a classificação leva cerca de {formatarDuracao(estimativa.segundos_por_documento)} por documento neste
						computador ({formatarInteiro(estimativa.documentos)} documentos com resumo no corpus atual).
					</p>
				{/if}
				<p class="suave">
					Um <strong>piloto</strong> coleta só 20 documentos, para conferir o recorte antes da coleta inteira. Depois,
					rode as outras etapas pela linha.
				</p>
			{/if}
		</div>

		{#if erro}<p class="erro" role="alert">{erro}</p>{/if}

		<div class="acoes">
			<button type="button" onclick={() => ((erro = null), (passo = Math.max(0, passo - 1)))} disabled={passo === 0}>← Voltar</button>
			{#if passo < PASSOS.length - 1}
				<button type="button" class="principal" onclick={avancar} data-testid="avancar">Continuar →</button>
			{:else}
				<button type="button" onclick={() => salvar(false)} disabled={salvando} data-testid="salvar">Salvar</button>
				<button type="button" class="principal" onclick={() => salvar(true)} disabled={salvando} data-testid="salvar-piloto">
					Salvar e rodar um piloto (20 documentos)
				</button>
			{/if}
		</div>
	{/if}
</section>

<style>
	.assistente {
		display: grid;
		gap: 1rem;
		padding: 1.2rem 1.4rem;
		border: 1px solid var(--linha);
		border-radius: var(--raio);
		background: var(--superficie);
	}

	header {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
	}

	h2 {
		margin: 0;
		font-size: 1.3rem;
		font-weight: 450;
	}

	h3 {
		margin: 0 0 0.6rem;
		font-size: 1rem;
		font-weight: 500;
	}

	.passos {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.passos button {
		display: inline-flex;
		gap: 0.4rem;
		align-items: center;
		padding: 0.3rem 0.7rem 0.3rem 0.3rem;
		border: 1px solid var(--linha);
		border-radius: 999px;
		background: none;
		color: var(--texto-suave);
		font: inherit;
		font-size: 0.86rem;
		cursor: pointer;
	}

	.numero {
		display: inline-grid;
		place-items: center;
		width: 1.4rem;
		height: 1.4rem;
		border-radius: 50%;
		background: var(--linha);
		font-size: 0.75rem;
	}

	.atual button {
		border-color: var(--acento);
		color: var(--texto);
	}

	.atual .numero,
	.feito .numero {
		background: var(--acento);
		color: var(--sobre-acento);
	}

	.conteudo {
		display: grid;
		gap: 0.8rem;
	}

	label {
		display: grid;
		gap: 0.25rem;
		font-size: 0.85rem;
		color: var(--texto-suave);
	}

	label.caixa {
		display: flex;
		gap: 0.4rem;
		align-items: center;
		color: var(--texto);
	}

	input:not([type='checkbox']),
	select {
		padding: 0.4rem 0.55rem;
		border: 1px solid var(--linha-forte);
		border-radius: var(--raio-pequeno);
		background: var(--fundo);
		color: var(--texto);
		font: inherit;
	}

	fieldset {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 1rem;
		margin: 0;
		padding: 0.5rem 0.8rem;
		border: 1px solid var(--linha);
		border-radius: var(--raio-pequeno);
	}

	legend {
		font-size: 0.82rem;
		color: var(--texto-suave);
	}

	.linha {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
	}

	.escolhidas,
	.achadas,
	.modelos,
	.mudancas {
		display: grid;
		gap: 0.3rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.mudancas {
		padding-left: 1.2rem;
		list-style: disc;
	}

	.escolhidas li,
	.modelos li {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem;
		align-items: baseline;
		font-size: 0.9rem;
	}

	.escolhidas button,
	.achadas button {
		border: 0;
		background: none;
		color: var(--texto-suave);
		font: inherit;
		cursor: pointer;
	}

	.achadas button {
		padding: 0.15rem 0;
		color: var(--texto);
		text-align: left;
	}

	.achadas button:disabled {
		color: var(--texto-fraco);
	}

	.perfis {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
		gap: 0.6rem;
	}

	.perfil {
		display: grid;
		gap: 0.3rem;
		padding: 0.7rem 0.8rem;
		border: 1px solid var(--linha);
		border-radius: var(--raio);
		background: var(--fundo);
		color: var(--texto);
		font: inherit;
		text-align: left;
		cursor: pointer;
	}

	.perfil[aria-pressed='true'] {
		border-color: var(--acento);
		box-shadow: inset 0 0 0 1px var(--acento);
	}

	.selo {
		justify-self: start;
		padding: 0 0.4rem;
		border: 1px solid var(--acento);
		border-radius: 999px;
		font-size: 0.72rem;
		color: var(--acento);
	}

	.suave {
		margin: 0;
		font-size: 0.82rem;
		color: var(--texto-fraco);
	}

	.falta,
	.erro {
		color: var(--acento);
		font-size: 0.85rem;
	}

	.erro {
		margin: 0;
	}

	.acoes {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}

	.acoes button,
	.fechar {
		padding: 0.35rem 0.85rem;
		border: 1px solid var(--linha-forte);
		border-radius: var(--raio-pequeno);
		background: none;
		color: var(--texto);
		font: inherit;
		font-size: 0.88rem;
		cursor: pointer;
	}

	.acoes .principal {
		border-color: var(--acento);
		background: var(--acento);
		color: var(--sobre-acento);
	}

	button:disabled {
		opacity: 0.45;
		cursor: default;
	}
</style>
