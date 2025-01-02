from django.shortcuts import render

# Create your views here.
# import pandas as pd

# df=pd.read_csv("pecas_serra_usinagem.csv", sep=',')
# pecas_serra=df[df['SERRA']==True][['RECURSO']].reset_index(drop=True)
# pecas_serra[['codigo', 'descricao']] = pecas_serra['RECURSO'].str.split(' - ', n=1, expand=True)
# pecas_serra['setor'] = 'serra'
# pecas_serra['materia_prima'] = None
# pecas_serra['comprimento'] = None
# pecas_serra.drop(columns=['RECURSO'], inplace=True)

# pecas_usinagem=df[df['SERRA']==False].drop(columns=['SERRA']).reset_index(drop=True)

# views.py
import csv
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import UploadCSVForm
from .models import Pecas, Setor, Maquina

def importar_peca(request):
    if request.method == 'POST':
        form = UploadCSVForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # Abrir o arquivo CSV
                csv_file = request.FILES['file']
                # Verificar se o arquivo é CSV
                if not csv_file.name.endswith('.csv'):
                    messages.error(request, 'Por favor, faça o upload de um arquivo CSV.')
                    return redirect('upload_csv')

                # Ler o conteúdo do CSV
                decoded_file = csv_file.read().decode('utf-8').splitlines()
                reader = csv.DictReader(decoded_file)

                for row in reader:
                    # Exemplo de como ler os dados do CSV e salvar no banco de dados
                    codigo = row.get('codigo')
                    descricao = row.get('descricao')
                    materia_prima = row.get('materia_prima', None)
                    setores = row.get('setor', None)

                    # Criar ou atualizar o objeto Pecas
                    peca, created = Pecas.objects.update_or_create(
                        codigo=codigo,
                        defaults={
                            'descricao': descricao,
                            'materia_prima': materia_prima,
                        }
                    )

                    # Associar os setores
                    if setores:
                        setores_list = [s.strip() for s in setores.split(';')]  # Supondo que os setores estejam separados por ";"
                        for setor_nome in setores_list:
                            setor, _ = Setor.objects.get_or_create(nome=setor_nome)
                            peca.setor.add(setor)

                messages.success(request, 'CSV carregado e processado com sucesso!')
                return redirect('upload_csv')

            except Exception as e:
                messages.error(request, f'Houve um erro no processamento: {str(e)}')
                return redirect('upload_csv')

    else:
        form = UploadCSVForm()

    return render(request, 'cadastro_massa/peca_massa.html', {'form': form})

# def importar_peca_processo_csv(request):
#     if request.method == 'POST':
#         form = UploadCSVForm(request.POST, request.FILES)
        
#         if form.is_valid():
#             csv_file = request.FILES['file']
#             if not csv_file.name.endswith('.csv'):
#                 messages.error(request, 'Por favor, faça o upload de um arquivo CSV.')
#                 return redirect('importar_peca_processo_csv')

#             decoded_file = csv_file.read().decode('utf-8').splitlines()
#             reader = csv.DictReader(decoded_file)

#             for row in reader:
#                 codigo_peca = row['codigo']
#                 nome_processo = row['nome_processo']
#                 nome_maquina = row['nome_maquina']
#                 ordem = row['ordem']

#                 # Buscar a peça, processo e máquina com base nos dados do CSV
#                 try:
#                     peca = Pecas.objects.get(codigo=codigo_peca)
#                     processo = Setor.objects.get(nome=nome_processo)
#                     maquina = Maquina.objects.get(nome=nome_maquina)

#                     # Criar ou atualizar o registro em PecaProcesso
#                     PecaProcesso.objects.update_or_create(
#                         peca=peca,
#                         processo=processo,
#                         maquina=maquina,
#                         ordem=ordem,
#                         defaults={
#                             'peca': peca,
#                             'processo': processo,
#                             'maquina': maquina,
#                             'ordem': ordem,
#                         }
#                     )
#                 except Pecas.DoesNotExist:
#                     messages.error(request, f"Peça com código {codigo_peca} não encontrada.")
#                 except Setor.DoesNotExist:
#                     messages.error(request, f"Setor com nome {nome_processo} não encontrado.")
#                 except Maquina.DoesNotExist:
#                     messages.error(request, f"Máquina com nome {nome_maquina} não encontrada.")
            
#             messages.success(request, 'CSV importado com sucesso!')
#             return redirect('importar_peca_processo_csv')
#     else:
#         form = UploadCSVForm()

#     return render(request, 'cadastro_massa/peca_processo_massa.html', {'form': form})

def atualizar_materia_prima(request):
    if request.method == 'POST':
        form = UploadCSVForm(request.POST, request.FILES)
        
        if form.is_valid():
            # Pegar o arquivo CSV enviado
            csv_file = request.FILES['file']
            
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'Por favor, envie um arquivo CSV.')
                return redirect('atualizar_materia_prima')

            try:
                # Decodificar o arquivo CSV
                decoded_file = csv_file.read().decode('utf-8').splitlines()
                reader = csv.DictReader(decoded_file)

                # Processar cada linha do CSV
                for row in reader:
                    codigo = row['codigo']
                    nova_materia_prima = row['materia_prima']
                    
                    try:
                        # Tentar buscar a peça pelo código e atualizar a matéria-prima
                        peca = Pecas.objects.get(codigo=codigo)
                        peca.materia_prima = nova_materia_prima
                        peca.save()
                    except Pecas.DoesNotExist:
                        messages.warning(request, f'Peça com código {codigo} não encontrada.')

                messages.success(request, 'Matéria-prima atualizada com sucesso!')
                return redirect('atualizar_materia_prima')
            
            except Exception as e:
                messages.error(request, f'Houve um erro ao processar o arquivo: {e}')
                return redirect('atualizar_materia_prima')
    
    else:
        form = UploadCSVForm()

    return render(request, 'cadastro_massa/atualizar_mp_massa.html', {'form': form})

# def importar_ordem(request):
#     if request.method == 'POST':
#         form = UploadCSVForm(request.POST, request.FILES)
#         if form.is_valid():
#             try:
#                 # Abrir o arquivo CSV
#                 csv_file = request.FILES['file']

#                 if not csv_file.name.endswith('.csv'):
#                     messages.error(request, 'Por favor, faça o upload de um arquivo CSV.')
#                     return redirect('importar_ordem')

#                 decoded_file = csv_file.read().decode('utf-8').splitlines()
#                 reader = csv.reader(decoded_file, delimiter=',')

#                 for row in reader:
#                     numero_ordem = int(row[0])
#                     codigo_peca = row[2]
#                     mp_usada_codigo, mp_usada_descricao = row[4].split(' - ', 1)

#                     # Obter ou criar a ordem
#                     ordem, created = OrdemPadrao.objects.get_or_create(
#                         numero_ordem=numero_ordem,
#                         defaults={
#                             'mp_usada_codigo': mp_usada_codigo,
#                             'mp_usada_descricao': mp_usada_descricao,
#                         }
#                     )

#                     # Verificar se a peça existe
#                     try:
#                         peca = Pecas.objects.get(codigo=codigo_peca)
#                     except Pecas.DoesNotExist:
#                         messages.error(request, f'A peça com o código {codigo_peca} não foi encontrada.')
#                         continue

#                     # Verificar se o processo da peça existe
#                     try:
#                         peca_processo = PecaProcesso.objects.get(peca=peca, ordem=1)
#                     except PecaProcesso.DoesNotExist:
#                         messages.error(request, f'Nenhum processo encontrado para a peça {codigo_peca}.')
#                         continue

#                     # Associar a peça à ordem, se ainda não estiver associada
#                     if not ordem.pecas.filter(id=peca_processo.id).exists():
#                         ordem.pecas.add(peca_processo)

#                 messages.success(request, 'CSV carregado e processado com sucesso!')
#                 return redirect('importar_ordem')

#             except Exception as e:
#                 messages.error(request, f'Houve um erro no processamento: {str(e)}')
#                 return redirect('importar_ordem')

#     else:
#         form = UploadCSVForm()

#     return render(request, 'cadastro_massa/ordem_massa.html', {'form': form})
