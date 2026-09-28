<script lang="ts">
	import AvisoExemplo from '$lib/componentes/AvisoExemplo.svelte';
	import CartaDoCorpus from '$lib/componentes/CartaDoCorpus.svelte';
	import EstadoVazio from '$lib/componentes/EstadoVazio.svelte';
	import Macrotemas from '$lib/componentes/Macrotemas.svelte';
	import Protegida from '$lib/componentes/Protegida.svelte';
	import { usarProjeto } from '$lib/dados/contexto';
	import { rota } from '$lib/estado/url';
	import { contar, formatarData, formatarInteiro, formatarPeriodo, formatarPorcentagem, nomeDaFonte } from '$lib/formato';

	const { fonte, manifesto, revistas, ehExemplo } = usarProjeto();

	const { contagens, recorte } = manifesto;
	const temDocumentos = contagens.documentos > 0;
	const [inicio, fim] = recorte.anos;
	const topicos = fonte.topicos();

	interface Numero {
		id: string;
		rotulo: string;
		valor: number | null;
		texto: string;
		nota: string;
		/** A vista que detalha o número. */
		href?: string;
	}

	// Os números da capa aparecem só se o projeto já os tiver.
	const numeros: Numero[] = [];
	if (temDocumentos) {
		const n = contagens.documentos;
		numeros.push({
			id: 'documentos',
			rotulo: 'Documentos',
			valor: n,
			texto: formatarInteiro(n),
			nota: contagens.classificados ? contar(contagens.classificados, 'classificado') : 'no recorte'
		});
		if (contagens.topicos) {
			numeros.push({
				id: 'topicos',
				rotulo: 'Tópicos',
				valor: contagens.topicos,
				texto: formatarInteiro(contagens.topicos),
				nota: 'descobertos nos resumos'
			});
		}
		if (revistas?.revistas.length) {
			numeros.push({
				id: 'revistas',
				rotulo: 'Revistas',
				valor: revistas.revistas.length,
				texto: formatarInteiro(revistas.revistas.length),
				nota: `fonte: ${recorte.fontes.map(nomeDaFonte).join(', ')}`
			});
		}
		numeros.push({
			id: 'periodo',
			rotulo: 'Período',
			valor: null,
			texto: formatarPeriodo(recorte.anos),
			nota: contar(fim - inicio + 1, 'ano')
		});
		if (manifesto.arquivos.includes('afiliacoes')) {
			const com = contagens.com_afiliacao ?? 0;
			const inst = contagens.com_instituicao ?? 0;
			numeros.push({
				id: 'afiliacao',
				rotulo: 'Com afiliação',
				valor: com / n,
				texto: formatarPorcentagem(com / n),
				nota: `${formatarInteiro(com)} de ${formatarInteiro(n)} documentos; ${formatarInteiro(inst)} com instituição identificada`,
				href: rota('/geografia')
			});
		}
	}

	const IDIOMAS: Record<string, string> = { pt: 'português', en: 'inglês', es: 'espanhol' };
	const idioma = (codigo: string) => IDIOMAS[codigo] ?? codigo;
</script>

<svelte:head>
	<title>{manifesto.projeto.titulo} · mapa da ciência</title>
</svelte:head>

<div class="pagina surgir">
	{#if ehExemplo}
		<AvisoExemplo descricao={manifesto.projeto.descricao ?? ''} />
	{/if}

	<section class="capa" class:sem-carta={!temDocumentos}>
		<div class="capa-texto">
			<p class="rotulo-miudo sobre">Observatório da literatura científica</p>
			<h1>{manifesto.projeto.titulo}</h1>
			<p class="resumo">
				{#if !ehExemplo && manifesto.projeto.descricao}
					{manifesto.projeto.descricao}
				{:else}
					Um retrato do corpus: quantos documentos há, de onde vêm e sobre o que falam. Use o trilho ao
					lado para explorar o mapa, os tópicos, a classificação e a geografia.
				{/if}
			</p>
			<dl class="ficha">
				<div>
					<dt>recorte</dt>
					<dd>{formatarPeriodo(recorte.anos)}</dd>
				</div>
				<div>
					<dt>fontes</dt>
					<dd>{recorte.fontes.map(nomeDaFonte).join(', ')}</dd>
				</div>
				<div>
					<dt>idioma</dt>
					<dd>análise em {idioma(recorte.idioma_analise)}, exibição em {idioma(recorte.idioma_exibicao)}</dd>
				</div>
				<div>
					<dt>gerado</dt>
					<dd>{formatarData(manifesto.gerado_em)}</dd>
				</div>
			</dl>
		</div>

		{#if temDocumentos}
			{#await topicos then t}
				{#if t}
					<div class="capa-carta"><CartaDoCorpus topicos={t} /></div>
				{/if}
			{/await}
		{/if}
	</section>

	{#if temDocumentos}
		<section aria-labelledby="titulo-numeros">
			<h2 id="titulo-numeros" class="visualmente-oculto">O corpus em números</h2>
			<dl class="numeros">
				{#each numeros as n (n.id)}
					<div class="numero-item">
						<dt class="rotulo-miudo">{n.rotulo}</dt>
						<dd>
							{#if n.href}
								<a class="valor" href={n.href} data-testid="numero-{n.id}" data-valor={n.valor ?? undefined}>{n.texto}</a>
							{:else}
								<span class="valor" data-testid="numero-{n.id}" data-valor={n.valor ?? undefined}>{n.texto}</span>
							{/if}
							<span class="nota">{n.nota}</span>
						</dd>
					</div>
				{/each}
			</dl>
		</section>

		{#await topicos}
			<p class="carregando" role="status">Carregando os macrotemas…</p>
		{:then t}
			<Protegida oque="a vista Início">
				{#if t}
					<Macrotemas topicos={t} totalDocumentos={contagens.documentos} />
				{:else}
					<p class="carregando" data-testid="proximo-passo">
						Documentos coletados. Próximo passo: <code>mapa topicos</code> monta o mapa e os macrotemas.
					</p>
				{/if}
			</Protegida>
		{:catch erro}
			<p class="falha" role="alert">Não foi possível carregar os tópicos: {erro.message}</p>
		{/await}
	{:else}
		<EstadoVazio titulo="Este projeto ainda não tem dados." sobretitulo="Projeto vazio">
			<p>
				Rode <code>mapa coletar</code> e depois <code>mapa topicos</code>.
			</p>
			<p>
				A coleta traz os documentos do recorte ({formatarPeriodo(recorte.anos)}), e a etapa de tópicos
				monta o mapa. Depois, recarregue esta página.
			</p>
		</EstadoVazio>
	{/if}
</div>

<style>
	.pagina {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: clamp(2rem, 4vw, 3rem);
	}

	.capa {
		display: grid;
		grid-template-columns: minmax(0, 1.25fr) minmax(16rem, 25rem);
		align-items: center;
		gap: clamp(1.5rem, 4vw, 4rem);
	}

	.capa.sem-carta {
		grid-template-columns: minmax(0, 1fr);
	}

	.capa-texto {
		display: grid;
		gap: 1.1rem;
		max-width: 44rem;
	}

	.sobre {
		color: var(--acento);
	}

	h1 {
		font-size: clamp(2.5rem, 4.8vw, 4.1rem);
		font-weight: 360;
		line-height: 1.04;
		letter-spacing: -0.02em;
	}

	.resumo {
		font-size: 1.12rem;
		color: var(--texto-suave);
		max-width: 38rem;
	}

	.ficha {
		display: grid;
		grid-template-columns: max-content minmax(0, 1fr);
		gap: 0.3rem 1rem;
		margin: 0.4rem 0 0;
		padding-top: 1rem;
		border-top: 1px solid var(--linha);
		font-size: 0.85rem;
	}

	.ficha div {
		display: contents;
	}

	.ficha dt {
		font-family: var(--fonte-mono);
		font-size: 0.72rem;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--texto-suave);
		padding-top: 0.12rem;
	}

	.ficha dd {
		margin: 0;
	}

	.capa-carta {
		width: 100%;
		max-width: 25rem;
		justify-self: end;
	}

	/* Flex, e não grade de colunas iguais: cada número ocupa a largura que precisa
	   ("2010–2025" é bem mais largo que "28") e a linha quebra se faltar espaço. */
	.numeros {
		display: flex;
		flex-wrap: wrap;
		margin: 0;
		border-top: 1px solid var(--linha-forte);
		border-bottom: 1px solid var(--linha);
	}

	.numero-item {
		flex: 1 1 auto;
		display: grid;
		align-content: start;
		gap: 0.5rem;
		padding: 1.1rem 1.25rem 1.3rem;
		border-left: 1px solid var(--linha);
	}

	.numero-item:first-child {
		border-left: 0;
		padding-left: 0;
	}

	.numero-item dd {
		display: grid;
		gap: 0.35rem;
		margin: 0;
	}

	a.valor {
		color: var(--texto);
		text-decoration: underline;
		text-decoration-thickness: 1px;
		text-underline-offset: 0.12em;
		text-decoration-color: var(--linha-forte);
	}

	a.valor:hover {
		text-decoration-color: var(--acento);
	}

	.valor {
		font-family: var(--fonte-titulo);
		font-size: clamp(2.4rem, 3.6vw, 3.4rem);
		font-weight: 330;
		line-height: 1;
		letter-spacing: -0.02em;
		font-variant-numeric: lining-nums;
		font-variation-settings: 'opsz' 144;
		white-space: nowrap;
	}

	.nota {
		max-width: 15rem;
		font-family: var(--fonte-mono);
		font-size: 0.74rem;
		color: var(--texto-suave);
	}

	.carregando,
	.falha {
		color: var(--texto-suave);
		font-size: 0.9rem;
	}

	@media (max-width: 980px) {
		.capa {
			grid-template-columns: minmax(0, 1fr);
		}

		.capa-carta {
			justify-self: start;
			max-width: 22rem;
		}
	}

	@media (max-width: 560px) {
		.numero-item,
		.numero-item:first-child {
			border-left: 0;
			padding-left: 0;
			border-top: 1px solid var(--linha);
		}

		.numero-item:first-child {
			border-top: 0;
		}
	}
</style>
