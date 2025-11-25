import json
import time
import paho.mqtt.client as mqtt

HOST = "labworks3d.com"
PORT = 1883

CLIENT_ID = "cemagprod_receiver"

def on_connect(client, userdata, flags, reason_code, properties=None):
    print("Conectado ao broker, código:", reason_code)

    # Assina todos os centros: centro1, centro2, centro3, etc.
    topic = "labworks/vc/cemag/+/data"
    client.subscribe(topic)
    print(f"Assinado no tópico: {topic}")


def on_message(client, userdata, msg):
    try:
        payload_str = msg.payload.decode("utf-8")
        data = json.loads(payload_str)
    except Exception as e:
        print(f"[ERRO] Não consegui decodificar a mensagem: {e}")
        print("Tópico:", msg.topic)
        print("Payload bruto:", msg.payload)
        print("-" * 80)
        return

    # Extrai o centro do tópico: labworks/vc/cemag/centroX/data
    topic_parts = msg.topic.split("/")
    centro = topic_parts[3] if len(topic_parts) >= 4 else "desconhecido"

    print("=" * 80)
    print(f"Tópico: {msg.topic}")
    print(f"Centro de Produção: {centro}")
    print("Payload bruto:", payload_str)

    # Tenta interpretar campos comuns, se existir
    data_dict = data.get("data") if isinstance(data, dict) else None

    if isinstance(data_dict, dict):
        peca = data_dict.get("0")
        estado = data_dict.get("1")  # pode ser bool ou string
        op = data_dict.get("2")

        print("--- Interpretação ---")
        if peca is not None:
            print(f"Peça: {peca}")
        if op is not None:
            print(f"Valor [2]: {op}")
        if estado is not None:
            print(f"Valor [1] (estado/bruto): {estado}")

    # Timestamp (se vier)
    ts = data.get("timestamp") if isinstance(data, dict) else None
    if ts is not None:
        try:
            dt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(ts)))
            print(f"Timestamp: {ts} ({dt})")
        except Exception:
            print(f"Timestamp: {ts}")

    print("=" * 80)


def main():
    client = mqtt.Client(client_id=CLIENT_ID, protocol=mqtt.MQTTv5)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(HOST, PORT, keepalive=60)

    print("Iniciando loop de recebimento (CTRL+C para parar)...")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("Encerrando...")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
