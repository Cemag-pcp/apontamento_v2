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
from .models import Pecas, Setor

def upload_csv(request):
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

