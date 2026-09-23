# Extrair Explosão

Ferramenta standalone (.exe) para extrair a tabela `cadastro_carretasexplodidas`
("base Explosão") do banco de produção em CSV.

## Uso (quem recebe o .exe)

1. Coloque `ExtrairExplosao.exe` em uma pasta qualquer.
2. Dê dois cliques nele.
3. Na primeira vez, ele cria um `config.ini` do lado e pede pra você preencher
   `host`, `usuario` e `senha` do banco.
4. Preencha o `config.ini` (editor de texto simples, ex: Notepad) e rode o
   `.exe` de novo.
5. O CSV é salvo na pasta **Downloads** do usuário (não na pasta do `.exe`),
   com nome `explosao_carretas_AAAAMMDD_HHMMSS.csv` (separador `;`, UTF-8
   com BOM — abre certo no Excel).

O `config.ini` fica só na pasta de quem for usar — nunca é embutido no
`.exe` nem enviado a lugar nenhum.

## Build (gerar o .exe de novo, se o script mudar)

```
pip install pyinstaller psycopg2-binary
python -m PyInstaller --onefile --console --name ExtrairExplosao --distpath dist --workpath build --specpath . extrair_explosao.py
```

O executável final fica em `dist/ExtrairExplosao.exe`.

## Segurança

Esse .exe usa a credencial do banco que for colocada no `config.ini` por
quem for usar. Quem tiver esse arquivo tem acesso de leitura/escrita ao
banco (mesma credencial da aplicação) — evite reaproveitar o mesmo
`config.ini` fora do necessário, e não versione um `config.ini` com senha
real (use `config.ini.exemplo` como modelo).
