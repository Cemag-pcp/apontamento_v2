import os
import requests

WHATSAPP_GRAPH_URL = "https://graph.facebook.com/{version}/{phone_number_id}/messages"


def _whatsapp_config():
    return {
        "version": os.environ.get("whatsapp_api_version", "v21.0"),
        "phone_number_id": os.environ.get("whatsapp_phone_number_id"),
        "token": os.environ.get("whatsapp_token"),
    }


def enviar_whatsapp_template(telefone, template_name, idioma, parametros_corpo):
    """
    Envia uma mensagem de template pela WhatsApp Cloud API (Meta).

    telefone: numero completo com DDI, ex: "5511999998888" (sem "+" e sem espacos)
    parametros_corpo: lista de strings, na ordem das variaveis {{1}}, {{2}}, ... do corpo do template
    """
    config = _whatsapp_config()
    if not config["phone_number_id"] or not config["token"]:
        return None, "Credenciais do WhatsApp nao configuradas (whatsapp_phone_number_id/whatsapp_token)."

    url = WHATSAPP_GRAPH_URL.format(version=config["version"], phone_number_id=config["phone_number_id"])
    headers = {"Authorization": f"Bearer {config['token']}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": telefone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": idioma},
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": str(p)} for p in parametros_corpo],
                }
            ],
        },
    }

    print(f"[WhatsApp] enviando template '{template_name}' para {telefone}")

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=(10, 30))
    except requests.RequestException as exc:
        print(f"[WhatsApp] erro de conexao: {exc}")
        return None, f"Erro de conexao com o WhatsApp: {exc}"

    print(f"[WhatsApp] status: {response.status_code}")
    print(f"[WhatsApp] resposta: {response.text}")

    try:
        resp_json = response.json()
    except ValueError:
        resp_json = {}

    if not response.ok:
        detail = (resp_json.get("error") or {}).get("message") or response.text
        return None, f"WhatsApp retornou erro: {detail}"

    message_id = (resp_json.get("messages") or [{}])[0].get("id")
    return message_id, None


def enviar_falta_de_peca(telefone, celula, conjunto, pecas_faltantes):
    """
    Dispara o template 'falta_de_peca_2'.

    celula: nome/numero da celula que informou a interrupcao ({{1}})
    conjunto: identificacao do conjunto/ordem ({{2}})
    pecas_faltantes: lista de strings, uma por peca em falta - viram uma unica
        variavel ({{3}}), ja que o template do WhatsApp nao suporta uma
        quantidade variavel de variaveis. A API rejeita \n/\t literal (e mais
        de 4 espacos seguidos) dentro do valor de uma variavel, mas nao
        rejeita \r (carriage return) - os clientes do WhatsApp renderizam
        \r como quebra de linha mesmo assim. Comportamento nao documentado
        pela Meta: se um dia pararem de aceitar, voltar pro formato numerado
        em uma linha so.
    """
    lista_pecas = "\r".join(f"- {peca}" for peca in pecas_faltantes)
    return enviar_whatsapp_template(
        telefone=telefone,
        template_name="falta_de_peca_2",
        idioma="pt_BR",
        parametros_corpo=[celula, conjunto, lista_pecas],
    )


def destinatarios_falta_de_peca():
    """
    Numeros (com DDI, sem "+") que recebem a notificacao de falta de peca,
    cadastrados em Cadastro > Configuracoes.
    """
    from cadastro.models import DestinatarioNotificacao

    return list(
        DestinatarioNotificacao.objects
        .filter(tipo_notificacao='falta_peca', ativo=True)
        .values_list('telefone', flat=True)
    )


def enviar_notificacao_qualidade(telefone, mensagem):
    """
    Dispara o template 'notificacao_qualidade_1' (cabecalho fixo "ATENCAO!!").

    mensagem: texto ja formatado que vai em {{1}}, ex:
        "Faz *2* dias que nao e registrado inspecao no setor de *Pintura*."
    Suporta negrito do WhatsApp (*texto*), mas nao pode ter \n/\t nem mais
    de 4 espacos seguidos (restricao da API pra valor de variavel) - use \r
    se precisar de quebra de linha (ver enviar_falta_de_peca).
    """
    return enviar_whatsapp_template(
        telefone=telefone,
        template_name="notificacao_qualidade_1",
        idioma="pt_BR",
        parametros_corpo=[mensagem],
    )


def destinatarios_notificacao_qualidade():
    """
    Numeros (com DDI, sem "+") que recebem a notificacao de qualidade,
    cadastrados em Cadastro > Configuracoes.
    """
    from cadastro.models import DestinatarioNotificacao

    return list(
        DestinatarioNotificacao.objects
        .filter(tipo_notificacao='notificacao_qualidade', ativo=True)
        .values_list('telefone', flat=True)
    )
