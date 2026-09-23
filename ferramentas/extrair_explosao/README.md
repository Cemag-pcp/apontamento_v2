# Extrair Explosão

Ferramenta para extrair a tabela `cadastro_carretasexplodidas`
("base Explosão") do banco de produção em CSV.

## Uso (quem recebe a ferramenta)

Precisa dos 2 arquivos juntos na mesma pasta: `extrair_explosao.bat` e
`extrair_explosao.py`. Requer **Python instalado** no computador (com a
opção "Add python.exe to PATH" marcada na instalação).

1. Coloque os 2 arquivos numa pasta qualquer.
2. Dê dois cliques em `extrair_explosao.bat`.
   - Se o Python não estiver instalado, ele avisa e pede pra instalar.
   - Se faltar a dependência `psycopg2-binary`, ele instala sozinho na
     primeira vez.
3. Na primeira vez, ele cria um `config.ini` do lado e pede pra você
   preencher `host`, `usuario` e `senha` do banco.
4. Preencha o `config.ini` (editor de texto simples, ex: Notepad) e rode o
   `.bat` de novo.
5. O CSV é salvo na pasta **Downloads** do usuário (não na pasta do
   `.bat`), com nome `explosao_carretas_AAAAMMDD_HHMMSS.csv` (separador
   `;`, UTF-8 com BOM — abre certo no Excel).

O `config.ini` fica só na pasta de quem for usar — nunca é versionado nem
enviado a lugar nenhum.

## Alternativa: gerar um .exe (não precisa de Python instalado)

Se for distribuir pra máquinas sem Python, ainda é possível empacotar
como executável standalone:

```
pip install pyinstaller psycopg2-binary
python -m PyInstaller --onefile --console --name ExtrairExplosao --distpath dist --workpath build --specpath . extrair_explosao.py
```

O executável final fica em `dist/ExtrairExplosao.exe` — pode substituir o
`.bat`/`.py` por ele, o comportamento (config.ini, salvar em Downloads) é
o mesmo.

## Segurança

Essa ferramenta usa a credencial do banco que for colocada no
`config.ini` por quem for usar. Quem tiver esse arquivo tem acesso de
leitura/escrita ao banco (mesma credencial da aplicação) — evite
reaproveitar o mesmo `config.ini` fora do necessário, e não versione um
`config.ini` com senha real (use `config.ini.exemplo` como modelo).
