"""Cache central thread-safe da aplicação SaaS Assistente PRO.

Centraliza o armazenamento temporário em memória de dados que são lidos
com frequência mas raramente alterados (registros TSI/SSI, índice de leads,
configurações de lojas/consultores).

Características:
- Singleton por processo: um único `AppCache` por execução.
- Thread-safe: operações atômicas via `threading.Lock`.
- TTL por entrada: dados expirados são ignorados e removidos na próxima leitura.
- Zero dependências externas: usa apenas stdlib.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional, Tuple


class AppCache:
    """Cache singleton thread-safe com TTL por entrada."""

    _instance: Optional["AppCache"] = None
    _instance_lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        # Protege contra reinicialização acidental via __init__ direto.
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._store: Dict[str, Tuple[Any, float]] = {}  # key -> (value, expires_at)
        self._lock = threading.Lock()

    @classmethod
    def instance(cls) -> "AppCache":
        """Retorna a instância singleton (lazy, thread-safe)."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[Any]:
        """Retorna o valor cacheado ou None se ausente/expirado."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if expires_at != 0 and time.monotonic() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: float = 0) -> None:
        """Armazena um valor.

        Args:
            key: Identificador único da entrada.
            value: Qualquer objeto Python.
            ttl: Tempo de vida em segundos. 0 = sem expiração.
        """
        expires_at = (time.monotonic() + ttl) if ttl > 0 else 0
        with self._lock:
            self._store[key] = (value, expires_at)

    def invalidate(self, key: str) -> None:
        """Remove uma entrada específica do cache."""
        with self._lock:
            self._store.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> None:
        """Remove todas as entradas cujas chaves começam com `prefix`."""
        with self._lock:
            keys_to_remove = [k for k in self._store if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._store[k]

    def clear(self) -> None:
        """Limpa todo o cache."""
        with self._lock:
            self._store.clear()

    def has(self, key: str) -> bool:
        """Retorna True se a chave existe e não expirou."""
        return self.get(key) is not None

    def get_or_set(self, key: str, factory, ttl: float = 0) -> Any:
        """Retorna o valor cacheado ou executa `factory()` para computá-lo.

        Args:
            key: Chave de cache.
            factory: Callable sem argumentos que produz o valor.
            ttl: Tempo de vida em segundos para o valor gerado.
        """
        value = self.get(key)
        if value is None:
            value = factory()
            if value is not None:
                self.set(key, value, ttl)
        return value

    def stats(self) -> Dict[str, int]:
        """Retorna estatísticas básicas para depuração."""
        with self._lock:
            now = time.monotonic()
            total = len(self._store)
            expired = sum(
                1 for _, (_, exp) in self._store.items()
                if exp != 0 and now > exp
            )
            return {"total_entries": total, "expired_entries": expired}
