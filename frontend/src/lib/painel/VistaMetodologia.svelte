<script lang="ts">
	/**
	 * Metodologia, no site publicado (sem API): como os dados foram gerados, tudo tirado do manifesto. As fontes, o
	 * recorte, as contagens, os modelos com a versão exata (digest), o codebook (hash), as sementes, as durações, as
	 * licenças e o que a publicação retirou; e os links para as explicações da documentação.
	 */
	import type { Manifesto } from '$lib/contrato/tipos';
	import { formatarData, formatarDuracao, formatarInteiro, formatarPeriodo } from '$lib/formato';

	let { manifesto }: { manifesto: Manifesto } = $props();

	const DOCS = 'https://felipelamarca.com/mapa-da-ciencia';
	const ETAPAS: Record<string, string> = {
		coleta: 'Coleta',
		embeddings: 'Embeddings',
		topicos: 'Tópicos',
		geografia: 'Geografia',
		classificacao: 'Classificação'
	};
	const PAPEIS: Record<string, string> = { embeddings: 'Embeddings', classificacao: 'Classificação', rotulos: 'Rótulos dos tópicos' };
	const fontes = $derived(
		manifesto.recorte.fontes.map((f) =>
			f.startsWith('scielo:') ? `SciELO (coleção ${f.slice(7)}), pela ArticleMeta` : f === 'openalex' ? 'OpenAlex' : f
		)
	);
	const c = $derived(manifesto.contagens);
	const e = $derived(manifesto.execucao);
	const pub = $derived(manifesto.publicacao ?? null);
	const licencas = $derived(Object.entries(manifesto.licencas ?? {}).sort((a, b) => b[1] - a[1]));
</script>

<svelte:head>
	<title>Metodologia · mapa da ciência</title>
</svelte:head>

<div class="vista surgir" data-testid="metodologia">
	<header>
		<h1>Metodologia</h1>
		<p class="lide">
			<strong>{manifesto.projeto.titulo}</strong>.{#if manifesto.projeto.descricao}{' '}{manifesto.projeto.descricao}{/if} Como
			estes dados foram gerados, pelo <a href="https://github.com/felipelmc/mapa-da-ciencia">mapa-da-ciencia</a>
			{e.versao_pacote}.
		</p>
	</header>

	<section>
		<h2>Corpus</h2>
		<dl>
			<dt>Fontes</dt>
			<dd>{fontes.join('; ')}</dd>
			<dt>Período</dt>
			<dd>{formatarPeriodo(manifesto.recorte.anos)}</dd>
			<dt>Documentos</dt>
			<dd>
				{formatarInteiro(c.documentos)}; {formatarInteiro(c.topicos ?? 0)} tópicos; {formatarInteiro(c.com_instituicao ?? 0)}
				com instituição identificada; {formatarInteiro(c.classificados ?? 0)} classificados; {formatarInteiro(c.validados ?? 0)}
				na amostra de validação codificada
			</dd>
			<dt>Idiomas</dt>
			<dd>tópicos a partir de textos em <code>{manifesto.recorte.idioma_analise}</code>; o painel e a classificação em <code>{manifesto.recorte.idioma_exibicao}</code></dd>
		</dl>
	</section>

	<section>
		<h2>Modelos e reprodutibilidade</h2>
		<dl data-testid="modelos-metodologia">
			{#each Object.entries(e.modelos ?? {}) as [papel, modelo] (papel)}
				<dt>{PAPEIS[papel] ?? papel}</dt>
				<dd><code>{modelo}</code></dd>
			{/each}
			{#if e.hash_codebook}
				<dt>Codebook</dt>
				<dd><code>{e.hash_codebook}</code> (hash do conteúdo)</dd>
			{/if}
			{#if Object.keys(e.sementes ?? {}).length}
				<dt>Sementes</dt>
				<dd>{Object.entries(e.sementes ?? {}).map(([k, v]) => `${k} = ${v}`).join('; ')}</dd>
			{/if}
			{#if Object.keys(e.duracao_s ?? {}).length}
				<dt>Duração das etapas</dt>
				<dd>{Object.entries(e.duracao_s ?? {}).map(([k, v]) => `${ETAPAS[k] ?? k}: ${formatarDuracao(v)}`).join('; ')}</dd>
			{/if}
			<dt>Contrato de dados</dt>
			<dd>versão {manifesto.versao_contrato}; gerado em {formatarData(manifesto.gerado_em)}</dd>
		</dl>
		<p class="suave">
			Os modelos rodaram localmente, pelo Ollama; o <em>digest</em> depois do <code>@</code> identifica a versão exata. Veja
			<a href="{DOCS}/explicacoes/reprodutibilidade/">Reprodutibilidade</a>.
		</p>
	</section>

	<section>
		<h2>Licenças e publicação</h2>
		{#if licencas.length}
			<ul class="licencas">
				{#each licencas as [licenca, n] (licenca)}<li><code>{licenca}</code>: {formatarInteiro(n)}</li>{/each}
			</ul>
		{/if}
		{#if pub}
			<p data-testid="publicacao">
				Publicado em {formatarData(pub.em)}.
				{#if pub.sem_resumos}Sem resumos, por escolha.{:else}{formatarInteiro(pub.resumos_publicados)} resumos com licença Creative
					Commons estão aqui sem alteração; {formatarInteiro(pub.resumos_retirados)} ficaram de fora (licença não aberta ou
					desconhecida) e aparecem só com o título, os autores e o link.{/if}
				Nenhum e-mail e nenhuma codificação individual de pessoas foram publicados.
			</p>
		{/if}
		<p class="suave">Veja <a href="{DOCS}/explicacoes/privacidade-e-licencas/">Privacidade e licenças</a>.</p>
	</section>

	<section>
		<h2>Como foi feito</h2>
		<ul class="links">
			<li><a href="{DOCS}/explicacoes/fontes/">Fontes de dados</a>: ArticleMeta, OpenAlex e o casamento dos registros</li>
			<li><a href="{DOCS}/explicacoes/topicos/">Como os tópicos são construídos</a></li>
			<li><a href="{DOCS}/explicacoes/geografia/">Geografia da produção</a>: instituições e contagem fracionária</li>
			<li><a href="{DOCS}/explicacoes/classificacao/">Classificação ancorada em evidência</a></li>
			<li><a href="{DOCS}/explicacoes/validacao/">Desenho da validação</a></li>
		</ul>
	</section>
</div>

<style>
	.vista {
		display: grid;
		gap: 1.8rem;
		max-width: 60rem;
	}

	h1 {
		margin: 0;
		font-size: clamp(2.2rem, 4.5vw, 3.2rem);
		font-weight: 380;
	}

	h2 {
		margin: 0 0 0.6rem;
		font-size: 1.15rem;
		font-weight: 500;
	}

	.lide {
		margin: 0.5rem 0 0;
		color: var(--texto-suave);
	}

	dl {
		display: grid;
		grid-template-columns: max-content 1fr;
		gap: 0.4rem 1.2rem;
		margin: 0;
	}

	dt {
		color: var(--texto-suave);
	}

	dd {
		margin: 0;
	}

	.suave {
		margin: 0.6rem 0 0;
		font-size: 0.85rem;
		color: var(--texto-fraco);
	}

	.licencas,
	.links {
		margin: 0;
		padding-left: 1.2rem;
	}

	a {
		color: var(--acento);
	}

	@media (max-width: 640px) {
		dl {
			grid-template-columns: 1fr;
		}
	}
</style>
