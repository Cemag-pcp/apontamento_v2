from django import forms
from .models import *
from cadastro_almox.models import ItensSolicitacao, ItensTransferencia, RegraSlaAlmox

class SolicitacaoRequisicaoForm(forms.ModelForm):
    status = forms.ModelChoiceField(
        queryset=RegraSlaAlmox.objects.filter(ativo=True).order_by('minutos_limite', 'prioridade'),
        required=True,
    )

    class Meta:
        model = SolicitacaoRequisicao
        fields = ['funcionario', 'cc', 'item', 'classe_requisicao', 'quantidade', 'status', 'obs']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['funcionario'].queryset = Funcionario.objects.filter(ativo=True).order_by('nome', 'matricula')
        self.fields['item'].queryset = ItensTransferencia.objects.filter(ativo=True).order_by('codigo')
        self.fields['item'].queryset = ItensSolicitacao.objects.filter(ativo=True).order_by('codigo')

class SolicitacaoTransferenciaForm(forms.ModelForm):
    status = forms.ModelChoiceField(
        queryset=RegraSlaAlmox.objects.filter(ativo=True).order_by('minutos_limite', 'prioridade'),
        required=True,
    )

    class Meta:
        model = SolicitacaoTransferencia
        fields = ['funcionario', 'deposito_destino', 'item', 'quantidade', 'status', 'obs']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['funcionario'].queryset = Funcionario.objects.filter(ativo=True).order_by('nome', 'matricula')

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
        
