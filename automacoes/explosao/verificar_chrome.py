import requests
import zipfile
import subprocess
import os

def verificar_chrome_driver():
    # URL que você deseja acessar
    url = "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"

    # Faz uma solicitação GET à URL
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()

        # Versão que você está procurando
        target_version = get_chrome_version()

        def version_key(version):
            # Converte a versão em uma lista de inteiros para comparação
            return list(map(int, version.split('.')))

        # Filtra as versões disponíveis
        versions = [v['version'] for v in data['versions']]

        # Encontra a versão mais próxima
        closest_version = None
        min_diff = float('inf')

        for version in versions:
            # Calcula a diferença em cada nível de versão
            current_diff = sum(
                abs(a - b) for a, b in zip(version_key(version), version_key(target_version)))

            if current_diff < min_diff:
                min_diff = current_diff
                closest_version = version

        # Filtra as versões disponíveis
        versions_info = data['versions']

        # Armazena versões que correspondem à versão desejada
        matching_versions = []

        for version_info in versions_info:
            version = version_info['version']

            # Verifica se a versão corresponde à versão desejada
            if version == closest_version:
                matching_versions.append(version_info)

        # Exibe todos os registros encontrados
        if matching_versions:
            print("Registros encontrados:")
            for match in matching_versions:
                download_chrome_driver = match['downloads']['chromedriver']
        else:
            print("Nenhum registro encontrado.")

        def get_url_by_platform(data, platform):
            for item in data:
                if item['platform'] == platform:
                    return item['url']
            return None

        # Exemplo de uso:
        url = get_url_by_platform(download_chrome_driver, 'win32')
        filename = 'chromedriver-win32.zip'
        download_file(url, filename)

        extract_to = 'chromedriver_extracted'
        unzip_file(filename, extract_to)

        chromedriver_path = find_chromedriver(extract_to)
        if chromedriver_path:
            print(f"chromedriver.exe encontrado em: {chromedriver_path}")
        else:
            print("chromedriver.exe não encontrado.")

        return chromedriver_path

    else:
        print(f"Falha ao acessar a URL: {response.status_code}")

def download_file(url, filename):
    response = requests.get(url)
    if response.status_code == 200:
        with open(filename, 'wb') as file:
            file.write(response.content)
        print(f"Download concluído: {filename}")
    else:
        print(f"Falha no download: {response.status_code}")

def unzip_file(zip_path, extract_to='.'):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
        print(f"Arquivos extraídos para: {extract_to}")

def find_chromedriver(extract_to='.'):
    for root, dirs, files in os.walk(extract_to):
        if 'chromedriver.exe' in files:
            return os.path.join(root, 'chromedriver.exe')
    return None

def get_chrome_version():
    try:
        # Executa o comando para obter a versão do Chrome
        version = subprocess.check_output(
            ['reg', 'query', r'HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon',
                '/v', 'version'],
            stderr=subprocess.STDOUT
        )
        # Processa a saída para extrair a versão
        version = version.decode().strip().split()[-1]
        return version
    except subprocess.CalledProcessError:
        return "Chrome não está instalado."

