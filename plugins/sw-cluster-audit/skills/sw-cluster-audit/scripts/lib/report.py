"""Schema do report.json v1: marcador n/a, montagem, validação, split_image."""
SCHEMA_VERSION = 1


def na(reason):
    """Marca um dado/seção como não coletado."""
    return {"status": "n/a", "reason": reason}


def new_report(generated_at, context):
    """Esqueleto de um report.json v1. `generated_at` vem do caller (não Date.now no script)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "cluster": {"context": context},
        "scope": {},
        "health": {},
        "nodes": [], "services": [], "networks": [],
        "secrets": [], "configs": [], "findings": [], "not_collected": [],
        # o agente preenche {service_name: "análise específica do componente"} após ler os fatos
        "components_analysis": {},
    }


def is_valid(r):
    return (r.get("schema_version") == SCHEMA_VERSION
            and bool(r.get("generated_at"))
            and "context" in (r.get("cluster") or {}))


def split_image(ref):
    """'app:1.2', 'web@sha256:..', 'registry.io:5000/app:2.0' -> {image, tag, digest}.

    Ignora o ':' do host:port (só considera tag o ':' depois da última '/').
    """
    if not ref:
        return {"image": None, "tag": None, "digest": None}
    digest = None
    if "@" in ref:
        ref, digest = ref.split("@", 1)
        digest = digest or None
    tag = None
    colon = ref.rfind(":")
    if colon > ref.rfind("/"):
        ref, tag = ref[:colon], ref[colon + 1:]
    return {"image": ref, "tag": tag, "digest": digest}
