"""Fila de processamento de envios SSI e TSI.

Mudanças de escalabilidade (2.0.7):
- Persistência JSON atômica opcional: quando ``persist=True``, o estado da
  fila é salvo em disco após cada operação. Isso evita perda silenciosa de
  itens em caso de crash ou fechamento inesperado do aplicativo.
- Retrocompatível: o comportamento padrão (``persist=False``) mantém a fila
  exclusivamente em memória, idêntico à versão anterior.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional


class QueueManager:
    def __init__(self, persist: bool = False, data_dir: str = "") -> None:
        """
        Args:
            persist: Se True, persiste a fila em JSON após cada operação.
            data_dir: Diretório onde os arquivos de fila serão gravados.
                      Ignorado quando persist=False.
        """
        self.queue_ssi: list = []
        self.queue_tsi: list = []
        self._persist = persist
        self._data_dir = data_dir

        if persist and data_dir:
            os.makedirs(data_dir, exist_ok=True)
            self._load_from_disk()

    # ------------------------------------------------------------------
    # API pública (retrocompatível)
    # ------------------------------------------------------------------

    def enqueue(self, item: Any, type: str = "SSI") -> None:
        if type == "SSI":
            self.queue_ssi.append(item)
        else:
            self.queue_tsi.append(item)
        if self._persist:
            self._save_to_disk()

    def dequeue(self, type: str = "SSI") -> Optional[Any]:
        item = None
        if type == "SSI" and self.queue_ssi:
            item = self.queue_ssi.pop(0)
        elif type == "TSI" and self.queue_tsi:
            item = self.queue_tsi.pop(0)
        if item is not None and self._persist:
            self._save_to_disk()
        return item

    def clear(self, type: str = "") -> None:
        """Limpa a fila do tipo informado, ou ambas se type estiver vazio."""
        if not type or type == "SSI":
            self.queue_ssi.clear()
        if not type or type == "TSI":
            self.queue_tsi.clear()
        if self._persist:
            self._save_to_disk()

    def size(self, type: str = "SSI") -> int:
        if type == "SSI":
            return len(self.queue_ssi)
        return len(self.queue_tsi)

    # ------------------------------------------------------------------
    # Persistência (ativada somente quando persist=True)
    # ------------------------------------------------------------------

    @property
    def _queue_path(self) -> str:
        return os.path.join(self._data_dir, "queue_state.json")

    def _save_to_disk(self) -> None:
        """Persiste o estado da fila com escrita atômica (os.replace)."""
        if not self._data_dir:
            return
        tmp = self._queue_path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(
                    {"queue_ssi": self.queue_ssi, "queue_tsi": self.queue_tsi},
                    f, ensure_ascii=False, indent=2,
                )
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self._queue_path)
        except Exception:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass

    def _load_from_disk(self) -> None:
        """Restaura o estado da fila do arquivo em disco (se existir)."""
        if not os.path.exists(self._queue_path):
            return
        try:
            with open(self._queue_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                ssi = data.get("queue_ssi", [])
                tsi = data.get("queue_tsi", [])
                if isinstance(ssi, list):
                    self.queue_ssi = ssi
                if isinstance(tsi, list):
                    self.queue_tsi = tsi
        except Exception:
            pass
