"""As três camadas de configuração: default (skill) < infra (sua máquina) < projeto (versionado).

A camada do projeto é versionada e chega por clone ou pull request. Ela tem uma **lista positiva**
do que pode definir — qualquer outra coisa é erro. Lista de proibidos não serve aqui: basta um
jeito novo de escrever a mesma coisa (`[alvo.x]`, chave no topo, tabela com outro nome) para o
arquivo voltar a entregar conexão.
"""
import tomllib
from pathlib import PurePosixPath, Path

# o que o arquivo do projeto pode definir — nada além disto
PROJETO_PERMITE = ("alvos", "aceite", "relatorio", "severidade")
RELATORIO_PERMITE = ("pasta", "formato", "ignorar_em")
# defesa em profundidade: nenhum nome de conexão, em qualquer profundidade
CHAVES_DE_CONEXAO = ("tipo", "host", "porta", "usuario", "senha", "senha_env", "metricas_url",
                     "context", "url", "password", "token")


class ConfigInvalida(Exception):
    """Configuração que a skill se recusa a interpretar."""


def _ler(caminho):
    if caminho is None:
        return {}
    caminho = Path(caminho)
    if not caminho.exists():
        return {}
    try:
        with caminho.open("rb") as arquivo:
            return tomllib.load(arquivo)
    except tomllib.TOMLDecodeError as erro:
        raise ConfigInvalida(f"{caminho.name}: TOML inválido — {erro}") from erro
    except OSError as erro:
        raise ConfigInvalida(f"{caminho.name}: não consegui ler — {erro}") from erro


def _achatar(dados, prefixo=""):
    """{'a': {'b': 1}} -> {'a.b': 1}.

    Lista de tabelas (`[[alvo]]`, `[[aceite]]`) fica de fora: tem tratamento próprio. Lista de
    valores entra — senão `alvos = [...]` sumiria do efetivo e do `--explicar` sem uma palavra.
    """
    saida = {}
    for chave, valor in dados.items():
        nome = f"{prefixo}{chave}"
        if isinstance(valor, dict):
            saida.update(_achatar(valor, f"{nome}."))
        elif isinstance(valor, list) and valor and all(isinstance(i, dict) for i in valor):
            continue
        else:
            saida[nome] = valor
    return saida


def _validar_projeto(dados, nome_arquivo):
    """O arquivo versionado do projeto: só o que está na lista positiva, e nunca conexão."""
    for chave in dados:
        if chave not in PROJETO_PERMITE:
            raise ConfigInvalida(
                f"{nome_arquivo}: o arquivo do projeto não define {chave!r}. Aqui entram apenas "
                f"{', '.join(PROJETO_PERMITE)} — conexão (host, porta, usuário, credencial) mora "
                f"no alvos.toml da sua máquina, fora do repositório.")

    for chave in _achatar(dados):
        folha = chave.split(".")[-1].casefold()
        if folha in CHAVES_DE_CONEXAO:
            raise ConfigInvalida(
                f"{nome_arquivo}: a chave {chave!r} descreve conexão, e o arquivo do projeto é "
                f"versionado. Declare o alvo no alvos.toml da sua máquina.")

    alvos = dados.get("alvos", [])
    if not isinstance(alvos, list) or not all(isinstance(n, str) for n in alvos):
        raise ConfigInvalida(f"{nome_arquivo}: `alvos` precisa ser uma lista de NOMES de alvos "
                             f"declarados no alvos.toml, por exemplo alvos = [\"cluster\"].")

    relatorio = dados.get("relatorio", {})
    if not isinstance(relatorio, dict):
        raise ConfigInvalida(f"{nome_arquivo}: `relatorio` precisa ser uma tabela")
    for chave in relatorio:
        if chave not in RELATORIO_PERMITE:
            raise ConfigInvalida(f"{nome_arquivo}: relatorio.{chave} não existe; disponíveis: "
                                 f"{', '.join(RELATORIO_PERMITE)}")
    pasta = relatorio.get("pasta")
    if pasta is not None:
        caminho = PurePosixPath(str(pasta))
        if caminho.is_absolute() or ".." in caminho.parts:
            raise ConfigInvalida(f"{nome_arquivo}: relatorio.pasta precisa ser relativa e dentro do "
                                 f"projeto — {pasta!r} não é.")


class Config:
    def __init__(self, camadas, alvos_escolhidos, aceites):
        self._valores, self._origens = {}, {}
        for origem, dados in camadas:                  # ordem: default, infra, projeto
            for chave, valor in _achatar(dados).items():
                self._valores[chave] = valor
                self._origens[chave] = origem
        self._alvos = alvos_escolhidos
        self._aceites = aceites

    def valor(self, chave):
        return self._valores.get(chave)

    def origem(self, chave):
        return self._origens.get(chave)

    def alvos_escolhidos(self):
        return list(self._alvos)

    def aceites(self):
        return list(self._aceites)

    def explicar(self):
        """[(chave, valor, origem)] em ordem estável — saída que o usuário compara entre rodadas."""
        return sorted(((chave, self._valores[chave], self._origens[chave])
                       for chave in self._valores), key=lambda linha: linha[0])


def carregar(padrao, infra, projeto):
    dados_padrao, dados_infra, dados_projeto = _ler(padrao), _ler(infra), _ler(projeto)
    _validar_projeto(dados_projeto, Path(projeto).name if projeto else ".sw-infra-audit.toml")

    aceites = [dict(a, origem="infra") for a in dados_infra.get("aceite", [])]
    aceites += [dict(a, origem="projeto") for a in dados_projeto.get("aceite", [])]

    return Config(
        camadas=[("default", dados_padrao), ("infra", dados_infra), ("projeto", dados_projeto)],
        alvos_escolhidos=dados_projeto.get("alvos", []),
        aceites=aceites)
