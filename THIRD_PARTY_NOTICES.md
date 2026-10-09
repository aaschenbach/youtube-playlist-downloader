# Componentes de terceiros

O aplicativo usa os componentes abaixo. As ferramentas são obtidas diretamente de suas distribuições oficiais, com SHA-256 verificado; o ZIP do aplicativo não incorpora esses executáveis.

| Componente | Licença / fonte |
| --- | --- |
| Python | PSF e licenças relacionadas; cópia em `licenses/PYTHON-LICENSE.txt` no pacote |
| Tcl/Tk | Licença Tcl/Tk; arquivos de licença da distribuição Python em `licenses/` |
| PyInstaller | GPL com exceção para aplicativos empacotados; https://pyinstaller.org/en/stable/license.html |
| yt-dlp.exe | Unlicense e componentes das distribuições binárias; https://github.com/yt-dlp/yt-dlp/blob/master/LICENSE e https://github.com/yt-dlp/yt-dlp/blob/master/THIRD_PARTY_LICENSES.txt |
| Node.js | MIT e componentes relacionados; LICENSE preservado na pasta de ferramentas; https://github.com/nodejs/node/blob/main/LICENSE |
| FFmpeg (build GPL estático) | GPL; avisos preservados na pasta de ferramentas; código e receita de build: https://github.com/yt-dlp/FFmpeg-Builds e https://github.com/FFmpeg/FFmpeg |

No uso por código, Rich (MIT), Questionary (MIT), curl-cffi (MIT) e yt-dlp-ejs (Unlicense e componentes MIT/ISC) mantêm suas próprias licenças. Elas não são necessárias para a janela empacotada.

O projeto não é afiliado ao YouTube, Google, yt-dlp ou Node.js.
