import os
import json
import redis
import win32print

REDIS_URL = os.getenv("REDIS_URL", "redis://default:AWbmAbD4G2CfZPb3RxwuWQ4RfY7JOmxS@redis-19210.c262.us-east-1-3.ec2.redns.redis-cloud.com:19210")
QUEUE_NAME = os.getenv("REDIS_QUEUE", "print-zebra")  # nome da fila

def send_label(printer: str):
    r = redis.from_url(REDIS_URL)
    print(f"Conectado ao Redis. Aguardando jobs em '{QUEUE_NAME}' -> {printer}")

    while True:
        _, raw = r.blpop(QUEUE_NAME)
        print("[WORKER] Recebi da fila:", raw)

        try:
            payload = json.loads(raw)
            zpl = payload.get("zpl", "")
            resposta_queue = payload.get("resposta_queue")
            job_id = payload.get("job_id")
        except Exception:
            zpl = raw.decode("utf-8", errors="replace")
            resposta_queue = None
            job_id = None

        if not zpl:
            print("[AVISO] Job sem ZPL. Ignorando.")
            continue

        try:
            hPrinter = win32print.OpenPrinter(printer)
            try:
                win32print.StartDocPrinter(hPrinter, 1, ("Etiqueta", None, "RAW"))
                win32print.StartPagePrinter(hPrinter)
                win32print.WritePrinter(hPrinter, zpl.encode("utf-8"))
                win32print.EndPagePrinter(hPrinter)
                win32print.EndDocPrinter(hPrinter)
                print("[WORKER] Impressão OK.")
                status = "OK"
            finally:
                win32print.ClosePrinter(hPrinter)
        except Exception as e:
            print("[ERRO] Falha ao imprimir:", e)
            status = f"ERRO: {e}"

        # --- envia resposta se houver fila de retorno ---
        if resposta_queue:
            r.rpush(resposta_queue, json.dumps({"job_id": job_id, "status": status}))


if __name__ == "__main__":
  
 
    # ajuste o nome exato da sua impressora (veja em Dispositivos e Impressoras)
    send_label("ZDesigner ZD220-203dpi ZPL")
