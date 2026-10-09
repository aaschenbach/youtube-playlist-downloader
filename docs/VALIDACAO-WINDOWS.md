# Validação antes de publicar

## Automatizada

Executar `uv run --extra build python -m unittest discover -s tests -v` e `uv run --extra build python scripts/build_windows.py`. O build executa o pacote com `--self-test`, sem acessar o YouTube.

Testes cobrem sessão compartilhada, cookies inválidos, acesso negado, bloqueio persistente, cancelamento de processo real, retomada, legendas, ZIP inseguro e atualização corrompida. Nenhum cookie real entra no CI.

## Windows limpo e interface

- Windows 10/11 x64, conta comum, sem Python, Git, Node ou FFmpeg e sem administrador.
- Extrair todo o ZIP em pasta com espaços e acentos. Abrir por duplo clique e a partir de outra pasta de trabalho.
- Conferir preparação inicial, reabertura e falha de internet preservando a versão existente.
- Testar teclado, foco, escala 100% e 150%, pasta sem escrita e link inválido.
- Confirmar que cancelamento não deixa yt-dlp ou FFmpeg rodando.

## Comparação com a linha de comando

Para investigar diferenças entre a janela e o yt-dlp, compare as duas execuções com a mesma URL, sessão e versões das ferramentas. Exemplo no PowerShell:

```powershell
& "C:\Ferramentas\yt-dlp.exe" $Url --ignore-config --js-runtimes "node:C:\Ferramentas\node.exe" --cookies "C:\Sessao\cookies.txt"
```

Substitua os caminhos pelos arquivos do ambiente de teste. Não registre o conteúdo dos cookies nos resultados.

Selecionar o arquivo e a URL de teste na janela e confirmar consulta e download. Se divergir, comparar os argumentos, as versões e as configurações externas. O aplicativo usa `--ignore-config` e caminhos absolutos; opções externas necessárias devem ser incorporadas explicitamente.

O manifesto usa Node LTS compatível. Validar a combinação antes de publicar. Consulta aceita não garante download aceito; recusa não comprova cookies inválidos.

## Downloads e atualização

- Vídeo MP4, playlist com item indisponível, MP3, legendas presentes e ausentes.
- Live encerrada aceita, ativa/agendada recusada com explicação.
- Cancelar, retomar e recuperar legendas preservando arquivos e histórico.
- Cookies válidos ainda recusados: preservar escolhas e oferecer uma ação possível.
- Release de teste com manifesto e ZIP: atualizar e reabrir pelo ZIP anterior.
- ZIP corrompido, ferramenta inválida e falta de internet: preservar versão anterior.
- Conferir ausência de credenciais nos detalhes.

## Publicação

Atualizar versão em `pyproject.toml` e `src/ytdl/settings.py`; regenerar o build e conferir nomes do ZIP nos documentos. Publicar ZIP, `manifest.json` e `SHA256SUMS.txt` na tag `v<versão>` do repositório oficial.

`manifest.json` é o contrato: schema 1, ferramentas com versão/URL/SHA-256 e aplicativo com versão/URL/SHA-256. Renovar as ferramentas com `scripts/resolve_tools.py` antes de publicar correções.

Registrar os cenários manuais executados e os pendentes. Testes unitários não provam funcionamento em Windows limpo ou acesso real ao YouTube.
