import redis, json, uuid
from datetime import datetime

# ip 226

def chamar_impressora(cliente, data_carga, nome_pacote, obs):

    data_formatada = datetime.strptime(data_carga, "%Y-%m-%d").strftime("%d/%m/%Y")

    # Monta o ZPL final
    zpl = f"""
^XA
^CI28
^PW799
^LL420
^LT0
^LH0,0

^FX ===================== CABEÇALHO =====================
^FO50,30
^A0N,40,40
^FB700,1,0,C,0
^FD{cliente}^FS

^FO50,80
^A0N,30,30
^FB700,1,0,C,0
^FDData da Carga: {data_formatada}^FS

^FX Linha separadora
^FO40,120
^GB720,3,3^FS

^FX ===================== PACOTE =====================
^FO50,160
^AE,40,30
^FB700,1,0,C,0
^FD{nome_pacote}^FS

^FX ===================== OBSERVAÇÕES =====================
^FO50,220
^A0N,28,28
^FDObservações:^FS

^FO50,260
^A0N,24,24
^FB700,4,10,L,0
^FD{obs}^FS

^XZ

    """

    r = redis.from_url("redis://default:AWbmAbD4G2CfZPb3RxwuWQ4RfY7JOmxS@redis-19210.c262.us-east-1-3.ec2.redns.redis-cloud.com:19210")

    job_id = str(uuid.uuid4())
    payload = {"job_id": job_id, "zpl": zpl}
    r.rpush("print-zebra", json.dumps(payload))
    print(job_id)
