import csv
from cadastro.models import Pecas, Setor

# def importar_pecas_csv(caminho_arquivo_csv):
#     """
#     Importa os dados de peças de um arquivo CSV para o modelo Pecas, separando código e descrição,
#     e associa o setor `prod_esp` para cada peça.

#     Args:
#         caminho_arquivo_csv (str): Caminho do arquivo CSV a ser importado.
#     """
#     with open(caminho_arquivo_csv, mode='r', encoding='utf-8') as arquivo:
#         leitor_csv = csv.DictReader(arquivo)  # Supondo que a coluna seja `codigo`
#         pecas_criadas = 0
#         pecas_existentes = 0

#         # Busca ou cria o setor `prod_esp`
#         setor_prod_esp, _ = Setor.objects.get_or_create(nome='prod_esp')

#         for linha in leitor_csv:
#             # Divide a string em código e descrição
#             if 'codigo' in linha:
#                 codigo_completo = linha['codigo']
#                 partes = codigo_completo.split(' - ', 1)  # Divide no primeiro " - "
                
#                 if len(partes) == 2:
#                     codigo = partes[0].strip()  # Código (antes do "-")
#                     descricao = partes[1].strip()  # Descrição (depois do "-")
#                 else:
#                     print(f"Linha inválida: {linha}")
#                     continue

#                 # Verifica se a peça já existe pelo código
#                 peca, criada = Pecas.objects.get_or_create(
#                     codigo=codigo,
#                     defaults={'descricao': descricao}
#                 )

#                 # Adiciona o setor `prod_esp` à peça
#                 if setor_prod_esp not in peca.setor.all():
#                     peca.setor.add(setor_prod_esp)

#                 if criada:
#                     pecas_criadas += 1
#                 else:
#                     pecas_existentes += 1

#         print(f"Importação concluída: {pecas_criadas} peças criadas, {pecas_existentes} já existentes.")

# def atualizar_setor_prod_esp_csv(caminho_arquivo_csv):
#     """
#     Adiciona o setor 'prod_esp' às peças existentes no banco de dados, com base nos códigos listados no CSV.

#     Args:
#         caminho_arquivo_csv (str): Caminho do arquivo CSV contendo os códigos das peças.
#     """
#     # Busca ou cria o setor `prod_esp`
#     setor_prod_esp, _ = Setor.objects.get_or_create(nome='prod_esp')

#     # Lê o CSV e extrai os códigos
#     with open(caminho_arquivo_csv, mode='r', encoding='utf-8') as arquivo:
#         leitor_csv = csv.DictReader(arquivo)  # Supondo que a coluna seja `codigo`
#         codigos_csv = []

#         for linha in leitor_csv:
#             if 'codigo' in linha:
#                 codigo_completo = linha['codigo']
#                 partes = codigo_completo.split(' - ', 1)  # Divide no primeiro " - "
#                 codigo = partes[0].strip()  # Extrai o código antes do " - "
#                 codigos_csv.append(codigo)

#     # Filtra as peças no banco de dados que correspondem aos códigos do CSV
#     pecas = Pecas.objects.filter(codigo__in=codigos_csv)
#     pecas_atualizadas = 0

#     for peca in pecas:
#         # Adiciona o setor apenas se ele ainda não estiver associado
#         if setor_prod_esp not in peca.setor.all():
#             peca.setor.add(setor_prod_esp)
#             pecas_atualizadas += 1

#     print(f"Atualização concluída: {pecas_atualizadas} peças no CSV atualizadas com o setor 'prod_esp'.")
