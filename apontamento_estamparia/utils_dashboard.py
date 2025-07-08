from django.http import JsonResponse
from django.db import transaction, connection

from datetime import datetime, timedelta
from apontamento_serra.utils import formatar_timedelta

def hora_operacao_maquina(maquina_param, data_inicio, data_fim):

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    sql = """
        WITH parametros AS (
        SELECT
            (%(data_inicio)s::date) AT TIME ZONE 'America/Fortaleza' AS start_ts,
            ((%(data_fim)s::date) + INTERVAL '1 day') AT TIME ZONE 'America/Fortaleza' AS end_ts_exclusive
        ),
        registros AS (
            SELECT
                cm.nome AS maquina,
                co.data_inicio,
                COALESCE(co.data_fim, NOW()) AS data_fim
            FROM apontamento_v2.core_ordemprocesso co
            JOIN apontamento_v2.core_ordem co2 ON co2.id = co.ordem_id
            JOIN apontamento_v2.cadastro_maquina cm ON cm.id = co2.maquina_id
            CROSS JOIN parametros p
            WHERE co2.grupo_maquina = 'estamparia'
                AND co.status = 'iniciada'
                AND COALESCE(co.data_fim, NOW()) >= p.start_ts
                AND co.data_inicio < p.end_ts_exclusive
                AND cm.nome = %(maquina_param)s
        ),
        dias AS (
            SELECT
                r.maquina,
                r.data_inicio,
                r.data_fim,
                generate_series(
                    date_trunc('day', r.data_inicio AT TIME ZONE 'America/Fortaleza') - INTERVAL '1 day',
                    date_trunc('day', r.data_fim AT TIME ZONE 'America/Fortaleza'),
                    INTERVAL '1 day'
                ) AT TIME ZONE 'America/Fortaleza' AS dia
            FROM registros AS r
        ),
        por_turno AS (
            SELECT
                d.maquina,
                (d.dia AT TIME ZONE 'America/Fortaleza')::date AS dia_label,
                -- manhã: 06:00–12:00
                GREATEST(d.data_inicio, d.dia + TIME '06:00') AS inicio_manha,
                LEAST(d.data_fim,    d.dia + TIME '12:00') AS fim_manha,
                -- tarde: 13:00–17:00
                GREATEST(d.data_inicio, d.dia + TIME '13:00') AS inicio_tarde,
                LEAST(d.data_fim, d.dia + TIME '17:00') AS fim_tarde,
                -- noite: 19:00 até 06:00 do dia seguinte
                GREATEST(d.data_inicio, d.dia + TIME '19:00') AS inicio_noite,
                LEAST(d.data_fim, (date_trunc('day', d.dia) + INTERVAL '1 day') + TIME '05:00') AS fim_noite
            FROM dias AS d
        ),
        duracoes AS (
            SELECT
                p.maquina,
                p.dia_label,
                CASE WHEN p.fim_manha > p.inicio_manha THEN (p.fim_manha - p.inicio_manha) ELSE INTERVAL '0' END AS duracao_manha,
                CASE WHEN p.fim_tarde > p.inicio_tarde THEN (p.fim_tarde - p.inicio_tarde) ELSE INTERVAL '0' END AS duracao_tarde,
                CASE WHEN p.fim_noite > p.inicio_noite THEN (p.fim_noite - p.inicio_noite) ELSE INTERVAL '0' END AS duracao_noite
            FROM por_turno AS p
        )
        SELECT
            d.maquina,
            d.dia_label AS dia,
            LEAST(SUM(d.duracao_manha), INTERVAL '6 hours') AS total_manha,
            LEAST(SUM(d.duracao_tarde), INTERVAL '4 hours') AS total_tarde,
            LEAST(SUM(d.duracao_noite), INTERVAL '10 hours') AS total_noite,
            (
                LEAST(SUM(d.duracao_manha), INTERVAL '6 hours') +
                LEAST(SUM(d.duracao_tarde), INTERVAL '4 hours') +
                LEAST(SUM(d.duracao_noite), INTERVAL '10 hours')
            ) AS total_dia
        FROM duracoes AS d
        WHERE (d.duracao_manha > INTERVAL '0'
            OR d.duracao_tarde > INTERVAL '0'
            OR d.duracao_noite > INTERVAL '0')
        GROUP BY d.maquina, d.dia_label
        ORDER BY d.dia_label, d.maquina;
        """

    # Executar consulta
    with connection.cursor() as cursor:
        cursor.execute(sql, {
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'maquina_param': maquina_param,
        })
        rows = cursor.fetchall()

    # Organizar dados em dict
    registros = {}
    maquinas_set = set()

    for maquina, dia, manha, tarde, noite, total_dia in rows:
        dia_str = dia.strftime('%Y-%m-%d')
        maquinas_set.add(maquina)
        registros[(maquina, dia_str)] = {
            'manha': formatar_timedelta(manha),
            'tarde': formatar_timedelta(tarde),
            'noite': formatar_timedelta(noite),
            'total': formatar_timedelta(total_dia),
        }

    # Garantir ordem dos dias
    dias_ordenados = []
    atual = data_inicio
    while atual < data_fim:
        dias_ordenados.append(atual.strftime('%Y-%m-%d'))
        atual += timedelta(days=1)

    # Construir matriz completa com zeros onde não houver registro
    resultado = []
    for maquina in sorted(maquinas_set):
        for dia in dias_ordenados:
            key = (maquina, dia)
            dados = registros.get(key, {
                'manha': '00:00:00',
                'tarde': '00:00:00',
                'noite': '00:00:00',
                'total': '00:00:00',
            })
            resultado.append({
                'maquina': maquina,
                'dia': dia,
                'total_manha': dados['manha'],
                'total_tarde': dados['tarde'],
                'total_noite': dados['noite'],
                'total_dia': dados['total'],
            })

    return resultado

def hora_parada_maquina(maquina_param, data_inicio, data_fim):

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    sql = """
        WITH parametros AS (
            SELECT
                (%(data_inicio)s::date) AT TIME ZONE 'America/Fortaleza' AS start_ts,
                ((%(data_fim)s::date) + INTERVAL '1 day') AT TIME ZONE 'America/Fortaleza' AS end_ts_exclusive
            ),
            registros AS (
                SELECT
                    cm2.nome AS maquina,
                    cm.data_inicio,
                    COALESCE(cm.data_fim, NOW()) AS data_fim
                FROM apontamento_v2.core_maquinaparada cm
                LEFT JOIN apontamento_v2.cadastro_maquina cm2 ON cm2.id = cm.maquina_id
                CROSS JOIN parametros p
                WHERE cm2.nome = %(maquina_param)s and cm.data_inicio >= p.start_ts AND COALESCE(cm.data_fim, NOW()) < p.end_ts_exclusive
            ),
            dias AS (
                SELECT
                    r.maquina,
                    r.data_inicio,
                    r.data_fim,
                    generate_series(
                        date_trunc('day', r.data_inicio AT TIME ZONE 'America/Fortaleza') - INTERVAL '1 day',
                        date_trunc('day', r.data_fim AT TIME ZONE 'America/Fortaleza'),
                        INTERVAL '1 day'
                    ) AT TIME ZONE 'America/Fortaleza' AS dia
                FROM registros AS r
            ),
            por_turno AS (
                SELECT
                    d.maquina,
                    (d.dia AT TIME ZONE 'America/Fortaleza')::date AS dia_label,
                    -- manhã: 06:00–12:00
                    GREATEST(d.data_inicio, d.dia + TIME '06:00') AS inicio_manha,
                    LEAST(d.data_fim,       d.dia + TIME '12:00') AS fim_manha,
                    -- tarde: 13:00–17:00
                    GREATEST(d.data_inicio, d.dia + TIME '13:00') AS inicio_tarde,
                    LEAST(d.data_fim,       d.dia + TIME '17:00') AS fim_tarde,
                    -- noite: 19:00 até 06:00 do dia seguinte
                    GREATEST(d.data_inicio, d.dia + TIME '19:00') AS inicio_noite,
                    LEAST(d.data_fim, (date_trunc('day', d.dia) + INTERVAL '1 day 3 hours') + TIME '05:00') AS fim_noite
                FROM dias AS d
            ),
            duracoes AS (
                SELECT
                    p.maquina,
                    p.dia_label,
                    CASE WHEN p.fim_manha > p.inicio_manha THEN (p.fim_manha - p.inicio_manha) ELSE INTERVAL '0' END AS duracao_manha,
                    CASE WHEN p.fim_tarde > p.inicio_tarde THEN (p.fim_tarde - p.inicio_tarde) ELSE INTERVAL '0' END AS duracao_tarde,
                    CASE WHEN p.fim_noite > p.inicio_noite THEN (p.fim_noite - p.inicio_noite) ELSE INTERVAL '0' END AS duracao_noite
                FROM por_turno AS p
            )
            SELECT
                d.maquina,
                d.dia_label AS dia,
                SUM(d.duracao_manha) AS total_manha,
                SUM(d.duracao_tarde) AS total_tarde,
                SUM(d.duracao_noite) AS total_noite,
                SUM(d.duracao_manha + d.duracao_tarde + d.duracao_noite) AS total_parada
            FROM duracoes AS d
            WHERE (d.duracao_manha > INTERVAL '0'
                OR d.duracao_tarde > INTERVAL '0'
                OR d.duracao_noite > INTERVAL '0')
            GROUP BY d.maquina, d.dia_label
            ORDER BY d.dia_label, d.maquina;
        """

    # Executar consulta
    with connection.cursor() as cursor:
        cursor.execute(sql, {
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'maquina_param': maquina_param,
        })
        rows = cursor.fetchall()

    # Organizar dados em dict
    registros = {}
    maquinas_set = set()

    for maquina, dia, manha, tarde, noite, total_dia in rows:
        dia_str = dia.strftime('%Y-%m-%d')
        maquinas_set.add(maquina)
        registros[(maquina, dia_str)] = {
            'manha': formatar_timedelta(manha),
            'tarde': formatar_timedelta(tarde),
            'noite': formatar_timedelta(noite),
            'total': formatar_timedelta(total_dia),
        }

    # Garantir ordem dos dias
    dias_ordenados = []
    atual = data_inicio
    while atual < data_fim:
        dias_ordenados.append(atual.strftime('%Y-%m-%d'))
        atual += timedelta(days=1)

    # Construir matriz completa com zeros onde não houver registro
    resultado = []
    for maquina in sorted(maquinas_set):
        for dia in dias_ordenados:
            key = (maquina, dia)
            dados = registros.get(key, {
                'manha': '00:00:00',
                'tarde': '00:00:00',
                'noite': '00:00:00',
                'total': '00:00:00',
            })
            resultado.append({
                'maquina': maquina,
                'dia': dia,
                'total_manha': dados['manha'],
                'total_tarde': dados['tarde'],
                'total_noite': dados['noite'],
                'total_dia': dados['total'],
            })

    return resultado

def ordem_por_maquina(data_inicio, data_fim):

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    sql = """
        SELECT 
            co.ultima_atualizacao::date as data_finalizacao,
            cm.nome AS maquina,
            COUNT(co.id) AS total_ordens_finalizadas
        FROM apontamento_v2.core_ordem co
        LEFT JOIN apontamento_v2.cadastro_maquina cm ON cm.id = co.maquina_id
        WHERE 
            co.grupo_maquina = 'estamparia'
            AND co.status_atual = 'finalizada'
            -- filtros opcionais de data
            AND co.ultima_atualizacao::date BETWEEN %(data_inicio)s AND %(data_fim)s
            AND cm.tipo = 'maquina'
        GROUP BY cm.nome, co.ultima_atualizacao::date
    ORDER BY co.ultima_atualizacao::date, cm.nome;
    """

    # Executar consulta
    with connection.cursor() as cursor:
        cursor.execute(sql, {
            'data_inicio': data_inicio,
            'data_fim': data_fim,
        })
        rows = cursor.fetchall()

    # Agrupar por data
    registros = {}

    for data_finalizacao, maquina, total in rows:
        dia_str = data_finalizacao.strftime('%Y-%m-%d')
        if dia_str not in registros:
            registros[dia_str] = []
        registros[dia_str].append({
            'maquina': maquina,
            'total_ordens_finalizadas': total
        })

    return registros

def producao_por_maquina(data_inicio, data_fim):

    try:
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return JsonResponse({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

    sql = """
        SELECT 
            asp.data::date,
            cm.nome AS maquina,
            sum(asp.qtd_boa) AS total_pecas_produzida
        FROM apontamento_v2.apontamento_estamparia_pecasordem asp 
        LEFT JOIN apontamento_v2.core_ordem co on co.id = asp.ordem_id 
        LEFT JOIN apontamento_v2.cadastro_maquina cm ON cm.id = co.maquina_id
        WHERE 
            co.grupo_maquina = 'estamparia'
            AND co.status_atual = 'finalizada'
            -- filtros opcionais de data
            AND asp.data >= %(data_inicio)s
            AND asp.data < ((%(data_fim)s)::date + INTERVAL '1 day')
            AND cm.tipo = 'maquina'
        GROUP BY cm.nome, asp.data::date
        ORDER BY data, maquina;
        """

    # Executar consulta
    with connection.cursor() as cursor:
        cursor.execute(sql, {
            'data_inicio': data_inicio,
            'data_fim': data_fim,
        })
        rows = cursor.fetchall()

    # Agrupar por data
    registros = {}

    for data_finalizacao, maquina, total in rows:
        dia_str = data_finalizacao.strftime('%Y-%m-%d')
        if dia_str not in registros:
            registros[dia_str] = []
        registros[dia_str].append({
            'maquina': maquina,
            'total_ordens_finalizadas': total
        })

    return registros
