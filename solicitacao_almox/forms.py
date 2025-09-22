from django import forms
from .models import *

class SolicitacaoRequisicaoForm(forms.ModelForm):
    class Meta:
        model = SolicitacaoRequisicao
        fields = ['funcionario', 'cc', 'item', 'classe_requisicao', 'quantidade', 'obs']

class SolicitacaoTransferenciaForm(forms.ModelForm):
    class Meta:
        model = SolicitacaoTransferencia
        fields = ['funcionario', 'deposito_destino', 'item', 'quantidade', 'obs']

class SolicitacaoCadastroItemRequisicaoForm(forms.ModelForm):
    class Meta:
        model=SolicitacaoCadastroItem
        fields=['codigo','descricao','quantidade']#, 'funcionario','cc']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'quantidade': forms.NumberInput(attrs={'class': 'form-control'}),
            # 'funcionario': forms.Select(attrs={'class': 'form-control'}),
            # 'cc': forms.Select(attrs={'class': 'form-control'}),
        }
        
class SolicitacaoCadastroItemTransferenciaForm(forms.ModelForm):
    class Meta:
        model=SolicitacaoCadastroItem
        fields=['codigo','descricao','quantidade','deposito_destino', 'funcionario']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'quantidade': forms.NumberInput(attrs={'class': 'form-control'}),
            'deposito_destino': forms.Select(attrs={'class': 'form-control'}),
            'funcionario': forms.Select(attrs={'class': 'form-control'}),
        }

class SolicitacaoCadastroMatriculaForm(forms.ModelForm):
    class Meta:
        model=SolicitacaoNovaMatricula
        fields=['matricula','nome','cc']
        widgets = {
            'matricula': forms.TextInput(attrs={'class': 'form-control'}),
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'cc': forms.Select(attrs={'class': 'form-control'}),
        }
        
