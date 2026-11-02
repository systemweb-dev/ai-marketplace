"""Rodada de referência do limite de páginas: tamanho grande, com números fictícios."""
from lib import remediacao
from lib.regras import REGRAS

CONTAGEM = {"SEC_USER_ROOT": 70, "OPS_NO_HEALTHCHECK": 58, "OPS_NO_LIMITS": 40, "SEC_IMAGE_UNPINNED": 24,
            "OPS_JOB_COMPLETED": 8, "OPS_TASK_FAILING": 7, "SEC_DOCKER_SOCK_EXPECTED": 5, "OPS_ENGINE_DRIFT": 1}


# As perguntas caladas e os motivos de uma rodada grande (ver `_mudos_por_motivo`).
MUDOS_POR_MOTIVO = {"nenhuma fonte declarada para este papel": 50,
                    "a fonte respondeu vazio para este componente": 20,
                    "a consulta não terminou dentro do prazo": 9}


QUANTAS_FILAS = 150
RESUMO = ("Texto do agente sobre a rodada: descreve o estado geral e os serviços que pedem atenção. "
          "A segunda frase diz o que mudou desde a rodada anterior e fecha no limite da trava do resumo, "
          "que aceita duas frases e até duzentos e oitenta caracteres.")


def _nome(i):
    return f"stack{i % 12}_servico-de-exemplo-{i}"


def _mudos():
    return [{"componente": _nome(i), "pergunta": "app.disponibilidade_7d", "motivo": motivo}
            for motivo, n in MUDOS_POR_MOTIVO.items() for i in range(n)]


def _achados():
    achados = [{"regra": regra, "objeto": _nome(i % 60), "alvo": "aurora",
                "severidade": REGRAS[regra]["severidade_padrao"],
                "detalhe": "detalhe igual na regra" if n > 20 else f"detalhe da ocorrência {i}"}
               for regra, n in CONTAGEM.items() for i in range(n)]
    achados += [{"regra": "fila_sem_consumidor", "objeto": f"f{i}@/", "alvo": "aurora",
                 "severidade": "high", "detalhe": "parada"} for i in range(3)]
    for achado in achados:
        bloco = remediacao.para(achado["regra"])
        if bloco:
            achado["como_resolver"] = bloco
    return achados


def _filas():
    """Forma de `fila.filas` e `fila.taxa_entrada_saida`: a maioria parada no zero, poucas com ritmo."""
    filas, taxas = [], []
    for i in range(QUANTAS_FILAS):
        objeto = f"pedidos-{i:03d}@/"
        parada, lenta = i < 2, 2 <= i < 5
        prontas = 18000 - i if parada else 120 - i if lenta else 300 - i if i < 26 else 0
        filas.append({"objeto": objeto, "nome": f"pedidos-{i:03d}", "vhost": "/", "prontas": prontas,
                      "nao_confirmadas": 0, "acumuladas": prontas, "consumidores": 0 if parada else 2})
        if i < 26:
            entrada = 4.0 if lenta else 1.5
            taxas.append({"objeto": objeto, "nome": f"pedidos-{i:03d}", "vhost": "/", "entrada": entrada,
                          "saida": 0.0 if parada else 1.0 if lenta else 1.5, "saldo": 0.0})
    return filas, taxas


def _stacks(servicos):
    """As rotas só existem aqui: o HTML não as desenha, e a fixture prova que elas ficam de fora."""
    pilhas = {}
    for s in servicos:
        pilhas.setdefault(s["name"].split("_", 1)[0], []).append(s)
    return [{"stack": nome, "services": lista, "kinds": ["app"], "note": "",
             "routes": [f"{s['name'].split('_', 1)[1]}.exemplo.test" for s in lista],
             "findings_high": 0, "findings_med": 2, "spofs": [lista[0]["name"]]}
            for nome, lista in sorted(pilhas.items())]


def _nos():
    falhas = ['stack1_servico-de-exemplo-1.1: "task: non-zero exit (137)"',
              'stack2_servico-de-exemplo-2.1: "task: non-zero exit (1)"',
              'stack3_servico-de-exemplo-3.1: "task: non-zero exit (137)"']
    return [{"hostname": f"no-{i}", "role": "manager" if i == 0 else "worker", "availability": "active",
             "state": "Ready", "leader": i == 0, "reachability": "reachable", "engine": "26.1.4",
             "platform": "linux/x86_64", "capacity": {"nano_cpus": 4_000_000_000, "mem_bytes": 16 * 1024 ** 3},
             "tasks_running": 20 + i, "tasks_failed": 3 * i, "failed_examples": falhas if i else []}
            for i in range(4)]


def _impacto(i):
    return {"cenario": f"Se o ponto {i} cair", "consequencia": "aplicações param", "impacto": "alto",
            "esforco": "alto", "alvos": [_nome(j) for j in range(8)], "fix": None,
            "plano": [{"passo": f"Passo {j}", "comando": "docker service ls", "porque": "confere"} for j in range(5)]}


def _urls():
    """Oito sites e o máximo gravado por site, com caminhos no limite de 200 caracteres."""
    itens, sites = [], []
    for s in range(8):
        site = f"sistema-{s}.exemplo.invalid"
        for i in range(50):
            caminho = f"/area-{i}/" + "recurso-de-exemplo/" * 9 + "fim"
            itens.append({"nome": f"{site}{caminho}", "site": site, "caminho": caminho, "acessos": 9000 - 100 * i - s,
                          "erros": 40 - i if i < 5 else 0, "pct_5xx": 1.5 if i < 5 else 0.0, "p95_ms": 2400.0 - i})
        sites.append({"site": site, "acessos": 120000 - s})
    cobertas = [{"inicio": "2026-10-31T10:00:00Z", "fim": "2026-10-31T11:00:00Z", "linhas": 5000, "amostrada": True}] * 24
    return {"pergunta": "entrada.urls_mais_acessadas", "fonte": "logql:exemplo", "valor": itens, "sites": sites,
            "janelas": {"total": 24, "cobertas": cobertas, "amostradas": 24, "descartadas": 0, "falhas": [],
                        "amostra": True}}


def _recomendacoes():
    return [{"alvo": "aurora", "titulo": f"Recomendação {i} para reduzir o risco do serviço de exemplo",
             "porque": "Motivo escrito pelo agente, longo o bastante para ocupar duas linhas na página. " * 2,
             "comando": f"docker service update --limit-memory 512M --limit-cpu 1 stack{i}_servico-de-exemplo-{i}",
             "impacto": "alto", "esforco": "baixo"} for i in range(8)]


def _nao_confirmado(nome):
    return {"nome": nome, "tipo": "docker", "onde": f"context: {nome}", "saude": "⚪", "coletado": False,
            "dimensoes": {}, "fatos": {}, "componentes": [], "achados": [], "cobertura": {},
            "analise": "", "nao_coletado": [{"o_que": nome, "motivo": "alvo não confirmado nesta execução"}]}


def relatorio_grande():
    servicos = [{"name": _nome(i), "replicas": "1/1", "tasks_failed": 0, "image": "img", "kind": "app"}
                for i in range(60)]
    componentes = [{"nome": s["name"], "papel": "app", "respostas": [
        {"pergunta": "app.cpu", "valor": 1.2, "fonte": "promql:cadvisor"},
        {"pergunta": "app.memoria", "valor": 2.1e8, "fonte": "promql:cadvisor"}], "achados": []} for s in servicos]
    filas, taxas = _filas()
    componentes.append({"nome": "stack0_broker", "papel": "fila", "achados": [], "respostas": [
        {"pergunta": "fila.filas", "valor": filas, "fonte": "admin_http:broker"},
        {"pergunta": "fila.taxa_entrada_saida", "valor": taxas, "fonte": "admin_http:broker"}]})
    componentes.append({"nome": "stack0_proxy", "papel": "entrada", "achados": [], "respostas": [_urls()]})
    fatos = {"services": servicos, "nodes": _nos(), "stacks": _stacks(servicos),
             "impact_points": [_impacto(i) for i in range(10)],
             "disk": [{"tipo": t, "total": "40", "ativo": "12", "tamanho": "7.1GB", "recuperavel": "1.2GB (17%)"}
                      for t in ("Images", "Containers", "Local Volumes", "Build Cache")],
             "tls": {"status": "ok", "days_left": 200, "not_after": "2027-05-20T00:00:00Z", "certs": [
                 {"file": n, "label": n, "status": "ok", "days_left": 200, "not_after": "2027-05-20T00:00:00Z"}
                 for n in ("cert.pem", "ca.pem")]}}
    alvo = {"nome": "aurora", "tipo": "docker", "onde": "context: aurora", "saude": "🟡", "coletado": True,
            "dimensoes": {}, "fatos": fatos, "componentes": componentes, "achados": _achados(),
            "cobertura": {"pct": 62, "mudos": _mudos()},
            "analise": "", "nao_coletado": [{"o_que": "métricas", "motivo": "fonte sem resposta"}]}
    fora = [_nao_confirmado(n) for n in ("boreal", "cirro", "delta")]
    return {"schema_version": 3, "generated_at": "2026-11-01T10:00:00Z", "alvos": [alvo, *fora],
            "inventario": [{"nome": a["nome"], "tipo": "docker", "onde": a["onde"], "saude": a["saude"]}
                           for a in [alvo, *fora]],
            "aceites": [{"alvo": "aurora", "componente": _nome(i), "regra": "SEC_USER_ROOT", "objeto": _nome(i),
                         "motivo": "Decisão registrada pelo dono, revisada na última rodada de auditoria.",
                         "desde": "2026-01-01", "revisar_em": "2027-01-01", "origem": "alvos", "vencido": False}
                        for i in range(4)],
            "historico": {"vs": "2026-10-01_1000", "novos": [], "resolvidos": []}, "resumo": RESUMO,
            "fortes": [f"Ponto forte {i}, com uma frase inteira escrita pelo agente" for i in range(7)],
            "fracos": [f"Ponto fraco {i}, com uma frase inteira escrita pelo agente" for i in range(8)],
            "recomendacoes": _recomendacoes(),
            "nota_geral": {"valor": 79, "faixa": "atencao", "parcial": False, "online": 57, "base": 57,
                           "teto": 79, "parcelas": {}}}
