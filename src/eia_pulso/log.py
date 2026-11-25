"""Logging con enmascarado de secretos."""

from __future__ import annotations

import logging


class MascaraSecretos(logging.Filter):
    """Reemplaza cualquier aparición de los secretos registrados por '***'."""

    def __init__(self, secretos: list[str] | None = None) -> None:
        super().__init__()
        self.secretos = [s for s in (secretos or []) if s]

    def filter(self, record: logging.LogRecord) -> bool:
        if self.secretos:
            msg = record.getMessage()
            for s in self.secretos:
                msg = msg.replace(s, "***")
            record.msg, record.args = msg, None
        return True


def configurar_logging(verbose: bool = False, secretos: list[str] | None = None) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s"))
    handler.addFilter(MascaraSecretos(secretos))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    # urllib3 loguea URLs completas (con la key) en DEBUG: lo silenciamos siempre.
    logging.getLogger("urllib3").setLevel(logging.WARNING)
