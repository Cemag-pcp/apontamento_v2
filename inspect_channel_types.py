import redis

# --- Configuração ---
# Use a mesma URL de conexão do seu settings.py
REDIS_URL = "redis://default:AWbmAbD4G2CfZPb3RxwuWQ4RfY7JOmxS@redis-19210.c262.us-east-1-3.ec2.redns.redis-cloud.com:19210"
# --------------------

# Conecte-se ao Redis
try:
    r = redis.from_url(REDIS_URL, db=0, decode_responses=True)
    r.ping()
    print("Conectado com sucesso ao Redis!")
except Exception as e:
    print(f"Erro ao conectar ao Redis: {e}")
    exit()

print("\nProcurando por QUALQUER chave com prefixo 'asgi:*'...")
keys_found = []
for key in r.scan_iter("asgi:*"):
    keys_found.append(key)

if not keys_found:
    print("\n--- Nenhuma chave com o prefixo 'asgi:' foi encontrada. ---")
    print("Isso sugere que sua aplicação Django não está enviando mensagens para o Channel Layer.")
    print("\nPossíveis causas:")
    print("1. Nenhum consumidor do Django Channels está em execução.")
    print("2. Nenhuma ação (ex: conexão de um WebSocket, chamada a `channel_layer.send()`) foi realizada para gerar uma mensagem.")
    print("3. O prefixo do Channel Layer foi alterado (o padrão é 'asgi:').")
else:
    print(f"\n--- Encontradas {len(keys_found)} chaves: ---")
    for key in keys_found:
        try:
            key_type = r.type(key)
            print(f"- Chave: '{key}', Tipo: {key_type}")
            # Se for uma lista, mostra quantos itens tem
            if key_type == 'list':
                list_length = r.llen(key)
                print(f"  (Esta lista contém {list_length} mensagens)")
        except Exception as e:
            print(f"Erro ao inspecionar a chave {key}: {e}")
