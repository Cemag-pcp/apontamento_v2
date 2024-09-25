from django import forms
from apontamento.models import Planejamento

# class PlanejamentoForm(forms.ModelForm):
#     class Meta:
#         model = Planejamento
#         fields = ['peca', 'quantidade_planejada', 'data_planejada', 'maquina', 'tamanho_vara']
#         widgets = {
#             'peca': forms.Select(attrs={'class': 'form-control'}),
#             'quantidade_planejada': forms.NumberInput(attrs={'class': 'form-control'}),
#             'data_planejada': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
#             'maquina': forms.Select(attrs={'class': 'form-control'}),
#             'tamanho_vara': forms.TextInput(attrs={'class': 'form-control'}),
#         }
