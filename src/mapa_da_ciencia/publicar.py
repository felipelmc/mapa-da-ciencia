"""`mapa publicar`: o site estático do projeto, pronto para o GitHub Pages ou qualquer servidor de arquivos.

O site é a interface compilada lendo o contrato de `saida/dados/`, com três diferenças:

- `api: false` no manifesto: sem API, a interface fica só de leitura (sem codificação, sem rodar etapas), e a vista
  Projeto vira a página Metodologia;
- os resumos (e o texto das evidências da classificação, que são trechos deles) só vão com licença Creative
  Commons (ADR 0003); os outros ficam `null`, com a licença à mostra. Com `--sem-resumos`, nenhum vai;
- uma varredura final garante que nenhum arquivo tem e-mail.

Codificações de pessoas nunca estão no contrato (ver `contrato/classificacao.py`). O site é montado numa pasta nova
e trocado de uma vez, como a exportação.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .config import ErroConfig
from .contrato import modelos as m
from .contrato.exportar import exportar
from .documento import pode_publicar_resumo
from .projeto import Projeto
from .texto import EMAIL


@dataclass
class ResumoPublicacao:
    destino: Path
    documentos: int
    resumos_publicados: int
    resumos_retirados: int
    evidencias_retiradas: int
    tamanho_mb: float
    avisos: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        mb = f"{self.tamanho_mb:.1f}".replace(".", ",")
        return (
            f"Site publicado em {self.destino}: {self.documentos} documentos, {self.resumos_publicados} resumos com "
            f"licença aberta e {self.resumos_retirados} retirados; {mb} MB."
        )


def _json(caminho: Path) -> dict:
    return json.loads(caminho.read_text(encoding="utf-8"))


def _gravar(caminho: Path, obj: m.BaseModel) -> None:
    caminho.write_text(json.dumps(obj.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":")), "utf-8")


def publicar(
    projeto: Projeto, destino: Path | None = None, *, sem_resumos: bool = False, estatico: Path | None = None
) -> ResumoPublicacao:
    from .servidor.app import pasta_estatico

    estatico = estatico if estatico is not None else pasta_estatico()
    if not (estatico / "index.html").exists():
        raise ErroConfig(
            "A interface não está no pacote. Instale o mapa-da-ciencia de uma versão publicada, ou compile a interface "
            "(em frontend/: npm ci && npm run empacotar)."
        )
    avisos = exportar(projeto)  # o contrato em dia antes de publicar
    dados = projeto.saida / "dados"
    if not (dados / "manifesto.json").exists():
        raise ErroConfig("O projeto ainda não tem dados. Rode `mapa coletar` e `mapa topicos` antes de publicar.")
    destino = (destino or projeto.saida / "site").resolve()
    novo = destino.with_name(destino.name + ".novo")
    shutil.rmtree(novo, ignore_errors=True)
    shutil.copytree(estatico, novo)
    shutil.copytree(dados, novo / "dados")

    publicados = retirados = evid_retiradas = 0
    abertos: set[str] = set()
    for arq in sorted((novo / "dados" / "detalhes").glob("*.json")):
        frag = m.Fragmento.model_validate(_json(arq))
        for doc, det in frag.documentos.items():
            if det.resumo is None:
                continue
            if not sem_resumos and pode_publicar_resumo(det.licenca):
                publicados += 1
                abertos.add(doc)
                continue
            retirados += 1
            det.resumo = None
            for e in det.evidencias.values():
                if e.evidencia:
                    evid_retiradas += 1
                e.evidencia, e.inicio, e.fim, e.campo = "", None, None, None
        _gravar(arq, frag)

    if (arq := novo / "dados" / "validacao.json").exists():
        val = m.Validacao.model_validate(_json(arq))
        for d in val.divergencias:
            if d.doc not in abertos:
                d.evidencia = ""
        _gravar(arq, val)

    manifesto = m.Manifesto.model_validate(_json(novo / "dados" / "manifesto.json"))
    manifesto = manifesto.model_copy(
        update={
            "api": False,
            "publicacao": m.PublicacaoInfo(
                em=datetime.now(UTC),
                resumos_publicados=publicados,
                resumos_retirados=retirados,
                sem_resumos=sem_resumos,
            ),
        }
    )
    _gravar(novo / "dados" / "manifesto.json", manifesto)

    for arq in (novo / "dados").rglob("*.json"):
        if EMAIL.search(arq.read_text(encoding="utf-8")):
            shutil.rmtree(novo, ignore_errors=True)
            raise ErroConfig(f"Um e-mail apareceu em {arq.name}; a publicação foi interrompida. Avise o projeto.")

    velho = destino.with_name(destino.name + ".velho")
    shutil.rmtree(velho, ignore_errors=True)
    if destino.exists():
        destino.rename(velho)
    novo.rename(destino)
    shutil.rmtree(velho, ignore_errors=True)
    tamanho = sum(a.stat().st_size for a in destino.rglob("*") if a.is_file()) / 1e6
    return ResumoPublicacao(
        destino=destino,
        documentos=manifesto.contagens.documentos,
        resumos_publicados=publicados,
        resumos_retirados=retirados,
        evidencias_retiradas=evid_retiradas,
        tamanho_mb=round(tamanho, 1),
        avisos=avisos,
    )
