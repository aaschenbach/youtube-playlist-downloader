"""Etapas reais do vídeo, independentes dos bytes de cada arquivo."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VideoProgress:
    title: str = "Consultando informações…"
    identifier: str = ""
    files: list[dict] = field(default_factory=list)
    steps: dict[str, str] = field(default_factory=dict)
    current: int | None = None

    @classmethod
    def from_plan(cls, event):
        video = event["video"]
        model = cls(title=video.get("title") or video["id"], identifier=str(video["id"]))
        for index, subtitle in enumerate(event.get("subtitles") or []):
            model.files.append({"key": f"sub:{index}", "label": f"Legenda {index + 1}", "subtitle": True, "status": "Aguardando"})
        formats = event.get("formats") or [video]
        if not event.get("subtitles_only"):
            for index, fmt in enumerate(formats):
                label = "Áudio" if fmt.get("vcodec") == "none" else "Imagem" if fmt.get("acodec") == "none" else "Vídeo e áudio"
                model.files.append({"key": str(fmt.get("format_id", index)), "label": label, "subtitle": False, "status": "Aguardando"})
            if event.get("audio"):
                model.steps["Converter para MP3"] = "Aguardando"
            elif len(formats) > 1:
                model.steps["Juntar imagem e áudio"] = "Aguardando"
        if event.get("subtitles_requested") and not event.get("subtitles"):
            model.steps["Legendas"] = "Não disponíveis"
        model.steps["Finalizar arquivo"] = "Aguardando"
        return model

    def select_file(self, format_id=None, subtitle=False):
        if subtitle and self.current is not None and self.files[self.current]["subtitle"] and self.files[self.current]["status"] == "Em andamento":
            return
        candidates = [(index, item) for index, item in enumerate(self.files) if item["subtitle"] == subtitle]
        match = next((index for index, item in candidates if format_id is not None and item["key"] == str(format_id)), None)
        if match is None:
            match = next((index for index, item in candidates if item["status"] == "Aguardando"), None)
        if match is not None:
            self.current = match
            self.files[match]["status"] = "Em andamento"

    def processing(self, name, status):
        labels = {"Merger": "Juntar imagem e áudio", "ExtractAudio": "Converter para MP3",
                  "SubtitlesConvertor": "Converter legendas", "MoveFiles": "Finalizar arquivo"}
        label = labels.get(name)
        if label:
            self.steps[label] = "Concluída" if status == "finished" else "Em andamento"

    def end(self, status):
        if status == "Concluído":
            for item in self.files:
                if item["status"] != "Falhou":
                    item["status"] = "Concluída"
            for name in self.steps:
                if self.steps[name] != "Não disponíveis":
                    self.steps[name] = "Concluída"
        else:
            if self.current is not None and self.files[self.current]["status"] == "Em andamento":
                self.files[self.current]["status"] = status
            for name in self.steps:
                if self.steps[name] == "Em andamento":
                    self.steps[name] = status

    @property
    def summary(self):
        return " · ".join([f"{item['label']}: {item['status']}" for item in self.files]
                          + [f"{name}: {status}" for name, status in self.steps.items()])

    @property
    def next_label(self):
        if self.current is not None and self.files[self.current]["status"] == "Em andamento":
            return self.files[self.current]["label"]
        return next((item["label"] for item in self.files if item["status"] == "Aguardando"), "próxima etapa")

    @property
    def remaining_text(self):
        pending = [item["label"].lower() for item in self.files if item["status"] == "Aguardando"]
        pending += [name.lower() for name, state in self.steps.items() if state == "Aguardando"]
        return "Ainda falta: " + ", ".join(pending) + "." if pending else "Finalização em andamento."
