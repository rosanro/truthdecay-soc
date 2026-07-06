"""Memoria persistente del agente (JSONL).

La memoria es donde ocurre el *lavado*: el agente escribe una nota-resumen que puede
haber perdido el puntero a su fuente. En el probe, esa memoria es la unica via por la
que el veneno del seed puede sobrevivir (el documento envenenado ya no existe).

Uso: en memoria (path=None) para la demo; o respaldada en JSONL para runs reales.
"""
from __future__ import annotations

import json
import os
from typing import List, Optional

from core.types import MemoryItem


class Memory:
    def __init__(self, path: Optional[str] = None):
        self.path = path
        self._items: List[MemoryItem] = []
        if path and os.path.exists(path):
            self._load()

    def _load(self):
        self._items = []
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                self._items.append(MemoryItem(**d))

    def _persist(self, item: MemoryItem):
        if not self.path:
            return
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(item.__dict__, ensure_ascii=False) + "\n")

    def write(self, item: MemoryItem):
        self._items.append(item)
        self._persist(item)

    def read(self, pair_id: Optional[str] = None) -> List[MemoryItem]:
        # devuelve copia (la memoria previa se pasa como `memory_before` a la traza)
        return list(self._items)

    def clear(self):
        self._items = []
        if self.path and os.path.exists(self.path):
            os.remove(self.path)
