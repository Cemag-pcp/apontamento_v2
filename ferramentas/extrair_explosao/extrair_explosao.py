"""
Extrai a tabela "cadastro_carretasexplodidas" (base "Explosao") do banco
de producao em CSV.

Le as credenciais de um arquivo config.ini na mesma pasta do executavel.
Se o arquivo nao existir, cria um modelo e pede pro usuario preencher.
"""

import configparser
import csv
import os
import sys
from datetime import datetime

import psycopg2

NOME_CONFIG = "config.ini"
TABELA = "cadastro_carretasexplodidas"
SCHEMA_PADRAO = "apontamento_v2"


def pasta_base():
    """Pasta onde o .exe (ou o script) esta rodando - onde procurar/criar o config.ini."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def criar_config_modelo(caminho):
    conteudo = (
        "[banco]\n"
        "host = \n"
        "porta = 5432\n"
        "database = postgres\n"
        "usuario = \n"
        "senha = \n"
        "schema = apontamento_v2\n"
    )
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(conteudo)


def carregar_config(caminho):
    config = configparser.ConfigParser()
    config.read(caminho, encoding="utf-8")
    if "banco" not in config:
        raise ValueError("Secao [banco] nao encontrada no config.ini.")

    banco = config["banco"]
    obrigatorios = ["host", "usuario", "senha"]
    faltando = [campo for campo in obrigatorios if not banco.get(campo, "").strip()]
    if faltando:
        raise ValueError(f"Preencha os campos no config.ini: {', '.join(faltando)}")

    return {
        "host": banco.get("host").strip(),
        "port": banco.get("porta", "5432").strip(),
        "dbname": banco.get("database", "postgres").strip(),
        "user": banco.get("usuario").strip(),
        "password": banco.get("senha").strip(),
        "schema": banco.get("schema", SCHEMA_PADRAO).strip() or SCHEMA_PADRAO,
    }


def extrair_para_csv(conexao_info, pasta_destino):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo = f"explosao_carretas_{timestamp}.csv"
    caminho_csv = os.path.join(pasta_destino, nome_arquivo)

    conn = psycopg2.connect(
        host=conexao_info["host"],
        port=conexao_info["port"],
        dbname=conexao_info["dbname"],
        user=conexao_info["user"],
        password=conexao_info["password"],
        connect_timeout=10,
    )
    try:
        with conn.cursor() as cur, open(caminho_csv, "wb") as f:
            f.write(b"\xef\xbb\xbf")  # BOM UTF-8 pro Excel abrir acentos certo
            query = (
                f'COPY (SELECT * FROM {conexao_info["schema"]}.{TABELA}) '
                "TO STDOUT WITH (FORMAT CSV, HEADER, DELIMITER ';', ENCODING 'UTF8')"
            )
            cur.copy_expert(query, f)
    finally:
        conn.close()

    return caminho_csv


def main():
    pasta = pasta_base()
    caminho_config = os.path.join(pasta, NOME_CONFIG)

    print("=" * 60)
    print("Extracao da base Explosao (cadastro_carretasexplodidas)")
    print("=" * 60)

    if not os.path.exists(caminho_config):
        criar_config_modelo(caminho_config)
        print(f"\nArquivo de configuracao criado em:\n  {caminho_config}")
        print("\nAbra esse arquivo num editor de texto, preencha host, usuario")
        print("e senha do banco, e rode este programa de novo.")
        input("\nPressione ENTER para sair...")
        return

    try:
        conexao_info = carregar_config(caminho_config)
    except ValueError as exc:
        print(f"\nErro no config.ini: {exc}")
        input("\nPressione ENTER para sair...")
        return

    print(f"\nConectando em {conexao_info['host']}...")

    try:
        caminho_csv = extrair_para_csv(conexao_info, pasta)
    except psycopg2.OperationalError as exc:
        print(f"\nNao foi possivel conectar ao banco.\nDetalhe: {exc}")
        input("\nPressione ENTER para sair...")
        return
    except Exception as exc:
        print(f"\nErro ao extrair os dados.\nDetalhe: {exc}")
        input("\nPressione ENTER para sair...")
        return

    print("\nExtracao concluida com sucesso!")
    print(f"Arquivo salvo em:\n  {caminho_csv}")
    input("\nPressione ENTER para sair...")


if __name__ == "__main__":
    main()
