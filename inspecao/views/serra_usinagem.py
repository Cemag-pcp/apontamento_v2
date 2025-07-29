from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import (
    Q, Prefetch, OuterRef, Subquery, Max, Sum, F, FloatField, 
    IntegerField,ExpressionWrapper, Func, Value, CharField, Count, Case, When
)
from django.db import transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.db.models.functions import Concat, Cast, TruncMonth, ExtractYear, ExtractMonth
from django.db import connection

from cadastro.models import PecasEstanqueidade
from apontamento_montagem.models import ConjuntosInspecionados
from apontamento_pintura.models import Retrabalho
from ..models import (
    Inspecao,
    DadosExecucaoInspecao,
    Reinspecao,
    Causas,
    CausasNaoConformidade,
    ArquivoCausa,
    InspecaoEstanqueidade,
    DadosExecucaoInspecaoEstanqueidade,
    ReinspecaoEstanqueidade,
    DetalhesPressaoTanque,
    InfoAdicionaisExecTubosCilindros,
    CausasNaoConformidadeEstanqueidade,
    ArquivoCausaEstanqueidade,
)
from core.models import Profile, Maquina
from apontamento_estamparia.models import (
    InfoAdicionaisInspecaoEstamparia,
    MedidasInspecaoEstamparia,
    DadosNaoConformidade,
    ImagemNaoConformidade,
)

from datetime import datetime, timedelta
from collections import defaultdict
import json


def inspecao_serra_usinagem(request):

    return