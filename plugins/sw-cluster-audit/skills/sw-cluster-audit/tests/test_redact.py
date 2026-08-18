import json
import pathlib

from lib.redact import redact_container, redact_service, scrub_info, redact_labels

FX = pathlib.Path(__file__).parent / "fixtures"


def _load(n):
    return json.loads((FX / n).read_text())


def test_container_env_vira_chaves_sem_valor():
    out = redact_container(_load("inspect_container_secret.json"))
    assert out["env_keys"] == ["DB_PASSWORD", "PORT"]
    dumped = json.dumps(out)
    assert "should-not-leak" not in dumped   # Labels, Cmd, Healthcheck e Sysctls TODOS descartados
    assert "supersecret" not in dumped       # valor de env nunca aparece
    assert out["image"] == "myapp:1.2" and out["user"] == "root"


def test_container_mantem_campos_whitelisted():
    out = redact_container(_load("inspect_container_secret.json"))
    assert out["privileged"] is False and out["cap_add"] == ["NET_ADMIN"]
    assert out["mounts"] == [{"type": "bind", "source": "/data", "target": "/app/data"}]
    assert out["ports"] == [{"port": "80/tcp", "host_ip": "0.0.0.0", "host_port": "8080"}]


def test_service_command_args_labels_nao_vazam():
    out = redact_service(_load("inspect_service_secret.json"))
    dumped = json.dumps(out)
    assert "abc123" not in dumped and "zzz" not in dumped          # Args/Env não vazam
    assert "zzz-label-should-not-leak" not in dumped               # Spec.Labels não-traefik não vaza
    assert "hashedsecret-should-not-leak" not in dumped            # basicauth do traefik redigido
    assert out["env_keys"] == ["API_KEY"] and out["name"] == "web"


def test_routing_labels_extrai_roteamento_e_redige_basicauth():
    rl = redact_labels({
        "traefik.http.routers.web.rule": "Host(`app.x`)",
        "traefik.http.routers.web.entrypoints": "websecure",
        "traefik.http.middlewares.auth.basicauth.users": "admin:$apr1$leak",
        "com.docker.stack.namespace": "not-traefik-excluded",
    })
    assert rl["traefik.http.routers.web.rule"] == "Host(`app.x`)"      # roteamento visível
    assert rl["traefik.http.routers.web.entrypoints"] == "websecure"
    assert rl["traefik.http.middlewares.auth.basicauth.users"] == "***"  # valor sensível redigido
    assert "com.docker.stack.namespace" not in rl                     # fora do prefixo → excluído


def test_cred_embutida_em_url_de_label_e_redigida():
    # chave .url não casa o regex, mas a cred no valor não pode vazar
    rl = redact_labels({
        "traefik.http.services.api.loadbalancer.server.url": "http://user:pass@backend:8080",
        "traefik.http.middlewares.fa.forwardauth.address": "http://admin:s3cr3t@auth:4181",
    })
    dumped = json.dumps(rl)
    assert "user:pass" not in dumped and "s3cr3t" not in dumped
    assert "backend:8080" in rl["traefik.http.services.api.loadbalancer.server.url"]  # host preservado


def test_scrub_info_redige_cred_do_proxy():
    out = scrub_info(_load("docker_info_proxy.json"))
    assert "user:pass" not in json.dumps(out)
    assert out["server_version"] == "25.0"


def test_campo_desconhecido_e_descartado():
    out = redact_container({"Config": {"Image": "x"}, "CampoNovoDaAPI": {"secret": "leak-token-9f2a"}})
    assert "CampoNovoDaAPI" not in out and "leak-token-9f2a" not in json.dumps(out)
