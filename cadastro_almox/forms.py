from django import forms

from .models import RegraSlaAlmox


class RegraSlaAlmoxForm(forms.ModelForm):
    class Meta:
        model = RegraSlaAlmox
        fields = ['prioridade', 'minutos_limite', 'cor', 'ativo']
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
            'cor': forms.TextInput(
                attrs={
                    'class': 'form-control form-control-color',
                    'type': 'color',
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
            'cor': 'Cor da flag',
            'ativo': 'Regra ativa',
        }

    def clean_prioridade(self):
        prioridade = self.cleaned_data['prioridade'].strip()
        if not prioridade:
            raise forms.ValidationError('Informe a prioridade da regra.')
        return prioridade

    def clean_cor(self):
        cor = (self.cleaned_data['cor'] or '').strip()
        if len(cor) != 7 or not cor.startswith('#'):
            raise forms.ValidationError('Informe uma cor hexadecimal valida.')

        try:
            int(cor[1:], 16)
        except ValueError:
            raise forms.ValidationError('Informe uma cor hexadecimal valida.')

        return cor.lower()
