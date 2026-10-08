# ytdl — YouTube Downloader Interativo

Baixe vídeos e playlists do YouTube com uma interface CLI amigável e interativa.  
Suporta vídeo (MP4), áudio (MP3), legendas automáticas e retoma downloads já iniciados.

Este projeto usa a biblioteca [yt-dlp](https://github.com/yt-dlp/yt-dlp) para extrair metadados, selecionar formatos e baixar vídeos, áudio e legendas. O `ytdl` fornece o menu interativo e configura o fluxo de download. Créditos aos mantenedores e colaboradores do yt-dlp, cujo código é disponibilizado sob a [Unlicense](https://github.com/yt-dlp/yt-dlp/blob/master/LICENSE). As demais dependências possuem suas próprias licenças.

---

## Índice

1. [Requisitos](#requisitos)
2. [Instalação](#instalação)
3. [Como usar](#como-usar)
4. [Guia do menu interativo](#guia-do-menu-interativo)
5. [Erros comuns e como resolver](#erros-comuns-e-como-resolver)
6. [Perguntas frequentes](#perguntas-frequentes)

---

## Requisitos

| Requisito | Versão mínima | Para que serve |
|-----------|--------------|----------------|
| Python    | 3.11         | Rodar o programa |
| FFmpeg    | qualquer     | Mesclar vídeo + áudio em MP4 |
| Deno ou Node.js | Deno 2.3+ / Node 22+ | Resolver desafios JavaScript do YouTube |
| uv *(opcional)* | qualquer | Gerenciar dependências de forma mais rápida |

### Instalar o Python

- **Windows**: baixe em <https://python.org/downloads> e marque **"Add Python to PATH"** na instalação.
- **macOS**: `brew install python`
- **Linux (Debian/Ubuntu)**: `sudo apt install python3 python3-pip`

### Instalar o FFmpeg

- **Windows**: baixe o build em <https://ffmpeg.org/download.html>, extraia e adicione a pasta `bin` ao PATH.
  - Ou via winget: `winget install ffmpeg`
  - Ou via choco: `choco install ffmpeg`
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg`

Verifique se está instalado: `ffmpeg -version`

### Instalar um runtime JavaScript

Instale [Deno](https://docs.deno.com/runtime/getting_started/installation/) (recomendado pelo yt-dlp) ou [Node.js](https://nodejs.org/en/download/), disponível no PATH. No Windows, uma alternativa é:

```powershell
winget install --id OpenJS.NodeJS.LTS -e
```

Reabra o terminal e verifique com `node --version` (22 ou superior) ou `deno --version` (2.3 ou superior). O programa habilita automaticamente o Node encontrado no PATH e mantém o Deno habilitado.

As dependências do projeto incluem `yt-dlp-ejs` para resolver os desafios e `curl-cffi` para requisições com características de navegador. Isso não garante que o YouTube aceite todas as requisições. Consulte o [guia oficial de EJS](https://github.com/yt-dlp/yt-dlp/wiki/EJS).

### Instalar o uv *(recomendado)*

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Instalação

### Com uv *(recomendado)*

No Windows, abra o PowerShell e execute:

```powershell
git clone https://github.com/aaschenbach/youtube-playlist-downloader.git
cd youtube-playlist-downloader
uv sync
uv run ytdl
```

Se o projeto já estiver clonado, entre na pasta existente e execute apenas `uv sync` e `uv run ytdl`. **Com `uv run ytdl`, não é necessário ativar a `.venv`**: o uv executa o programa dentro dela.

### Com uv pip e ativação da .venv (PowerShell)

Esta é uma alternativa completa ao fluxo acima. Na pasta do projeto, crie a `.venv` apenas se ela ainda não existir:

```powershell
uv venv
uv pip install -e .
.\.venv\Scripts\Activate.ps1
ytdl
```

`uv pip` instala no ambiente do projeto mesmo sem ativação. Para executar `ytdl` diretamente pelo nome, ative a `.venv` antes. Repita a ativação sempre que abrir um novo terminal. Para sair do ambiente, execute `deactivate`.

Para este projeto, prefira `uv sync` e `uv run ytdl`. `uv pip install` instala diretamente no ambiente e não atualiza o lock; um `uv sync` ou `uv run` posterior pode desfazer instalações avulsas.

### Com pip (Python com pip instalado)

No PowerShell, com um Python que tenha pip instalado:

```powershell
git clone https://github.com/aaschenbach/youtube-playlist-downloader.git
cd youtube-playlist-downloader
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
ytdl
```

No macOS/Linux, a ativação é `source .venv/bin/activate`.

---

## Como usar

Execute os comandos na pasta do projeto. Escolha uma das opções:

### Rodar com uv, sem ativação manual

```powershell
uv run ytdl
```

### Rodar diretamente no PowerShell, ativando a .venv

```powershell
.\.venv\Scripts\Activate.ps1
ytdl
```

Essa ativação é o passo necessário antes de chamar apenas `ytdl`. No Prompt de Comando (cmd), use `.venv\Scripts\activate.bat`; no macOS/Linux, use `source .venv/bin/activate`.

Se preferir executar sem ativar e sem sincronizar dependências, no PowerShell use:

```powershell
.\.venv\Scripts\ytdl.exe
```

O programa abre um menu interativo e guia você passo a passo. Não é necessário nenhum argumento na linha de comando.

---

## Guia do menu interativo

### Passo 1 — URL

Cole a URL de um **vídeo único** ou de uma **playlist**. Exemplos válidos:

```
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://www.youtube.com/playlist?list=PLxxxxxxxx
https://youtu.be/dQw4w9WgXcQ
```

> Pressione **Enter** para confirmar ou **Ctrl+C** para cancelar a qualquer momento.

### Passo 2 — Pasta de destino

O padrão é `~/Downloads/YouTube`. Você pode digitar qualquer caminho absoluto ou relativo, por exemplo:

```
C:\Users\SeuNome\Musicas
/home/seunome/videos
```

A pasta é criada automaticamente se não existir.

### Passo 3 — Modo de download

| Opção | O que faz |
|-------|-----------|
| 🎬 Vídeo + áudio (MP4) | Baixa a melhor qualidade de vídeo e áudio e mescla em MP4 |
| 🎵 Somente áudio (MP3) | Extrai apenas o áudio em MP3 (192 kbps) |
| 🎬 Melhor qualidade (auto) | Igual ao primeiro; alias para quem não quer pensar |

### Passo 4 — Legendas

Se você responder **sim**, o programa tentará baixar legendas em português (PT / PT-BR) e inglês (EN) no formato `.srt`, quando disponíveis. Legendas automáticas geradas pelo YouTube também são incluídas.

### Passo 5 — Comportamento em erros

- **Sim (padrão)**: se um vídeo da playlist estiver indisponível, o programa pula e continua.
- **Não**: o programa para ao encontrar qualquer erro.

### Passo 6 — Confirmação

Um resumo é exibido antes do download iniciar. Revise e confirme ou cancele.

### Após o download

Você pode:
- **Baixar outra URL** — reinicia o menu
- **Abrir a pasta de destino** — abre o gerenciador de arquivos diretamente
- **Sair**

---

## Erros comuns e como resolver

### Atualizar a versão do projeto

Na pasta do repositório:

```powershell
git pull --ff-only
uv sync
```

Se o Git apontar conflito ou alterações locais, revise essas alterações antes de continuar. Para instalações via `uv pip`, use `uv pip install -e .` após atualizar o código; com pip tradicional, use `python -m pip install -e .`.

### Atualizar o yt-dlp e as dependências

O YouTube muda com frequência. Antes de investigar uma falha de extração, atualize na pasta do projeto:

```powershell
# Com uv (uv sync sozinho mantém as versões do lock existente)
uv sync --upgrade-package yt-dlp --upgrade-package yt-dlp-ejs

# Alternativa: instalação direta no ambiente do uv, sem atualizar o lock
uv pip install --upgrade "yt-dlp[default,curl-cffi]"

# Com pip tradicional / ambiente ativado
python -m pip install -U "yt-dlp[default,curl-cffi]"
```

### `No supported JavaScript runtime could be found`

**Causa**: nenhum runtime compatível está disponível para o yt-dlp. O download pode continuar, mas alguns formatos podem faltar.
**Solução**: instale Deno ou Node conforme [Requisitos](#requisitos), reabra o terminal e atualize as dependências. Instalar apenas o pacote Python `yt-dlp-ejs` não instala o runtime.

### `HTTP Error 429: Too Many Requests`

**Causa**: o YouTube está limitando requisições. Pode afetar metadados ou legendas mesmo quando vídeo e áudio são baixados normalmente.
**Solução**: aguarde antes de tentar novamente e evite downloads simultâneos. Com legendas habilitadas, o programa espera 1 segundo entre requisições de extração e 5 segundos antes de cada legenda; essas pausas reduzem a frequência, mas não garantem eliminar o bloqueio. Veja a [FAQ oficial sobre HTTP 429](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#http-error-429-too-many-requests-or-402-payment-required).

`Unable to download video subtitles` significa que aquela legenda falhou. A linha `Writing video subtitles to` anuncia uma tentativa e não comprova que o arquivo foi baixado.

### `no impersonate target is available`

**Causa**: falta suporte para requisições com características de navegador.
**Solução**: rode `uv sync` ou `python -m pip install -e .` para instalar as dependências atuais, que incluem `curl-cffi`. Essa dependência não elimina necessariamente o HTTP 429. Veja a [documentação oficial sobre impersonation](https://github.com/yt-dlp/yt-dlp#impersonation).

### Recuperar somente legendas que falharam

Vídeos concluídos entram em `.download-archive.txt` mesmo quando alguma legenda falha. Rodar novamente o menu na mesma pasta pode pular esses vídeos e suas legendas. Preserve o histórico e use o yt-dlp diretamente para tentar só as legendas, depois de aguardar o bloqueio passar:

```powershell
uv run python -m yt_dlp --ignore-config --skip-download --write-subs --write-auto-subs --sub-langs "pt,pt-BR,en" --sub-format srt --sleep-requests 1 --sleep-subtitles 5 --js-runtimes node --ignore-errors --no-overwrites -P "C:\Users\SeuNome\Downloads\SuaPlaylist" -o "%(playlist_index)03d - %(title)s [%(id)s].%(ext)s" "https://www.youtube.com/playlist?list=PLxxxxxxxx"
```

Substitua a pasta e a URL pelos mesmos valores do download original. O comando não usa o histórico nem baixa vídeo/áudio e preserva legendas existentes. Com Deno, troque `--js-runtimes node` por `--js-runtimes deno`. Com pip, use `python -m yt_dlp` no lugar de `uv run python -m yt_dlp`.

Se instalou ou atualizou via `uv pip`, substitua `uv run python` por `.\.venv\Scripts\python.exe` para usar exatamente as versões instaladas, sem sincronizar o lock. A mesma substituição vale para o comando de download forçado abaixo.

---

### `ERROR: ffmpeg not found`

**Causa**: FFmpeg não está instalado ou não está no PATH.  
**Solução**: instale conforme descrito em [Requisitos](#requisitos) e reinicie o terminal.

---

### `ERROR: Sign in to confirm you're not a bot`

**Causa**: o YouTube detectou muitas requisições ou está pedindo login.  
**Solução**:
1. Exporte os cookies do seu navegador com a extensão [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc).
2. Salve o arquivo como `cookies.txt` na pasta do projeto.
3. Adicione a opção no código editando `src/ytdl/downloader.py`, linha `opts`, adicionando:
   ```python
   "cookiefile": "cookies.txt",
   ```

---

### `ERROR: Video unavailable`

**Causa**: o YouTube informou que o vídeo está indisponível; a mensagem sozinha não confirma o motivo. Pode ter sido removido, ser privado ou estar bloqueado no seu país.
**Solução**: habilite **"Continuar em erros"** no menu para que a playlist continue mesmo assim.

`1 unavailable video is hidden` indica um item indisponível na playlist. `Finished downloading playlist` significa que o processamento terminou, mas não comprova que todos os vídeos e legendas foram baixados. O programa sinaliza erros ou avisos no encerramento.

---

### `ModuleNotFoundError: No module named 'ytdl'`

**Causa**: o pacote não foi instalado corretamente.  
**Solução**:
```powershell
# Com uv
uv sync

# Com uv pip
uv pip install -e .

# Com pip tradicional, após ativar a .venv
python -m pip install -e .
```

---

### `command not found: ytdl` / `ytdl não é reconhecido`

**Causa**: o script de entrada não está no PATH.  
**Solução**: execute `uv run ytdl` na pasta do projeto. Se quiser chamar apenas `ytdl`, execute antes `.\.venv\Scripts\Activate.ps1` no PowerShell. Se o erro continuar, reinstale o projeto conforme a seção [Instalação](#instalação).

---

### `PermissionError` ao salvar arquivos

**Causa**: a pasta de destino não tem permissão de escrita.  
**Solução**: escolha uma pasta diferente (ex.: `~/Downloads/YouTube`) ou corrija as permissões da pasta.

---

### Download muito lento

**Causa**: rede, ou o YouTube limitando a velocidade.  
**Solução**: o programa já usa 4 fragmentos em paralelo. Se ainda estiver lento, aguarde — é uma limitação do servidor.

---

### Arquivo já existe / download não reinicia

**Causa**: o programa mantém um arquivo `.download-archive.txt` dentro da pasta de destino para evitar redownload.  
**Solução**: para tentar novamente apenas itens ausentes, rode o menu com a mesma pasta. Os itens registrados no histórico serão pulados. Não apague o histórico para recuperar somente legendas; use o comando da seção [Recuperar somente legendas que falharam](#recuperar-somente-legendas-que-falharam).

### Forçar o download novamente

O menu não possui uma opção de sobrescrita. Para baixar novamente mesmo que os arquivos existam, use o yt-dlp diretamente:

```powershell
uv run python -m yt_dlp --ignore-config --yes-playlist --force-overwrites --no-continue --js-runtimes node -f "bv*+ba/b" --merge-output-format mp4 --windows-filenames --ignore-errors -P "C:\Users\SeuNome\Downloads\SuaPlaylist" -o "%(playlist_index)03d - %(title)s [%(id)s].%(ext)s" "https://www.youtube.com/playlist?list=PLxxxxxxxx"
```

Substitua pasta e URL. Esse comando baixa vídeo e áudio novamente, sobrescreve os arquivos com os mesmos nomes e não usa nem altera `.download-archive.txt`. Se quiser preservar os arquivos anteriores, escolha outra pasta. Não rode junto com outro download para o mesmo destino.

Para incluir legendas, acrescente `--write-subs --write-auto-subs --sub-langs "pt,pt-BR,en" --sub-format srt --sleep-requests 1 --sleep-subtitles 5`. Com Deno, troque `--js-runtimes node` por `--js-runtimes deno`. Para baixar só um vídeo, use uma URL sem `list=...`.

---

## Perguntas frequentes

**Posso baixar um único vídeo em vez de uma playlist inteira?**  
Sim. Cole a URL do vídeo normalmente — o programa detecta automaticamente se é vídeo único ou playlist.

Se a URL contiver `&list=...`, o programa processa a playlist. Para baixar só o vídeo, remova esse parâmetro ou use `https://youtu.be/ID_DO_VIDEO`.

**O programa vai redownload se eu rodar de novo?**  
Não. O arquivo `.download-archive.txt` registra tudo que já foi baixado. Apenas novos vídeos serão baixados.

**Posso usar no macOS / Linux?**  
Sim. O programa é multiplataforma.

**A opção de abrir a pasta funciona em todos os sistemas?**  
Sim: usa `os.startfile` no Windows, `open` no macOS e `xdg-open` no Linux.
