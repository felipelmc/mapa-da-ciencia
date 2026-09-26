#!/usr/bin/env bash
# Smoke test do pacote: instala o wheel num ambiente limpo (sem Node, sem o código-fonte)
# e confere que a CLI funciona e que `mapa painel --exemplo` serve a interface e os dados.
#
# Uso (da raiz do repo, depois de `uv build` com a interface empacotada):
#     bash scripts/testar_wheel.sh dist/mapa_da_ciencia-*.whl
set -euo pipefail

WHEEL="${1:?informe o caminho do wheel}"
PORTA="${PORTA:-8799}"
TMP="$(mktemp -d)"
trap 'kill "${PID:-0}" 2>/dev/null || true; rm -rf "$TMP"' EXIT

echo "== ambiente limpo em $TMP"
uv venv -q "$TMP/venv" --python 3.12
uv pip install -q --python "$TMP/venv/bin/python" "$WHEEL"

echo "== CLI"
"$TMP/venv/bin/mapa" --versao

echo "== o wheel traz a interface compilada?"
"$TMP/venv/bin/python" - <<'PY'
from mapa_da_ciencia.servidor.app import pasta_estatico
index = pasta_estatico() / "index.html"
assert index.exists(), f"interface ausente no wheel: {index}"
print("ok:", index)
PY

echo "== mapa painel --exemplo"
cd "$TMP"
"$TMP/venv/bin/mapa" painel --exemplo --nao-abrir --porta "$PORTA" &
PID=$!
for _ in $(seq 1 60); do
  curl -fs "http://127.0.0.1:$PORTA/api/saude" > /dev/null && break
  sleep 0.5
done
curl -fs "http://127.0.0.1:$PORTA/" | grep -qi "<!doctype html" || { echo "a raiz não serviu HTML"; exit 1; }
curl -fs "http://127.0.0.1:$PORTA/" | grep -q "compilada" && { echo "o painel serviu a página de 'interface não compilada'"; exit 1; }
curl -fs "http://127.0.0.1:$PORTA/dados/manifesto.json" | grep -q '"versao_contrato"' || { echo "manifesto ausente"; exit 1; }
echo "== tudo certo"
