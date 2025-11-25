import json
import time
import paho.mqtt.client as mqtt

HOST = "labworks3d.com"
PORT = 1883

CLIENT_ID = "cemagprod_sender"


def enviar_sinal_iniciar(centro: str, peca: str, ordem_producao: str):
    """
    Envia sinal de INICIAR para o centro informado.

    centro: ex: 'centro5'
    peca: código da peça, ex: '232500'
    ordem_producao: ex: 'OP100230'
    """

    client = mqtt.Client(client_id=CLIENT_ID, protocol=mqtt.MQTTv5)

    def on_connect(client, userdata, flags, reason_code, properties=None):
        print("Conectado ao broker para envio, código:", reason_code)

    client.on_connect = on_connect

    client.connect(HOST, PORT, keepalive=60)

    topic = f"labworks/vc/cemag/{centro}/write"

    payload = {
        "data": {
            "0": peca,          # Peça
            "1": True,          # True = Iniciar (Acionado)
            "2": ordem_producao # Ordem de Produção
        },
        "timestamp": int(time.time())
    }

    payload_str = json.dumps(payload)

    print("=" * 60)
    print("Publicando sinal de START")
    print(f"Tópico:  {topic}")
    print(f"Payload: {payload_str}")
    print("=" * 60)

    client.loop_start()
    result = client.publish(topic, payload_str, qos=0, retain=False)
    result.wait_for_publish()
    client.loop_stop()

    client.disconnect()
    print("Sinal de INICIAR enviado com sucesso.")


def main():
    print("=== Envio de comando START para Labworks/CEMAG ===")

    # Aqui você pode fixar valores ou pedir no input:
    centro = input("Centro de produção (ex: centro5): ").strip() or "centro5"
    peca = input("Código da peça (ex: 232500): ").strip() or "232500"
    ordem = input("Ordem de produção (ex: OP100230): ").strip() or "OP100230"

    enviar_sinal_iniciar(centro, peca, ordem)


if __name__ == "__main__":
    main()
