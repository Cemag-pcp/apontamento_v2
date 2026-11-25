"""Vários operadores num apontamento (início na solda, finalização na montagem).

A tela manda uma lista ("operadores_inicio" / "operadores_final"); telas e
apps antigos ainda mandam um só ("operador_inicio" / "operador_final"). O
primeiro da lista continua indo para o campo de operador único do modelo,
para relatórios e painéis que leem só ele.
"""
from cadastro.models import Operador


class OperadorInvalido(ValueError):
    pass


def operadores_do_corpo(body, campo_lista, campo_unico):
    """Lista de Operador na ordem escolhida, sem repetir. Vazia se nada veio.
    Levanta OperadorInvalido se algum id não existe."""
    valores = body.get(campo_lista)
    if not isinstance(valores, list):
        valores = [body.get(campo_unico)]

    ids = []
    for valor in valores:
        texto = str(valor if valor is not None else '').strip()
        if not texto:
            continue
        if not texto.isdigit():
            raise OperadorInvalido(f'Operador inválido: {texto}.')
        if int(texto) not in ids:
            ids.append(int(texto))

    por_id = Operador.objects.in_bulk(ids)
    faltando = [i for i in ids if i not in por_id]
    if faltando:
        raise OperadorInvalido('Operador não encontrado.')
    return [por_id[i] for i in ids]


def nomes_operadores(operadores, primeiro_nome=False):
    """"123 - João, 456 - Maria" para exibir."""
    partes = []
    for operador in operadores:
        nome = operador.nome.split(' ')[0] if primeiro_nome else operador.nome
        partes.append(f'{operador.matricula} - {nome}')
    return ', '.join(partes)
