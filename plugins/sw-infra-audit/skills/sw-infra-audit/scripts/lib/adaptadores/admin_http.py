"""Adaptador de API de administração — o mais específico, e o mais frágil.

Ele não sabe o que é o produto. Pergunta "que família você é?" olhando quais chaves o JSON de
identificação traz, e a partir daí caminho e extração vêm do arquivo daquela família
(`references/apis/<familia>.toml`).

Prioridade 20: mais específico que o `promql` (30), porque quem fala a API do próprio produto
sabe mais que um exporter genérico. Também é o primeiro a cair em `sem_dados` — depende de
credencial, de porta de administração aberta e de um formato que muda entre versões.

Toda rede passa por `lib/http_get.py` e toda credencial por `lib/credencial.py`. Aqui não se
importa urllib, não se lê variável de ambiente e não se monta header — e este módulo entrega o
OBJETO `Credencial` a `get_autenticado`, que é quem decide se a senha pertence ao destino.

Custo: uma identificação e UM download por endpoint, por componente. As perguntas de `fila`
leem todas o mesmo endpoint de listagem; sem o cache (que vive em `contexto["cache"]`,
compartilhado entre as perguntas do alvo), um broker grande seria baixado inteiro a cada uma.
"""
import json

from lib import catalogo_api, extracao, http_get
from lib import credencial as credencial_mod

ID = "admin_http"


def base_de(url):
    """A raiz da API a partir do que o dono declarou, sem barra no fim."""
    return str(url or "").rstrip("/")


def _sem_dados(pergunta, motivo, **extra):
    return dict({"pergunta": pergunta, "sem_dados": True, "motivo": motivo}, **extra)


def _cache(contexto, nome):
    return contexto.setdefault("cache", {}).setdefault(nome, {})


def _timeout(contexto):
    return contexto.get("http_timeout", contexto["timeout"])


def _motivo_do_status(status, o_que):
    """O motivo que manda procurar no lugar certo. "Não reconheci a família" para um 403 fazia
    o dono revisar catálogo quando o problema era permissão."""
    if status is None:
        return f"{o_que} não respondeu (endereço, porta ou rede)"
    if status == 401:
        return (f"{o_que} respondeu 401: falta credencial — declare `senha_env` no alvos.toml "
                f"com o nome da variável que guarda a senha")
    if status == 403:
        return (f"{o_que} respondeu 403: a credencial não tem permissão para ler — o usuário "
                f"precisa de acesso de leitura a todos os vhosts")
    if 300 <= status < 400:
        return (f"{o_que} redireciona ({status}) — a `admin_url` talvez precise de https ou de "
                f"outro caminho; a skill não segue redirect")
    return f"{o_que} respondeu {status}"


def _buscar(base, caminho, credencial, contexto):
    """(status, documento), com cache por (base, caminho) no alvo."""
    cache = _cache(contexto, "documentos_admin")
    chave = (base, caminho)
    if chave not in cache:
        # NotConfirmed NÃO é capturado: destino fora da allowlist é erro de programação.
        try:
            status, corpo = http_get.get_autenticado(
                f"{base}{caminho}", [http_get.destino(base)], credencial, contexto.get("alvo"),
                timeout=_timeout(contexto))
        except http_get.RespostaGrandeDemais:
            cache[chave] = ("grande", None)
            return cache[chave]
        documento = None
        if status == 200 and corpo:
            try:
                documento = json.loads(corpo)
            except ValueError:
                documento = None
        cache[chave] = (status, documento)
    return cache[chave]


def familia_do_componente(componente, contexto, credencial, familias):
    """(família, motivo) — um dos dois é sempre None.

    Não precisa de cache próprio: o documento de identificação já fica no cache de `_buscar`,
    então repetir a identificação por pergunta não repete a requisição — só reconfere chaves
    num dicionário que já está em memória.
    """
    base = base_de(componente.get("admin_url"))
    motivo, achada = None, None
    for familia in familias:
        identificacao = familia["identificacao"]
        status, documento = _buscar(base, identificacao["caminho"], credencial, contexto)
        if status == 200 and isinstance(documento, dict):
            if all(extracao.ponteiro(documento, f"/{exigida}") is not None
                   for exigida in identificacao["exige_chaves"]):
                achada = familia
                break
            motivo = motivo or ("a API respondeu, mas não reconheci a família de "
                                "administração deste componente")
            continue
        if status == 401 and not identificacao.get("aceita_401"):
            continue
        motivo = motivo or (_motivo_do_status(status, "a API de administração")
                            if status != "grande" else
                            "a identificação da API passou do tamanho máximo de resposta")
    return achada, None if achada else (motivo or "a API de administração não respondeu")


def _com_identidade(valor, identidade):
    """Compõe `objeto = "nome@vhost"` quando o catálogo declara `identidade`.

    `/api/queues` lista filas de todos os vhosts, e `emails` em `/` e em `staging` são duas
    filas: sem isto, no histórico colapsavam numa chave só, e um aceite de `emails` aceitava as
    duas. `@` e não `·`: o dono precisa DIGITAR isto num aceite. Campo ausente sai do objeto em
    vez de virar "None".
    """
    if not identidade or not isinstance(valor, list):
        return valor
    for item in valor:
        partes = [str(item[campo]) for campo in identidade if item.get(campo) is not None]
        item["objeto"] = "@".join(partes)
    return valor


def perguntar(pergunta, componente, contexto):
    """Responde a pergunta, ou devolve `sem_dados` com o motivo real. Nunca levanta."""
    try:
        familias = catalogo_api.familias()
    except catalogo_api.CatalogoInvalido as erro:
        # Catálogo quebrado é bug da skill — mas não pode tirar a resposta de outro adaptador:
        # `nao_se_aplica` deixa o `promql` falar pelo proxy, e o motivo fica se ninguém falar.
        return _sem_dados(pergunta, f"catálogo de API inválido: {erro}", nao_se_aplica=True)

    if not any(p.get("id") == pergunta for familia in familias
               for p in familia.get("pergunta", [])):
        # A marca diz ao `responder` que este motivo não é o útil: sem ela, um proxy sem nada
        # declarado seria mandado declarar `admin_url` em vez de `metricas_url`.
        return _sem_dados(pergunta, "nenhuma API de administração conhecida responde a esta "
                                    "pergunta", nao_se_aplica=True)

    base = base_de(componente.get("admin_url"))
    if not base:
        return _sem_dados(pergunta, "o componente não declara `admin_url` no alvos.toml")

    try:
        credencial = credencial_mod.de_componente(componente, contexto.get("alvo"))
    except credencial_mod.CredencialFaltando as erro:
        return _sem_dados(pergunta, str(erro))

    familia, motivo = familia_do_componente(componente, contexto, credencial, familias)
    if familia is None:
        return _sem_dados(pergunta, motivo)

    declarada = next((p for p in familia.get("pergunta", []) if p["id"] == pergunta), None)
    if declarada is None:
        return _sem_dados(pergunta,
                          f"a API {familia['familia']} não expõe o dado desta pergunta")

    status, documento = _buscar(base, declarada["caminho"], credencial, contexto)
    if status == "grande":
        return _sem_dados(pergunta, f"a resposta da API passou de "
                                    f"{http_get.MAX_BYTES // (1024 * 1024)} MB, grande demais "
                                    f"para ler")
    if documento is None:
        return _sem_dados(pergunta, _motivo_do_status(status, "a consulta desta pergunta")
                          if status != 200 else "a API respondeu, mas não com JSON")

    try:
        valor = extracao.extrair(documento, declarada)
    except extracao.ExtracaoInvalida as erro:
        return _sem_dados(pergunta, f"o catálogo de {familia['familia']} não casa com a "
                                    f"resposta desta API: {erro}")
    if isinstance(valor, dict):
        # pergunta escalar: o catálogo põe o número em `valor` (validado no carregamento)
        valor = valor.get("valor")
    if valor is None:
        return _sem_dados(pergunta, "a API respondeu, mas sem o dado desta pergunta")
    # `[]` é resposta: zero filas é um fato, e nunca dispara limiar
    return {"pergunta": pergunta, "fonte": f"{ID}:{familia['familia']}",
            "valor": _com_identidade(valor, declarada.get("identidade"))}
