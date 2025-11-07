import json
import time
import paho.mqtt.client as mqtt

HOST = "labworks3d.com"   # teste
PORT = 1883               # sem TLS

CLIENT_ID = "cemag-mes"  # só um identificador da conexão
MQTT_CLIENT_ID_LABWORKS = "cemag"  # client_id definido por vocês

# Callback quando conectar
def on_connect(client, userdata, flags, reason_code, properties=None):
    print("Conectado ao broker, código:", reason_code)
    # Assina todos os tópicos de data de todos os centros da cemag
    # “labworks/vc/cemag/centro1/status”
    # “labworks/vc/cemag/centro3/data”
    # “labworks/vc/cemag/centro2/status”
    # “labworks/vc/cemag/centro2/read”
    # “labworks/vc/cemag/centro4/response”
    # “labworks/vc/cemag/centro4/write”

    topic = f"labworks/vc/{MQTT_CLIENT_ID_LABWORKS}/centro2/data"

    client.subscribe(topic)
    print("Assinado tópico:", topic)

# Callback quando chega mensagem
def on_message(client, userdata, msg):
    print(f"\nTópico recebido: {msg.topic}")
    payload_str = msg.payload.decode("utf-8")
    print("Payload bruto:", payload_str)

    try:
        data = json.loads(payload_str)
    except json.JSONDecodeError:
        print("Erro ao decodificar JSON")
        return

    # Pela documentação, o JSON tem sempre 'data' e 'timestamp'
    # Exemplo de data para contagem: {"data": {"3": 37}, "timestamp": 1742922122}
    dados = data.get("data", {})
    timestamp = data.get("timestamp")

    # Porta 3 = contagem atual do centro de produção
    contagem = dados.get("3")  # pode vir como int

    print("Timestamp:", timestamp)
    print("Contagem lida (porta 3):", contagem)

    # Se quiser extrair o centro (device_id) do tópico:
    # labworks/vc/cemag/centro2/data
    partes = msg.topic.split("/")
    device_id = partes[3] if len(partes) > 3 else None
    print("Centro de produção:", device_id)


def main():
    client = mqtt.Client(client_id=CLIENT_ID, protocol=mqtt.MQTTv5)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(HOST, PORT, keepalive=60)
    client.loop_start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Encerrando...")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
