from django import forms

from .models import RegraSlaAlmox


class RegraSlaAlmoxForm(forms.ModelForm):
    class Meta:
        model = RegraSlaAlmox
        fields = ['prioridade', 'minutos_limite', 'ativo']
        widgets = {
            'prioridade': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Ex.: Alto, Medio, Baixo',
                }
            ),
            'minutos_limite': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'min': '1',
                    'placeholder': 'Ex.: 40',
                }
            ),
            'ativo': forms.CheckboxInput(
                attrs={
                    'class': 'form-check-input',
                }
            ),
        }

        labels = {
            'prioridade': 'Prioridade',
            'minutos_limite': 'Tempo limite (minutos)',
            'ativo': 'Regra ativa',
        }

    def clean_prioridade(self):
        prioridade = self.cleaned_data['prioridade'].strip()
        if not prioridade:
            raise forms.ValidationError('Informe a prioridade da regra.')
        return prioridade
