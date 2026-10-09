"""Conta tentativas da lista, separadamente dos bytes do arquivo atual."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PlaylistProgress:
    total: int | None = None
    current: int | None = None
    current_id: str | None = None
    ids: dict[int, str] = field(default_factory=dict)
    titles: dict[int, str] = field(default_factory=dict)
    outcomes: dict[int, str] = field(default_factory=dict)

    @classmethod
    def from_metadata(cls, metadata: dict):
        entries = metadata.get("entries")
        if not isinstance(entries, list):
            return cls()
        return cls(total=len(entries), ids={index: str(entry["id"]) for index, entry in enumerate(entries, 1)
                                          if entry and entry.get("id")},
                   titles={index: entry["title"] for index, entry in enumerate(entries, 1) if entry and entry.get("title")})

    def filtered(self, title):
        position = next((index for index, value in self.titles.items() if value == title and index not in self.outcomes), None)
        if position is not None:
            self.outcomes[position] = "Pulado"
        else:
            self.record(None, "Pulado")

    def begin(self, position: int, total: int | None):
        self.current, self.current_id = position, None
        if total is not None:
            self.total = max(total, position)

    def record(self, identifier: str | None, status: str):
        position = None
        if self.current is not None and identifier and (
            self.current_id == identifier or self.ids.get(self.current) == identifier
        ) and (self.current not in self.outcomes or status != "Já baixado"):
            position = self.current
        if position is None and identifier:
            position = next((index for index, video_id in self.ids.items()
                             if video_id == identifier and index not in self.outcomes), None)
        if position is None and self.current is not None and self.current not in self.outcomes:
            position = self.current
        if position is None:
            return
        if status == "Baixando":
            self.current, self.current_id = position, identifier
            return
        if status in ("Concluído", "Já baixado", "Falhou", "Pulado"):
            if self.outcomes.get(position) == "Falhou" and status == "Concluído":
                return
            self.outcomes[position] = status

    def finish(self):
        # O fim do subprocesso não comprova o resultado de itens sem eventos.
        pass

    @property
    def processed(self):
        return len(self.outcomes)

    @property
    def remaining(self):
        return None if self.total is None else max(0, self.total - self.processed)

    @property
    def percent(self):
        return None if not self.total else min(100, self.processed / self.total * 100)

    def count(self, status):
        return sum(value == status for value in self.outcomes.values())
