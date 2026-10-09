# YouTube Downloader para Windows

Baixe vídeos, playlists, áudio MP3 e legendas com uma janela no seu computador. A versão para usuários funciona no Windows 10/11 de 64 bits.

## Baixar e abrir

1. Abra a página de [Releases](https://github.com/aaschenbach/youtube-playlist-downloader/releases).
2. Baixe o **YouTubeDownloader-2.0.4-Windows-x64.zip** da versão disponível. Os arquivos **Source code** são para desenvolvimento.
3. Extraia **todo** o ZIP e abra **YouTube Downloader.exe** na pasta extraída.

A primeira abertura prepara as ferramentas com internet e mostra cada etapa. Não precisa instalar Python, Git, Node ou FFmpeg, abrir terminal, alterar PATH ou ter acesso de administrador. Mantenha o executável junto da pasta `_internal`.

**Disponibilidade:** o pacote é gerado pelo workflow do projeto. Ele estará disponível para baixar depois que o mantenedor publicar ZIP e `manifest.json` em uma Release. Baixar o código pelo botão Code não substitui essa publicação.

## Baixar e retomar

Cole o link, escolha a pasta, selecione MP4 ou MP3 e clique em **Baixar**. Legendas tenta obter português e inglês quando disponíveis. A pasta inicial é `Downloads/YouTube`. Para um link que contenha vídeo e playlist, o aplicativo pergunta qual deseja baixar.

Arquivos de playlist recebem numeração com pelo menos três dígitos: `001 -`, `002 -`, `003 -`.

A janela acompanha três níveis: **playlist**, **vídeo atual** e **arquivo atual**. O vídeo mostra as etapas aplicáveis (imagem, áudio, legendas e finalização); o arquivo mostra sua identificação, percentual, bytes, velocidade e tempo estimado. Chegar a 100% em um arquivo não significa que o vídeo terminou: a janela informa o que falta, incluindo áudio e junção. A conclusão aparece explicitamente com a pasta de destino. Gravações de lives encerradas são aceitas; transmissões ativas ou agendadas não são gravadas.

As pausas de 5–10 segundos antes dos downloads aparecem com contagem regressiva baseada na duração informada pelo motor. Percentuais e estimativas pertencem ao arquivo atual e só aparecem quando há dados; não há percentual artificial para o vídeo inteiro. Os intervalos também se aplicam à CLI e não garantem evitar restrições do YouTube.

Para playlists, uma segunda barra acompanha a lista toda: vídeo atual, quantidade processada e quantos faltam. Concluídos, já baixados e falhas são contados separadamente. O percentual representa itens processados, não o tamanho dos arquivos; uma playlist totalmente processada ainda pode conter falhas. Se o total não for conhecido, o aplicativo mostra a contagem sem inventar percentual. Ao cancelar, o acompanhamento mantém o avanço real até a interrupção.

Use **Cancelar** e aguarde antes de fechar. **Tentar novamente / retomar** preserva arquivos parciais e o histórico `.download-archive.txt`. A retomada consulta a tarefa e pula os vídeos registrados no histórico.

**Recuperar legendas** consulta os itens sem usar o histórico de vídeos, sem baixar áudio/vídeo e preservando legendas existentes. Alguns vídeos não possuem legendas; confira os arquivos e os avisos.

## Quando o YouTube pedir verificação

Abra o vídeo no navegador e confirme que consegue assisti-lo. Na aba **Sessão**, clique em **Selecionar cookies.txt** e escolha um arquivo de cookies exportado do YouTube. Se ainda não tiver o arquivo, consulte **Ajuda com cookies**. Ele pode estar em qualquer pasta. Cole o link e clique em **Testar sessão**.

Consulta e download usam o mesmo arquivo e Node. O teste confirma somente aquela consulta; o YouTube ainda pode restringir o download.

Para obter um novo arquivo, clique em **Ajuda com cookies** e siga as [instruções oficiais de exportação](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies). A ajuda explica a exportação de `youtube.com` em janela privada. Cookies dão acesso à sua sessão: mantenha-os no computador e não os envie ao suporte. Usar uma conta com yt-dlp pode resultar em restrições da conta.

Firefox e seus perfis são alternativas opcionais. Chrome/Edge ficam nas opções avançadas: **acesso negado** significa falha na leitura do navegador, não rejeição de um arquivo escolhido manualmente.

**Remover sessão** apaga a configuração do aplicativo e preserva o arquivo original. O arquivo selecionado tem preferência sobre leitura do navegador.

Em **HTTP 429**, aguarde antes de tentar novamente. O aplicativo interrompe uma playlist bloqueada, preserva a tarefa e evita insistir automaticamente. Se uma sessão válida continuar recusada, a janela informa isso. Cookies e atualização não garantem superar todo bloqueio.

## Atualizar e reparar

O aplicativo verifica versões publicadas ao abrir. Na aba **Atualização**, use **Verificar atualização** e **Preparar / atualizar**.

A nova versão é preparada separadamente, verifica SHA-256 e testa ferramentas antes de ativá-las. Bloqueios temporários de arquivos pelo Windows têm espera limitada; downloads já verificados são reutilizados nas próximas tentativas. Falhas preservam a versão anterior. Não há atualização durante downloads. Use **Restaurar ferramentas anteriores** ou **Restaurar aplicativo anterior** para voltar à versão disponível anteriormente.

Ferramentas e preferências ficam em `%LOCALAPPDATA%\YouTubeDownloader`. Cookies permanecem no local escolhido. O programa não envia cookies a servidores do projeto; yt-dlp usa a sessão para acessar o YouTube.

Um ZIP antigo pode abrir o aplicativo atualizado na pasta local. Atualizações vêm de Releases publicadas, sem acompanhar branches de desenvolvimento ou instalar dependências Python no computador do usuário.

## Pedir ajuda

Consulte **Detalhes** e descreva a etapa que falhou em uma [issue](https://github.com/aaschenbach/youtube-playlist-downloader/issues). Não envie cookies, senhas ou sessões. Os detalhes removem parâmetros das URLs extraídas e valores identificados como credenciais.

## Desenvolvimento

Este caminho é para trabalhar no código; usuários finais devem usar o ZIP.

```powershell
git clone https://github.com/aaschenbach/youtube-playlist-downloader.git
cd youtube-playlist-downloader
uv sync --extra build
uv run --extra build ytdl-window
```

A janela por código usa as mesmas ferramentas gerenciadas que o executável. A CLI técnica continua em `uv run ytdl`, com configuração de cookies pelo menu e preferências compartilhadas. A CLI usa a biblioteca Python yt-dlp e ferramentas no PATH; a distribuição para usuários finais é a janela.

```powershell
uv run --extra build python -m unittest discover -s tests -v
uv run --extra build python scripts/build_windows.py
```

O build gera ZIP, `dist/manifest.json` e `dist/SHA256SUMS.txt`. O workflow Windows testa e guarda esses arquivos como artifact, sem publicar automaticamente.

Para atualizar as ferramentas verificadas antes de um novo build:

```powershell
uv run --extra build python scripts/resolve_tools.py
```

Esse comando altera `src/ytdl/tools-manifest.json`: revisar, testar e versionar a mudança. O manifesto usa FFmpeg datado, Node LTS compatível e uma Release oficial do yt-dlp, com URLs de versões específicas. O aplicativo ignora configurações externas de yt-dlp para manter escolhas explícitas.

Antes de publicar, siga [a validação Windows](docs/VALIDACAO-WINDOWS.md). Testes simulados não comprovam aceitação de sessões reais; testes com cookies pessoais ficam fora do CI.

## Créditos

Usa [yt-dlp](https://github.com/yt-dlp/yt-dlp), [Node.js](https://nodejs.org/) e [FFmpeg](https://ffmpeg.org/). Consulte [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Não é afiliado ao YouTube ou Google.
