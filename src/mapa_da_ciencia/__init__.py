"""mapa-da-ciencia: observatório da literatura científica com modelos de linguagem locais."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mapa-da-ciencia")
except PackageNotFoundError:  # rodando direto da árvore de código, sem instalação
    __version__ = "0.0.0+desconhecida"
