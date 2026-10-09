"""Janela Windows; operações de rede e processos nunca bloqueiam o Tk."""
from __future__ import annotations

import ctypes
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from dataclasses import replace
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import parse_qs, urlsplit

from .engine import Cancelled, Engine, Session, Task
from .installation import Installation, bundled_manifest, executable_version, latest_manifest
from .playlist_progress import PlaylistProgress
from .video_progress import VideoProgress
from .settings import VERSION, data_dir, friendly_error, read_json, redact, validate_cookie_file, validate_url, write_json


def newer(version):
    try:
        return tuple(map(int, version.split("."))) > tuple(map(int, VERSION.split(".")))
    except (AttributeError, ValueError):
        return False


HELP = """Se o YouTube solicitar verificação

1. Abra o mesmo vídeo no navegador e confirme que consegue assisti-lo.
2. Clique em Selecionar cookies.txt e escolha um arquivo de cookies exportado do YouTube. Se ainda não tiver um arquivo, siga as instruções de exportação abaixo.
3. Clique em Testar sessão. Consulta e download usam a mesma configuração.

Para exportar uma nova sessão, use a ajuda oficial abaixo. Ela descreve a extensão Get cookies.txt LOCALLY e a exportação de cookies de youtube.com em uma janela privada. Feche a janela privada após exportar; sessões abertas podem ter seus cookies renovados pelo YouTube.

O arquivo dá acesso à sua sessão: mantenha-o no seu computador e não o envie em pedidos de suporte. O aplicativo guarda somente o caminho. Usar uma conta com yt-dlp pode resultar em restrições da conta; use sessão apenas quando necessário.

Acesso negado no Chrome/Edge significa que o programa não conseguiu ler o navegador. Isso é diferente de cookies rejeitados pelo YouTube. Importe um arquivo de cookies ou selecione um perfil do Firefox.

Se o YouTube continuar recusando uma sessão válida, você pode substituir o arquivo ou tentar mais tarde. Não é necessário editar código. Atualizar pode corrigir incompatibilidades, mas não garante remover um bloqueio.
"""


class Application:
    def __init__(self, root: tk.Tk, installation: Installation | None = None, startup=True):
        self.root = root
        self.installation = installation or Installation()
        self.events = queue.Queue()
        self.busy = False
        self.engine: Engine | None = None
        self.manifest = None
        self.last_task: Task | None = None
        self.last_result = None
        self.item_rows = {}
        self.playlist_tracking = False
        self.playlist_progress = PlaylistProgress()
        self.video_progress = VideoProgress()
        self.wait_until = None
        self.preferences = read_json(self.installation.root / "preferences.json")
        self.url = tk.StringVar()
        self.output = tk.StringVar(value=self.preferences.get("output", str(Path.home() / "Downloads" / "YouTube")))
        self.mode = tk.StringVar(value=self.preferences.get("mode", "MP4 — vídeo e áudio"))
        self.subtitles = tk.BooleanVar(value=self.preferences.get("subtitles", False))
        self.cookie_path = tk.StringVar(value=self.preferences.get("cookie_file", ""))
        self.browser = tk.StringVar(value=self.preferences.get("browser", "Sem sessão"))
        self.profile = tk.StringVar(value=self.preferences.get("profile", ""))
        self.status = tk.StringVar(value="Cole um link para começar.")
        self.update_status = tk.StringVar(value="")
        self.session_status = tk.StringVar(value="")
        self.progress_text = tk.StringVar(value="")
        self.playlist_text = tk.StringVar(value="Playlist: consultando o total de vídeos…")
        self.playlist_counts = tk.StringVar(value="")
        self.video_text = tk.StringVar(value="")
        self.title = tk.StringVar(value="")
        self.root.title(f"YouTube Downloader {VERSION}")
        scale = max(1.0, self.root.winfo_fpixels("1i") / 96)
        width = min(int(840 * scale), self.root.winfo_screenwidth() - 60)
        height = min(int(840 * scale), self.root.winfo_screenheight() - 100)
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(min(int(740 * scale), width), min(int(760 * scale), height))
        self.root.configure(bg="#f5f7fa")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#f5f7fa")
        style.configure("TLabel", background="#f5f7fa", foreground="#202d42", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 23, "bold"))
        style.configure("TButton", font=("Segoe UI", 10), padding=(10, 7))
        style.configure("Primary.TButton", background="#245cc5", foreground="white", font=("Segoe UI", 11, "bold"))
        style.map("Primary.TButton", background=[("active", "#184999"), ("disabled", "#91a4c8")])
        style.configure("TCheckbutton", background="#f5f7fa", font=("Segoe UI", 10))
        style.configure("TEntry", padding=6)
        self.build()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(100, self.poll)
        if startup:
            self.root.after(200, self.startup)

    def build(self):
        frame = ttk.Frame(self.root, padding=24)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text="YouTube Downloader", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text="Vídeos, playlists e áudio no seu computador.").grid(row=1, column=0, sticky="w", pady=(0, 16))
        ttk.Label(frame, text="Link do vídeo ou da playlist").grid(row=2, column=0, sticky="w")
        self.url_entry = ttk.Entry(frame, textvariable=self.url)
        self.url_entry.grid(row=3, column=0, sticky="ew", pady=(4, 12))
        self.url_entry.bind("<Return>", lambda event: self.start_download())
        self.url_entry.focus_set()
        destination = ttk.Frame(frame)
        destination.grid(row=4, column=0, sticky="ew")
        destination.columnconfigure(0, weight=1)
        ttk.Label(destination, text="Salvar em").grid(row=0, column=0, sticky="w")
        self.output_entry = ttk.Entry(destination, textvariable=self.output)
        self.output_entry.grid(row=1, column=0, sticky="ew", pady=4)
        self.choose_button = ttk.Button(destination, text="Escolher pasta", command=self.choose_output)
        self.choose_button.grid(row=1, column=1, padx=(8, 0))
        options = ttk.Frame(frame)
        options.grid(row=5, column=0, sticky="ew", pady=10)
        self.mode_box = ttk.Combobox(options, textvariable=self.mode, values=["MP4 — vídeo e áudio", "MP3 — somente áudio"], state="readonly", width=27)
        self.mode_box.pack(side="left")
        self.subtitle_check = ttk.Checkbutton(options, text="Legendas em português e inglês", variable=self.subtitles)
        self.subtitle_check.pack(side="left", padx=18)
        actions = ttk.Frame(frame)
        actions.grid(row=6, column=0, sticky="ew", pady=(0, 12))
        self.download_button = ttk.Button(actions, text="Baixar", style="Primary.TButton", command=self.start_download)
        self.download_button.pack(side="left")
        self.cancel_button = ttk.Button(actions, text="Cancelar", command=self.cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=8)
        ttk.Button(actions, text="Abrir pasta", command=self.open_output).pack(side="right")
        ttk.Label(frame, textvariable=self.status, wraplength=740).grid(row=7, column=0, sticky="w", pady=6)
        ttk.Label(frame, textvariable=self.title, wraplength=740).grid(row=9, column=0, sticky="w", pady=(8, 2))
        ttk.Label(frame, textvariable=self.video_text, wraplength=740).grid(row=10, column=0, sticky="w", pady=(0, 6))
        self.progress = ttk.Progressbar(frame, mode="determinate")
        self.progress.grid(row=12, column=0, sticky="ew")
        ttk.Label(frame, textvariable=self.progress_text, wraplength=740).grid(row=11, column=0, sticky="w", pady=(2, 4))
        self.playlist_frame = ttk.Frame(frame)
        self.playlist_frame.grid(row=8, column=0, sticky="ew", pady=(4, 0))
        self.playlist_frame.columnconfigure(0, weight=1)
        ttk.Label(self.playlist_frame, textvariable=self.playlist_text, wraplength=740).grid(row=0, column=0, sticky="w")
        self.playlist_bar = ttk.Progressbar(self.playlist_frame, mode="determinate")
        self.playlist_bar.grid(row=1, column=0, sticky="ew", pady=4)
        ttk.Label(self.playlist_frame, textvariable=self.playlist_counts, wraplength=740).grid(row=2, column=0, sticky="w")
        self.playlist_frame.grid_remove()
        notebook = ttk.Notebook(frame)
        notebook.grid(row=13, column=0, sticky="nsew", pady=(12, 0))
        frame.rowconfigure(13, weight=1)
        results = ttk.Frame(notebook, padding=10)
        session = ttk.Frame(notebook, padding=10)
        updates = ttk.Frame(notebook, padding=10)
        details = ttk.Frame(notebook, padding=10)
        for child, name in ((results, "Resultados"), (session, "Sessão"), (updates, "Atualização"), (details, "Detalhes")):
            notebook.add(child, text=name)
        self.results = ttk.Treeview(results, columns=("item", "status"), show="headings", height=4)
        self.results.heading("item", text="Vídeo")
        self.results.heading("status", text="Resultado")
        self.results.column("item", width=460)
        self.results.column("status", width=140)
        recovery = ttk.Frame(results)
        recovery.pack(side="bottom", fill="x", pady=(8, 0))
        self.retry_button = ttk.Button(recovery, text="Tentar novamente / retomar", command=self.retry, state="disabled")
        self.retry_button.pack(side="left")
        self.recover_button = ttk.Button(recovery, text="Recuperar legendas", command=lambda: self.retry(True), state="disabled")
        self.recover_button.pack(side="left", padx=8)
        self.results.pack(fill="both", expand=True)
        ttk.Label(session, text="Se o YouTube solicitar verificação, selecione um arquivo de cookies exportado do navegador.", wraplength=720).pack(anchor="w")
        file_row = ttk.Frame(session)
        file_row.pack(fill="x", pady=8)
        self.cookie_entry = ttk.Entry(file_row, textvariable=self.cookie_path)
        self.cookie_entry.pack(side="left", fill="x", expand=True)
        self.cookie_button = ttk.Button(file_row, text="Selecionar cookies.txt", command=self.choose_cookie)
        self.cookie_button.pack(side="left", padx=(8, 0))
        browser_row = ttk.Frame(session)
        browser_row.pack(fill="x")
        ttk.Label(browser_row, text="Alternativa:").pack(side="left")
        self.browser_box = ttk.Combobox(browser_row, textvariable=self.browser, state="readonly", width=20,
            values=["Sem sessão", "Firefox", "Chrome (avançado)", "Edge (avançado)"])
        self.browser_box.pack(side="left", padx=8)
        self.browser_box.bind("<<ComboboxSelected>>", self.browser_selected)
        ttk.Label(browser_row, text="Perfil (opcional):").pack(side="left")
        self.profile_entry = ttk.Entry(browser_row, textvariable=self.profile, width=20)
        self.profile_entry.pack(side="left", padx=8)
        session_actions = ttk.Frame(session)
        session_actions.pack(fill="x", pady=8)
        self.test_button = ttk.Button(session_actions, text="Testar sessão", command=self.test_session)
        self.test_button.pack(side="left")
        self.remove_button = ttk.Button(session_actions, text="Remover sessão", command=self.remove_session)
        self.remove_button.pack(side="left", padx=8)
        ttk.Button(session_actions, text="Abrir vídeo no navegador", command=self.open_video).pack(side="left")
        ttk.Button(session_actions, text="Ajuda com cookies", command=self.help).pack(side="right")
        ttk.Label(session, textvariable=self.session_status, wraplength=720).pack(anchor="w")
        ttk.Label(updates, textvariable=self.update_status, wraplength=720).pack(anchor="w")
        update_actions = ttk.Frame(updates)
        update_actions.pack(fill="x", pady=10)
        self.check_button = ttk.Button(update_actions, text="Verificar atualização", command=self.check_updates)
        self.check_button.pack(side="left")
        self.install_button = ttk.Button(update_actions, text="Preparar / atualizar", command=self.prepare)
        self.install_button.pack(side="left", padx=8)
        self.rollback_button = ttk.Button(update_actions, text="Restaurar ferramentas anteriores", command=self.rollback)
        self.rollback_button.pack(side="left")
        self.app_rollback_button = ttk.Button(updates, text="Restaurar aplicativo anterior", command=self.rollback_app)
        self.app_rollback_button.pack(anchor="w", pady=(0, 8))
        ttk.Label(updates, text="Atualizações preservam configurações, downloads e histórico. Não ocorrem durante downloads.", wraplength=720).pack(anchor="w")
        self.details = tk.Text(details, height=5, wrap="word", font=("Consolas", 9), state="disabled")
        scrollbar = ttk.Scrollbar(details, command=self.details.yview)
        self.details.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.details.pack(fill="both", expand=True)
        self.mutable = [self.url_entry, self.output_entry, self.choose_button, self.subtitle_check,
            self.download_button, self.cookie_entry, self.cookie_button, self.profile_entry, self.test_button,
            self.remove_button, self.check_button, self.install_button, self.rollback_button, self.app_rollback_button]
        def resize_labels(event):
            for child in frame.winfo_children():
                if isinstance(child, ttk.Label):
                    child.configure(wraplength=max(320, event.width - 8))
        frame.bind("<Configure>", resize_labels)

    def emit(self, event):
        self.events.put(event)

    def set_busy(self, value):
        self.busy = value
        for widget in self.mutable:
            widget.configure(state="disabled" if value else "normal")
        for widget in (self.mode_box, self.browser_box):
            widget.configure(state="disabled" if value else "readonly")
        self.cancel_button.configure(state="normal" if value and self.engine else "disabled")
        for widget in (self.retry_button, self.recover_button):
            widget.configure(state="disabled" if value or self.last_task is None else "normal")
        if not value:
            self.progress.stop()
            self.progress.configure(mode="determinate")
            self.playlist_bar.stop()

    def background(self, operation, done=None):
        if self.busy:
            return
        self.set_busy(True)
        def work():
            try:
                result = operation()
                self.emit({"type": "finished", "result": result, "done": done})
            except Cancelled:
                self.emit({"type": "cancelled"})
            except Exception as exc:
                self.emit({"type": "failure", "raw": redact(str(exc)), "exception": type(exc).__name__})
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        for _ in range(100):
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            kind = event["type"]
            if kind == "stage":
                self.status.set(event["text"])
                self.progress.stop()
                self.progress.configure(mode="indeterminate")
                self.progress.start(15)
                self.progress_text.set("")
            elif kind == "video-plan":
                self.wait_until = None
                self.video_progress = VideoProgress.from_plan(event)
                self.title.set("Vídeo atual — " + self.video_progress.title)
                self.video_text.set(self.video_progress.summary)
                self.progress_text.set("Preparando os arquivos deste vídeo…")
                self.progress.stop()
                self.progress.configure(mode="determinate", value=0)
            elif kind == "waiting":
                self.wait_until = time.monotonic() + event["seconds"]
                self.progress.stop()
                self.progress.configure(mode="determinate", value=0)
            elif kind in ("subtitle-start", "subtitle-existing", "subtitle-failure"):
                current = self.video_progress.current
                if kind != "subtitle-failure":
                    if current is not None and self.video_progress.files[current]["subtitle"] and self.video_progress.files[current]["status"] == "Em andamento":
                        self.video_progress.files[current]["status"] = "Concluída"
                    self.video_progress.select_file(subtitle=True)
                if self.video_progress.current is not None and kind != "subtitle-start":
                    self.video_progress.files[self.video_progress.current]["status"] = "Falhou" if kind == "subtitle-failure" else "Concluída"
                self.video_text.set(self.video_progress.summary)
            elif kind == "processing":
                self.video_progress.processing(event.get("postprocessor"), event.get("status"))
                if event.get("postprocessor") in ("Merger", "ExtractAudio", "SubtitlesConvertor", "MoveFiles"):
                    self.wait_until = None
                    self.video_text.set(self.video_progress.summary)
                    self.status.set({"Merger": "Juntando imagem e áudio…", "ExtractAudio": "Convertendo para MP3…",
                                     "SubtitlesConvertor": "Convertendo legendas…", "MoveFiles": "Finalizando arquivo…"}[event["postprocessor"]])
                    self.progress_text.set("Downloads encerrados; processamento do vídeo em andamento.")
                    self.progress.stop()
                    self.progress.configure(mode="indeterminate")
                    self.progress.start(15)
            elif kind == "subtitles-ready":
                for item in self.video_progress.files:
                    if item["subtitle"] and item["status"] != "Falhou":
                        item["status"] = "Concluída"
                self.video_text.set(self.video_progress.summary)
            elif kind == "detail":
                self.append_detail(event["text"])
            elif kind == "progress":
                self.wait_until = None
                self.video_progress.select_file(event.get("format_id"), event.get("subtitle", False))
                percent = event.get("percent")
                current = self.video_progress.current
                file_label = "Arquivo atual"
                if current is not None:
                    file_label = f"Arquivo {current + 1} de {len(self.video_progress.files)} — {self.video_progress.files[current]['label']}"
                self.status.set("Baixando " + self.video_progress.next_label.lower() + "…")
                if percent is not None:
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=percent)
                    eta = event.get("eta")
                    details = f"{percent:.0f}%"
                    if event.get("total"):
                        details += f" · {self.size(event.get('downloaded', 0))} de {'~' if event.get('estimated') else ''}{self.size(event['total'])}"
                    if event.get("speed"):
                        details += f" · {self.size(event['speed'])}/s"
                    if isinstance(eta, (int, float)) and event.get("status") != "finished":
                        details += f" · aproximadamente {int(eta)} s restantes neste arquivo"
                    self.progress_text.set(file_label + ": " + details)
                else:
                    self.progress.stop()
                    self.progress.configure(mode="indeterminate")
                    self.progress.start(15)
                    self.progress_text.set(file_label + ": " + self.size(event.get("downloaded", 0)) + " transferidos · tamanho total desconhecido")
                if event.get("status") == "finished":
                    if current is not None:
                        self.video_progress.files[current]["status"] = "Concluída"
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=100)
                    self.progress_text.set(file_label + ": download concluído. " + self.video_progress.remaining_text)
                    self.status.set("Arquivo baixado. O vídeo ainda está sendo preparado.")
                self.video_text.set(self.video_progress.summary)
            elif kind == "metadata":
                meta = event["value"]
                self.title.set("Vídeo atual — aguardando o primeiro vídeo…" if self.playlist_tracking else "Vídeo atual — " + meta.get("title", ""))
                if self.playlist_tracking:
                    self.playlist_progress = PlaylistProgress.from_metadata(meta)
                    self.refresh_playlist()
                for entry in meta.get("entries") or [meta]:
                    if entry and entry.get("id"):
                        self.item(entry["id"], "Aguardando", entry.get("title"))
            elif kind == "item":
                self.item(event["id"], event["status"])
                if str(event["id"]) == self.video_progress.identifier and event["status"] in ("Concluído", "Falhou"):
                    self.video_progress.end(event["status"])
                    self.video_text.set(self.video_progress.summary)
                    self.wait_until = None
                    if event["status"] == "Concluído":
                        self.progress.stop()
                        self.progress.configure(mode="determinate", value=100)
                        self.progress_text.set("Arquivos e finalização deste vídeo concluídos.")
                if self.playlist_tracking:
                    self.playlist_progress.record(event["id"], event["status"])
                    self.refresh_playlist()
            elif kind == "playlist-position" and self.playlist_tracking:
                self.playlist_progress.begin(event["position"], event["total"])
                self.refresh_playlist()
            elif kind == "playlist-outcome" and self.playlist_tracking:
                self.playlist_progress.record(None, event["status"])
                self.refresh_playlist()
            elif kind == "playlist-filtered" and self.playlist_tracking:
                self.playlist_progress.filtered(event["title"])
                self.refresh_playlist()
            elif kind == "playlist-finished" and self.playlist_tracking:
                self.playlist_progress.finish()
                self.refresh_playlist()
            elif kind in ("finished", "failure", "cancelled"):
                self.wait_until = None
                self.engine = None
                self.set_busy(False)
                if kind == "finished" and event.get("done"):
                    event["done"](event["result"])
                elif kind == "failure":
                    self.video_progress.end("Falhou")
                    self.video_text.set(self.video_progress.summary)
                    raw = event["raw"]
                    self.append_detail(raw)
                    message = raw if event["exception"] in ("ValueError", "PermissionError") or "transmissão" in raw else friendly_error(raw)
                    self.status.set(message)
                    self.session_status.set(message)
                elif kind == "cancelled":
                    self.video_progress.end("Cancelada")
                    self.video_text.set(self.video_progress.summary)
                    self.progress_text.set("Operação interrompida; o vídeo pode estar incompleto.")
                    self.status.set("Operação cancelada. Arquivos parciais e histórico foram preservados; use Retomar.")
        if self.wait_until is not None:
            seconds = max(0, int(self.wait_until - time.monotonic() + 0.999))
            label = self.video_progress.next_label.lower()
            self.status.set(f"Pausa entre downloads: {label} começa em aproximadamente {seconds} s." if seconds else f"Aguardando início de {label}…")
            current = self.video_progress.current
            previous = ""
            if current is not None and self.video_progress.files[current]["status"] == "Concluída":
                previous = f"Arquivo {current + 1} de {len(self.video_progress.files)} — {self.video_progress.files[current]['label']}: download concluído. "
            self.progress_text.set(previous + "Aguardando " + label + ". O vídeo ainda não está pronto.")
        self.root.after(100, self.poll)

    @staticmethod
    def size(value):
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024 or unit == "GB":
                return f"{value:.1f} {unit}"
            value /= 1024

    def refresh_playlist(self):
        progress = self.playlist_progress
        current = f"Vídeo {progress.current}" + (f" de {progress.total}" if progress.total is not None else "") + " · " if progress.current else ""
        if progress.total is None:
            text = f"{progress.processed} processados · total ainda não informado"
        elif progress.total == 0:
            text = "Nenhum vídeo listado"
        else:
            text = f"{progress.processed} de {progress.total} processados · faltam {progress.remaining}"
        self.playlist_text.set("Playlist: " + current + text)
        counts = [f"Concluídos: {progress.count('Concluído')}", f"Já baixados: {progress.count('Já baixado')}",
                  f"Falhas: {progress.count('Falhou')}"]
        if progress.count("Pulado"):
            counts.append(f"Pulados: {progress.count('Pulado')}")
        self.playlist_counts.set(" · ".join(counts))
        self.playlist_bar.stop()
        if progress.percent is None:
            self.playlist_bar.configure(mode="indeterminate", value=0)
            if self.busy and progress.total != 0:
                self.playlist_bar.start(15)
        else:
            self.playlist_bar.configure(mode="determinate", value=progress.percent)

    def append_detail(self, value):
        self.details.configure(state="normal")
        self.details.insert("end", redact(value) + "\n")
        # Evita acumular uma playlist longa indefinidamente na memória.
        if int(self.details.index("end-1c").split(".")[0]) > 600:
            self.details.delete("1.0", "100.0")
        self.details.see("end")
        self.details.configure(state="disabled")

    def item(self, identifier, status, title=None):
        if identifier in self.item_rows:
            row = self.item_rows[identifier]
            label = self.results.item(row, "values")[0]
            self.results.item(row, values=(title or label, status))
        else:
            self.item_rows[identifier] = self.results.insert("", "end", values=(title or identifier, status))

    def save(self):
        write_json(self.installation.root / "preferences.json", {
            "output": self.output.get(), "mode": self.mode.get(), "subtitles": self.subtitles.get(),
            "cookie_file": self.cookie_path.get(), "browser": self.browser.get(), "profile": self.profile.get()})

    def session(self):
        if self.cookie_path.get().strip():
            return Session(cookie_file=validate_cookie_file(Path(self.cookie_path.get().strip())))
        mapping = {"Firefox": "firefox", "Chrome (avançado)": "chrome", "Edge (avançado)": "edge"}
        return Session(browser=mapping.get(self.browser.get()), profile=self.profile.get().strip())

    def task(self, choose_playlist=True):
        url = validate_url(self.url.get())
        playlist = "list" in parse_qs(urlsplit(url).query)
        if choose_playlist and playlist and urlsplit(url).path != "/playlist":
            answer = messagebox.askyesnocancel("Vídeo ou playlist", "Baixar a playlist inteira?\n\nSim: playlist inteira.\nNão: somente este vídeo.", parent=self.root)
            if answer is None:
                return None
            playlist = answer
        return Task(url, Path(self.output.get()).expanduser().resolve(), audio=self.mode.get().startswith("MP3"),
                    subtitles=self.subtitles.get(), playlist=playlist, session=self.session())

    def run_task(self, task: Task, test=False):
        tools = self.installation.tools()
        if not tools:
            self.status.set("Prepare as ferramentas em Atualização antes de baixar.")
            self.prepare()
            return
        self.save()
        if not test and self.details.compare("end-1c", ">", "1.0"):
            self.append_detail("")
        self.engine = Engine(tools, self.emit)
        engine = self.engine
        self.playlist_tracking = not test and task.playlist
        if not test:
            self.last_task = task
            self.last_result = None
            self.results.delete(*self.results.get_children())
            self.item_rows.clear()
            self.playlist_progress = PlaylistProgress()
            self.video_progress = VideoProgress()
            self.wait_until = None
            self.title.set("Vídeo atual — consultando informações…")
            self.video_text.set("")
            if task.playlist:
                self.playlist_frame.grid()
                self.refresh_playlist()
            else:
                self.playlist_frame.grid_remove()
        def work():
            meta = engine.fetch_info(task)
            self.emit({"type": "metadata", "value": meta})
            if test:
                return meta
            return engine.download(task)
        self.background(work, self.session_tested if test else self.download_finished)

    def start_download(self):
        if self.busy:
            return
        try:
            task = self.task()
            if task:
                self.run_task(task)
        except (ValueError, OSError) as exc:
            self.status.set(str(exc))

    def test_session(self):
        try:
            task = self.task(False)
            self.run_task(task, True)
        except (ValueError, OSError) as exc:
            self.session_status.set(str(exc))

    def session_tested(self, metadata):
        self.status.set("Consulta concluída com a sessão selecionada. Você pode iniciar o download.")
        self.session_status.set("Sessão aceita nesta consulta. O download ainda pode sofrer restrições do YouTube.")

    def download_finished(self, result):
        self.last_result = result
        counts = f"{len(result.completed)} concluído(s), {len(result.skipped)} já baixado(s), {len(result.failed)} falha(s)."
        if self.playlist_tracking:
            counts = f"{self.playlist_progress.count('Concluído')} concluídos, {self.playlist_progress.count('Já baixado')} já baixados, {self.playlist_progress.count('Falhou')} com falha."
            if self.playlist_progress.count("Pulado"):
                counts += f" {self.playlist_progress.count('Pulado')} pulados."
            if self.playlist_progress.remaining:
                counts += f" {self.playlist_progress.remaining} sem resultado confirmado."
        destination = str(self.last_task.output_dir) if self.last_task else self.output.get()
        if result.errors or result.exit_code:
            self.status.set(("Playlist encerrada com falhas: " if self.playlist_tracking else "Download encerrado com falha: ") + counts + " " + friendly_error("\n".join(result.errors)) + " Use Tentar novamente / retomar.")
        elif result.warnings:
            summary = "Playlist encerrada: " + counts if self.playlist_tracking else "Vídeo concluído" if result.completed else "Operação encerrada: " + counts
            self.status.set(summary + f". Arquivos em: {destination}. Há avisos; confira Detalhes e as legendas na pasta.")
        elif self.last_task.subtitles_only:
            self.status.set("Consulta de legendas encerrada. Confira os arquivos na pasta; alguns vídeos podem não ter legendas disponíveis.")
        else:
            if self.playlist_tracking:
                self.status.set("Playlist encerrada: " + counts + f" Arquivos em: {destination}. Use Abrir pasta.")
            elif result.completed:
                self.status.set(f"Vídeo concluído e salvo em: {destination}. Use Abrir pasta.")
            elif result.skipped:
                self.status.set(f"Este vídeo já foi baixado. Arquivos em: {destination}. Use Abrir pasta.")
            else:
                self.status.set("Operação encerrada sem novo vídeo concluído. Confira os avisos em Detalhes.")

    def retry(self, subtitles_only=False):
        if self.last_task and not self.busy:
            try:
                task = replace(self.last_task, session=self.session(), subtitles_only=subtitles_only)
                self.run_task(task)
            except ValueError as exc:
                self.status.set(str(exc))

    def choose_output(self):
        folder = filedialog.askdirectory(parent=self.root, title="Onde salvar os downloads?")
        if folder:
            self.output.set(folder)
            self.save()

    def choose_cookie(self):
        filename = filedialog.askopenfilename(parent=self.root, title="Selecionar arquivo de cookies do YouTube",
                                             filetypes=[("Arquivo de cookies", "*.txt"), ("Todos os arquivos", "*.*")])
        if filename:
            try:
                self.cookie_path.set(str(validate_cookie_file(Path(filename))))
                self.browser.set("Sem sessão")
                self.save()
                self.session_status.set("Arquivo selecionado. Cole o link e clique em Testar sessão.")
            except ValueError as exc:
                self.session_status.set(str(exc))

    def browser_selected(self, event=None):
        if self.browser.get() != "Sem sessão":
            self.cookie_path.set("")
        self.save()

    def remove_session(self):
        self.cookie_path.set("")
        self.browser.set("Sem sessão")
        self.profile.set("")
        self.save()
        self.session_status.set("Sessão removida do aplicativo. Seu arquivo original foi preservado.")

    def open_video(self):
        try:
            webbrowser.open(validate_url(self.url.get()))
        except ValueError as exc:
            self.status.set(str(exc))

    def open_output(self):
        try:
            path = Path(self.output.get()).expanduser().resolve()
            if not path.is_dir():
                raise ValueError("A pasta ainda não existe. Ela será criada quando você baixar.")
            os.startfile(path)
        except (OSError, ValueError) as exc:
            self.status.set(str(exc))

    def help(self):
        popup = tk.Toplevel(self.root)
        popup.title("Ajuda com a sessão do YouTube")
        popup.geometry("700x580")
        text = tk.Text(popup, wrap="word", font=("Segoe UI", 11), padx=20, pady=20)
        text.insert("1.0", HELP)
        text.configure(state="disabled")
        text.pack(fill="both", expand=True)
        ttk.Button(popup, text="Abrir instruções oficiais de exportação", command=lambda: webbrowser.open(
            "https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies")).pack(pady=8)

    def startup(self):
        if self.installation.tools():
            self.check_updates()
        else:
            self.prepare(initial=True)

    def check_updates(self):
        self.update_status.set("Verificando versões disponíveis…")
        def work():
            try:
                return latest_manifest(), None
            except Exception as exc:
                return None, redact(str(exc))
        def done(result):
            manifest, error = result
            if error:
                self.update_status.set("Não foi possível verificar atualizações. A instalação existente continua disponível.")
                self.append_detail(error)
                return
            self.manifest = manifest
            app_update = newer(manifest.get("app", {}).get("version"))
            self.update_status.set("Atualização disponível. Clique em Preparar / atualizar." if self.installation.needs_update(manifest) or app_update else "Você está usando as versões verificadas mais recentes.")
        self.background(work, done)

    def prepare(self, initial=False):
        if self.busy:
            return
        if not initial and not messagebox.askokcancel("Preparar / atualizar", "Verificar e preparar as ferramentas e atualizações disponíveis?\n\nOs downloads e a sessão serão preservados.", parent=self.root):
            return
        current_manifest = self.manifest
        def work():
            manifest = current_manifest
            if manifest is None:
                try:
                    manifest = latest_manifest()
                except Exception:
                    manifest = bundled_manifest()
            if self.installation.needs_update(manifest):
                self.installation.install(manifest, self.emit)
            app = manifest.get("app")
            if not initial and app and newer(app.get("version")):
                return self.installation.install_app(app, self.emit)
            return None
        def done(executable):
            self.status.set("Ferramentas prontas. Cole um link e clique em Baixar.")
            self.update_status.set("Preparação concluída. Seus dados foram preservados.")
            if executable:
                self.save()
                subprocess.Popen([str(executable), "--wait-pid", str(os.getpid())], creationflags=subprocess.CREATE_NO_WINDOW)
                self.root.destroy()
        self.background(work, done)

    def rollback(self):
        self.background(self.installation.rollback, lambda result: self.status.set("Ferramentas anteriores restauradas."))

    def rollback_app(self):
        def work():
            state = read_json(self.installation.root / "app.json")
            if not state.get("previous"):
                raise ValueError("Não existe um aplicativo anterior disponível.")
            previous = Path(state["previous"]).resolve()
            if previous.name != "YouTube Downloader.exe" or not previous.is_file():
                raise ValueError("O aplicativo anterior não está mais disponível na pasta original.")
            executable_version(previous, "--self-test")
            write_json(self.installation.root / "app.json", {"active": str(previous), "previous": state["active"]})
            return previous
        def done(executable):
            self.save()
            subprocess.Popen([str(executable), "--use-bundled", "--wait-pid", str(os.getpid())], creationflags=subprocess.CREATE_NO_WINDOW)
            self.root.destroy()
        self.background(work, done)

    def cancel(self):
        if self.engine:
            self.status.set("Cancelando…")
            threading.Thread(target=self.engine.cancel, daemon=True).start()

    def close(self):
        if self.busy:
            if self.engine:
                self.status.set("Clique em Cancelar e aguarde a operação terminar antes de fechar.")
            else:
                self.status.set("Aguarde a preparação terminar antes de fechar. Sua instalação anterior está preservada.")
            return
        self.save()
        self.root.destroy()


def main():
    if "--self-test" in sys.argv:
        tk.Tcl()
        bundled_manifest()
        # Executáveis --windowed não têm stdout. O retorno zero é a prova de execução.
        if sys.stdout:
            print(VERSION)
        return
    if os.name != "nt":
        raise SystemExit("Esta versão do aplicativo é destinada ao Windows.")
    if "--wait-pid" in sys.argv:
        previous_pid = int(sys.argv[sys.argv.index("--wait-pid") + 1])
        kernel_wait = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel_wait.OpenProcess.restype = ctypes.c_void_p
        kernel_wait.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong]
        previous = kernel_wait.OpenProcess(0x100000, False, previous_pid)
        if previous:
            kernel_wait.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            kernel_wait.WaitForSingleObject(previous, 30000)
            kernel_wait.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel_wait.CloseHandle(previous)
    # Um ZIP antigo funciona como lançador da atualização local sem sobrescrever arquivos em uso.
    app_state = read_json(data_dir() / "app.json")
    current = Path(sys.executable).resolve()
    target = Path(app_state.get("active", str(current))).resolve()
    if "--use-bundled" not in sys.argv and getattr(sys, "frozen", False) and target != current and target.is_file() and target.is_relative_to(data_dir().resolve() / "apps"):
        try:
            executable_version(target, "--self-test")
            subprocess.Popen([str(target)], creationflags=subprocess.CREATE_NO_WINDOW)
            return
        except (OSError, subprocess.SubprocessError, ValueError):
            # Um update local danificado nunca impede abrir o ZIP de origem.
            write_json(data_dir() / "app.json", {"active": str(current), "previous": str(target)})
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    handle = kernel.CreateMutexW(None, False, "Local\\YouTubeDownloader-" + str(data_dir()).replace("\\", "_"))
    if ctypes.get_last_error() == 183:
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("YouTube Downloader", "O aplicativo já está aberto. Use a janela existente.")
        root.destroy()
        return
    try:
        root = tk.Tk()
        Application(root)
        root.mainloop()
    finally:
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle(handle)


if __name__ == "__main__":
    main()
