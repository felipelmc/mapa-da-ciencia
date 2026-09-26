<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { parametrosDoHash } from '$lib/url';

	let { children } = $props();

	// Com router por hash, `resolve()` devolve `<base>#/rota`.
	const hrefInicio = resolve('/');
	const hrefMapa = resolve('/mapa');

	const doSearch = $derived(Object.fromEntries(page.url.searchParams));
	const doHash = $derived(Object.fromEntries(parametrosDoHash(page.url)));

	let atualizacoes = 0;
	$effect(() => {
		atualizacoes += 1;
		window.__rotaDebug = {
			href: page.url.href,
			pathname: page.url.pathname,
			search: page.url.search,
			hash: page.url.hash,
			routeId: page.route.id,
			searchParams: doSearch,
			hashParams: doHash,
			hrefInicio,
			hrefMapa,
			atualizacoes
		};
	});

	// Simulam o que o app real fará ao mudar um filtro: trocar só os parâmetros.
	// Três formas de montar o destino, para comparar no subcaminho.
	const opcoesGoto = { replaceState: true, keepFocus: true, noScroll: true };
	const gotoComResolve = () => goto(`${hrefMapa}?anos=2000-2005&cor=area`, opcoesGoto);
	const gotoHashRelativo = () => goto('#/mapa?anos=1990-1995&cor=area', opcoesGoto);
	const gotoQueryAntesDoHash = () => goto('?anos=1980-1985&cor=area#/mapa', opcoesGoto);
</script>

<nav>
	<a data-testid="link-inicio" href={hrefInicio}>Início</a>
	<a data-testid="link-mapa" href={hrefMapa}>Mapa</a>
	<a data-testid="link-mapa-params" href="#/mapa?anos=2012-2020&cor=topico">Mapa (2012–2020, cor=tópico)</a>
	<button data-testid="botao-goto" type="button" onclick={gotoComResolve}>goto(resolve + ?anos)</button>
	<button data-testid="botao-goto-hash" type="button" onclick={gotoHashRelativo}>goto('#/mapa?anos')</button>
	<button data-testid="botao-goto-query" type="button" onclick={gotoQueryAntesDoHash}>goto('?anos#/mapa')</button>
</nav>

<aside data-testid="painel-url">
	<div>rota: <code data-testid="route-id">{page.route.id}</code></div>
	<div>hash: <code>{page.url.hash}</code></div>
	<div>
		page.url.searchParams:
		<code data-testid="search-params">{JSON.stringify(doSearch)}</code>
	</div>
	<div>
		parâmetros do hash:
		<code data-testid="hash-params">{JSON.stringify(doHash)}</code>
	</div>
</aside>

{@render children()}

<style>
	:global(html, body) {
		margin: 0;
		height: 100%;
		background: #0a0e1f;
		color: #d8dcef;
		font-family: system-ui, sans-serif;
		font-size: 13px;
	}
	nav {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		z-index: 2;
		display: flex;
		gap: 12px;
		align-items: center;
		padding: 8px 12px;
		background: rgb(10 14 31 / 0.85);
	}
	nav a {
		color: #8fb4ff;
	}
	aside {
		position: fixed;
		bottom: 8px;
		left: 8px;
		z-index: 2;
		padding: 6px 8px;
		background: rgb(10 14 31 / 0.85);
		border: 1px solid #2a3150;
		border-radius: 4px;
		line-height: 1.5;
	}
	code {
		color: #ffd58f;
	}
</style>
