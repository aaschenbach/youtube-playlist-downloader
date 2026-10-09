# Resultado da validação local — 2026-10-09

Ambiente: Windows 11 x64, Python 3.14.0, PyInstaller 6.22.3. A máquina já possui ferramentas de desenvolvimento; não equivale a Windows limpo.

## Executado

- `python -m unittest discover -s tests -v`: **23 testes, OK**.
- `ruff check --isolated --select E4,E7,E9,F src scripts tests`: **All checks passed**.
- `git diff --check`: sem erros de whitespace; Git informou somente conversão futura de LF para CRLF.
- `python scripts/build_windows.py`: ZIP gerado, executável congelado passou em `--self-test`.
- `python scripts/verify_windows.py --prepare`: preparação real das ferramentas em pasta isolada com espaços e acentos; versões e argumentos verificados.
- `python scripts/verify_windows.py --fixture`: vídeo próprio de um segundo servido somente em HTTP local; metadados, MP4, histórico e conversão MP3 passaram. Servidor e processos encerrados ao terminar.
- Capturas de janela inicial, sessão e atualização examinadas em tamanho normal e texto ampliado a 150%. Controles utilizáveis e sem cortes nas capturas.
- `python scripts/verify_windows.py --package dist/YouTubeDownloader-2.0.0-Windows-x64.zip`: extração, instalação de atualização local e teste do executável passaram.

As ferramentas preparadas foram yt-dlp 2026.08.19, Node v24.21.0 e FFmpeg autobuild-2026-10-08-19-47. Foram obtidas dos URLs versionados do manifesto e verificadas por SHA-256.

O teste real detectou e corrigiu a supressão de mensagens de histórico causada por `--print` e um filtro de lives que recusava vídeos sem `live_status`. A regressão do filtro está na suíte.

## Pendente antes da publicação

- Consulta/download real de um vídeo do YouTube usando uma sessão de teste. Nenhum cookie real foi lido ou usado nesta validação.
- Windows 10/11 limpo, conta sem administrador, sem ferramentas de desenvolvimento.
- Playlist real, legendas reais e lives reais. Esses fluxos têm cobertura controlada, mas não validação de acesso ao YouTube.
- Atualização entre duas Releases publicadas no GitHub e GitHub Actions no remoto. O teste local de ZIP não comprova publicação ou execução de CI.

O ZIP, manifesto e checksum estão em `dist/`. Nenhuma Release foi publicada.

## Correção 2.0.1

- Textos de janela, ajuda e documentação revisados para público geral; removidas referências a experiências específicas e ao histórico de atendimento.
- Instalação de ferramentas prepara uma pasta definitiva ainda inativa e só altera o ponteiro após a conferência. Não move a pasta depois de executar FFmpeg/ffprobe.
- Bloqueios Windows 5/32/33 têm tentativas com espera limitada. Falha na limpeza de temporários não substitui o erro original nem invalida uma instalação concluída.
- Cache de downloads verifica SHA-256 novamente antes de reutilizar arquivos em uma nova tentativa.
- **28 testes passaram**, incluindo bloqueio real de arquivo no Windows, falha de limpeza, espera limitada, ativação sem mover diretório executado e reutilização de cache. Verificação Ruff também passou.
- Preparação real concluída tanto na pasta isolada de validação quanto em `%LOCALAPPDATA%\YouTubeDownloader`. Configurações de sessão não foram alteradas.
- ZIP 2.0.1 gerado e executável congelado aprovado no teste de inicialização.

## Ajuste 2.0.2

- Detalhes insere uma linha em branco antes de cada nova sessão de download, incluindo retomadas e recuperação de legendas.
- Verificação direta do componente Tk confirmou a separação e a ausência de linha vazia no primeiro download sem registros anteriores.
- Nomes de arquivos de playlist voltaram a usar pelo menos três dígitos: `001 -`, `002 -`, `010 -`. A formatação foi conferida com o yt-dlp para vídeo único e índices 1, 2, 10, 100 e 1000.

## Acompanhamento 2.0.3

- Barra da playlist separada da barra do arquivo atual, com posição, total processado e quantidade restante. Concluídos, já baixados e falhas aparecem separadamente.
- Contagem atualizada por eventos reais do yt-dlp. Cancelamento mantém o progresso parcial; total desconhecido não recebe porcentagem estimada.
- **38 testes passaram**, incluindo contagem de itens repetidos, falhas, histórico, cancelamento e separação entre progresso do arquivo e da lista. Ruff também passou.
- Playlist de dois vídeos próprios servidos por HTTP local: metadados, progresso e duas conclusões conferidos com o motor real. Na repetição, os dois itens foram identificados como já baixados.
- Capturas com acompanhamento da playlist conferidas em tamanho normal e texto ampliado a 150%.
- ZIP 2.0.3 gerado; extração, atualização local e teste de inicialização do executável congelado passaram.

## Acompanhamento 2.0.4

- Três níveis de acompanhamento: playlist por itens, vídeo por etapas e arquivo por bytes. Imagem, áudio, legendas, junção e conversão têm estados próprios.
- Pausas reais de 5–10 segundos aparecem com contagem regressiva. Os intervalos também se aplicam à CLI; consultas de metadados usam espera entre requisições.
- Conclusão explícita com pasta de destino; o motor verifica a existência do arquivo final antes de anunciar sucesso. Cancelamento e falhas preservam etapas concluídas e arquivos parciais.
- Itens sem resultado identificado não completam artificialmente a barra da playlist. Pulados pelo filtro são contados separadamente.
- **49 testes passaram**. Ruff e verificação de whitespace passaram.
- Teste real com manifesto DASH local: plano dos dois arquivos recebido antes dos downloads; esperas, identidade da imagem/áudio e eventos de junção conferidos. Testes locais de MP4, histórico e MP3 também passaram.
- Capturas de espera, áudio, finalização e conclusão examinadas em 100% e 150%. Botões de recuperação permanecem visíveis.
- O teste local corrigiu o nome do estágio de impressão para `video` (antes dos downloads) e isolou a geração dos fragmentos DASH na pasta da própria fixture.
- Playlist real em HTTP local conferida novamente: total, progresso, conclusões e itens já baixados passaram.
- ZIP 2.0.4 gerado; extração, atualização local e teste de inicialização do executável congelado passaram. Nenhuma Release foi publicada.
