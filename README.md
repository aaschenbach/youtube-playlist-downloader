# ytdl — YouTube Downloader Interativo

Baixe vídeos e playlists do YouTube com uma interface CLI amigável e interativa.  
Suporta vídeo (MP4), áudio (MP3), legendas automáticas e retoma downloads já iniciados.

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

```bash
git clone https://github.com/aaschenbach/youtube-playlist-downloader.git
cd youtube-playlist-downloader
uv sync
```

### Com pip

```bash
git clone https://github.com/aaschenbach/youtube-playlist-downloader.git
cd youtube-playlist-downloader
pip install -e .
```

> **Nota**: se `pip install` reclamar de permissão, use `pip install --user -e .` ou crie um virtualenv antes:
> ```bash
> python -m venv .venv
> # Windows
> .venv\Scripts\activate
> # macOS / Linux
> source .venv/bin/activate
> pip install -e .
> ```

---

## Como usar

```bash
# Com uv
uv run ytdl

# Com pip / ambiente ativado
ytdl
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

**Causa**: o vídeo foi removido, é privado ou está bloqueado no seu país.  
**Solução**: habilite **"Continuar em erros"** no menu para que a playlist continue mesmo assim.

---

### `ModuleNotFoundError: No module named 'ytdl'`

**Causa**: o pacote não foi instalado corretamente.  
**Solução**:
```bash
# Com uv
uv sync

# Com pip
pip install -e .
```

---

### `command not found: ytdl` / `ytdl não é reconhecido`

**Causa**: o script de entrada não está no PATH.  
**Solução**: use sempre `uv run ytdl` (com uv) ou ative o virtualenv antes de chamar `ytdl`.

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
**Solução**: se quiser forçar o rebaixamento, apague o arquivo `.download-archive.txt` da pasta de destino.

---

## Perguntas frequentes

**Posso baixar um único vídeo em vez de uma playlist inteira?**  
Sim. Cole a URL do vídeo normalmente — o programa detecta automaticamente se é vídeo único ou playlist.

**O programa vai redownload se eu rodar de novo?**  
Não. O arquivo `.download-archive.txt` registra tudo que já foi baixado. Apenas novos vídeos serão baixados.

**Posso usar no macOS / Linux?**  
Sim. O programa é multiplataforma.

**A opção de abrir a pasta funciona em todos os sistemas?**  
Sim: usa `os.startfile` no Windows, `open` no macOS e `xdg-open` no Linux.
