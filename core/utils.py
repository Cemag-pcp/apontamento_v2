import os
import gspread
import pandas as pd
from datetime import datetime, timedelta
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from datetime import timedelta as dt_timedelta
# from django.db import transaction
# from django.utils import timezone as dj_timezone
# from .models import Profile, Notificacao, RegistroNotificacao
# from solicitacao_almox.models import SolicitacaoRequisicao, SolicitacaoTransferencia

# Constantes de alerta
# LIMITE_ERROS = 20
# FREQUENCIA_ALERTA_ERROS = dt_timedelta(days=2)  # ajuste conforme desejado
# CACHE_DF = None 
# CACHE_EXPIRATION_TIME = datetime.min 
# CACHE_DURATION = timedelta(hours=24) 

def notificar_ordem(ordem):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "ordens_iniciadas",
        {
            "type": "enviar_ordem",
            "data": {
                "ordem": ordem.ordem,
                "ultima_atualizacao": ordem.ultima_atualizacao.isoformat()
            }
        }
    )


def notificar_acao_almox(tipo_acao, tipo_solicitacao, solicitacao_id):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "almox_solicitacoes",
        {
            "type": "enviar_acao_almox",
            "data": {
                "acao": tipo_acao,
                "tipo_solicitacao": tipo_solicitacao,
                "solicitacao_id": solicitacao_id,
            },
        },
    )

# def notificacao_almoxarifado(
#     titulo: str,
#     mensagem: str,
#     rota_acesso: str,
#     tipo: str = "info",
#     chave: str = None,
#     frequencia: dt_timedelta = None,
# ):
#     # 1) Controle de frequência
#     if chave and frequencia:
#         agora = dj_timezone.now()
#         try:
#             registro = RegistroNotificacao.objects.get(chave=chave)
#             if agora - registro.ultimo_envio < frequencia:
#                 print(f"🔕 Notificação para a chave '{chave}' pulada.")
#                 return
#         except RegistroNotificacao.DoesNotExist:
#             pass
#     elif chave or frequencia:
#         raise ValueError("Para notificações periódicas, 'chave' e 'frequencia' devem ser fornecidos.")

#     profiles_to_notify = Profile.objects.filter(tipo_acesso="almoxarifado")
#     if not profiles_to_notify.exists():
#         print("AVISO: Nenhum usuário com perfil de destino foi encontrado.")
#         return

#     # 2) Escritas em transação
#     try:
#         with transaction.atomic():
#             notificacoes_criadas = 0
#             for profile in profiles_to_notify:
#                 Notificacao.objects.create(
#                     profile=profile,
#                     rota_acesso=rota_acesso,
#                     titulo=titulo,
#                     mensagem=mensagem,
#                     tipo=tipo,
#                 )
#                 notificacoes_criadas += 1

#             if chave:
#                 RegistroNotificacao.objects.update_or_create(
#                     chave=chave,
#                     defaults={"ultimo_envio": dj_timezone.now()},
#                 )

#             if notificacoes_criadas > 0:
#                 print(f"✅ Transação concluída: {notificacoes_criadas} notificações criadas com sucesso.")
#     except Exception as e:
#         print(f"❌ ERRO na transação ao criar notificações: {e}. Rollback executado.")

# def verificar_e_notificar_requisicoes_pendentes():
#     """
#     Verifica o número total de requisições pendentes e envia uma notificação
#     se o limite de 30 for atingido.
#     Usa um controle de frequência para não enviar múltiplos alertas seguidos.
#     """
#     requisicoes_pendentes = SolicitacaoRequisicao.objects.filter(
#         entregue_por__isnull=True, data_entrega__isnull=True
#     ).count()

#     if requisicoes_pendentes >= 30:
#         print(f"⚠️ Limite atingido! {requisicoes_pendentes} requisições pendentes. Tentando notificar...")

#         notificacao_almoxarifado(
#             titulo="Alerta: Alto Volume de Requisições",
#             mensagem=f"Existem {requisicoes_pendentes} requisições pendentes de atendimento. Por favor, verifique.",
#             rota_acesso="/almox/solicitacoes-page/",
#             tipo="aviso",
#             chave="alerta_requisicoes_pendentes_almox",
#             frequencia=dt_timedelta(days=2),  # ajuste aqui
#         )


# def verificar_e_notificar_transferencias_pendentes():
#     """
#     Verifica o número total de transferências pendentes e envia uma notificação
#     se o limite de 30 for atingido.
#     Usa um controle de frequência para não enviar múltiplos alertas seguidos.
#     """
#     transferencias_pendentes = SolicitacaoTransferencia.objects.filter(
#         entregue_por__isnull=True, data_entrega__isnull=True
#     ).count()

#     if transferencias_pendentes >= 30:
#         print(f"⚠️ Limite atingido! {transferencias_pendentes} transferências pendentes. Tentando notificar...")

#         notificacao_almoxarifado(
#             titulo="Alerta: Alto Volume de Transferências",
#             mensagem=f"Existem {transferencias_pendentes} requisições pendentes de atendimento. Por favor, verifique.",
#             rota_acesso="/almox/solicitacoes-page/",
#             tipo="alerta",
#             chave="alerta_transferencias_pendentes_almox",
#             frequencia=dt_timedelta(days=2),  # ajuste aqui
#         )

# def contar_erros_requisicoes() -> int:
#     # rpa diferente de 'OK' (case-insensitive), desconsiderando nulos e vazios
#     return (
#         SolicitacaoRequisicao.objects
#         .filter(rpa__isnull=False)
#         .exclude(rpa__iexact="OK")
#         .exclude(rpa__exact="")
#         .count()
#     )

# def contar_erros_transferencias() -> int:
#     return (
#         SolicitacaoTransferencia.objects
#         .filter(rpa__isnull=False)
#         .exclude(rpa__iexact="OK")
#         .exclude(rpa__exact="")
#         .count()
#     )

# def notificar_erro_requisicoes_se_acima_limite():
#     qtd = contar_erros_requisicoes()
#     if qtd > LIMITE_ERROS:
#         notificacao_almoxarifado(
#             titulo="Alerta: Requisições com erro",
#             mensagem=f"Existem {qtd} requisições com erro. Verifique o painel do Almox.",
#             rota_acesso="/almox/erros/",
#             tipo="aviso",
#             chave="alerta_erros_requisicoes_almox",
#             frequencia=FREQUENCIA_ALERTA_ERROS,
#         )

# def notificar_erro_transferencias_se_acima_limite():
#     qtd = contar_erros_transferencias()
#     if qtd > LIMITE_ERROS:
#         notificacao_almoxarifado(
#             titulo="Alerta: Transferências com erro",
#             mensagem=f"Existem {qtd} transferências com erro. Verifique o painel do Almox.",
#             rota_acesso="/almox/erros/",
#             tipo="aviso",
#             chave="alerta_erros_transferencias_almox",
#             frequencia=FREQUENCIA_ALERTA_ERROS,
#         )

def format_private_key(key):
    """
    Substitui as ocorrências literais de '\\n' na chave privada 
    por quebras de linha reais.
    """
    if key:
        return key.replace('\\n', '\n')
    return key

# --- Construção do Objeto de Credenciais ---
def get_google_credentials():
    """
    Carrega e formata o objeto de credenciais a partir das variáveis de ambiente.
    """
    credentials_google = {
        "type": os.environ.get('type'),
        "project_id": os.environ.get('project_id'),
        "private_key": format_private_key(os.environ.get('private_key')),
        "client_email": os.environ.get('client_email'),
        "client_id": os.environ.get('client_id'),
        "auth_uri": os.environ.get('auth_uri'),
        "token_uri": os.environ.get('token_uri'),
        "auth_provider_x509_cert_url": os.environ.get('auth_provider_x509_cert_url'),
        "client_x509_cert_url": os.environ.get('client_x509_cert_url'),
        "universe_domain": os.environ.get('universe_domain')
    }
    
    if not credentials_google.get('private_key') or not credentials_google.get('client_email'):
        print("Erro: Credenciais essenciais (PRIVATE_KEY ou CLIENT_EMAIL) não encontradas nas variáveis de ambiente.")
        return None
        
    return credentials_google

# ----------------------------------------

def carregar_planilha_base_geral():
    """
    Carrega os dados da planilha base geral, lidando com colunas duplicadas
    e utilizando cache diário.
    """
    global CACHE_DF, CACHE_EXPIRATION_TIME

    # 1. VERIFICAÇÃO DO CACHE (Permanece inalterada)
    if CACHE_DF is not None and datetime.now() < CACHE_EXPIRATION_TIME:
        print("Cache diário válido. Utilizando dados em memória.")
        return CACHE_DF
    
    print("Cache expirado ou vazio. Recarregando planilha do Google Sheets...")

    chave_planilha = os.environ.get('BASE_GERAL_KEY')
    credentials = get_google_credentials()
    if not chave_planilha or credentials is None:
        return None

    try:
        gc = gspread.service_account_from_dict(credentials)
        sh = gc.open_by_key(chave_planilha)
        worksheet = sh.worksheet("BASE ATUALIZADA") 
        
        data = worksheet.get_all_values()

        if not data:
            print("Planilha vazia.")
            return None

        headers = data[0]
        records = data[1:]

        colunas_interesse = ['CODIGO', 'DESCRIÇÃO', 'CONJUNTO', '2 PROCESSO']
        
        indices_para_manter = []
        headers_filtrados = []
        
        for i, header in enumerate(headers):
            if header in colunas_interesse and header not in headers_filtrados:
                indices_para_manter.append(i)
                headers_filtrados.append(header)

        dados_filtrados = [
            [row[i] for i in indices_para_manter] 
            for row in records
        ]
        
        df = pd.DataFrame(dados_filtrados, columns=headers_filtrados)

        df['CONJUNTO_CODIGO_PURO'] = df['CONJUNTO'].str.split(' - ').str[0].str.strip()

        df['DESCRIÇÃO'] = df['CONJUNTO'].str.split(' - ').str[1].str.strip()
        
        df['CONJUNTO_CODIGO_PURO'].fillna(df['CONJUNTO'], inplace=True)

        df_filtrado = df.astype(str)

        CACHE_DF = df_filtrado
        CACHE_EXPIRATION_TIME = datetime.now() + CACHE_DURATION
        print(f"Planilha carregada ({len(df_filtrado)} registros). Novo cache expira em: {CACHE_EXPIRATION_TIME.strftime('%Y-%m-%d %H:%M:%S')}")

        return CACHE_DF

    except Exception as e:
        print(f"Erro ao carregar a planilha. Erro: {e}")
        return CACHE_DF if CACHE_DF is not None else None
