"""Cliente de la API v2 de la EIA: paginación, reintentos con backoff y errores claros.

La API key se envía como parámetro de query (así lo exige la EIA) pero nunca se loguea
ni se incluye en mensajes de error ni en los metadatos que se guardan en Bronze.
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import requests

log = logging.getLogger(__name__)

ESTADOS_REINTENTABLES = {429, 500, 502, 503, 504}


class EIAApiError(RuntimeError):
    """Error no recuperable al consultar la API de la EIA."""


@dataclass
class ResultadoConsulta:
    filas: list[dict[str, Any]]
    total_api: int
    paginas: int
    endpoint: str
    parametros: dict[str, Any]  # sin api_key
    advertencias: list[str] = field(default_factory=list)


class EIAClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.eia.gov/v2",
        tamanio_pagina: int = 5000,
        max_reintentos: int = 5,
        backoff_base_s: float = 1.0,
        timeout_s: float = 60,
        session: requests.Session | None = None,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise ValueError("api_key vacía")
        self._key = api_key
        self.base_url = base_url.rstrip("/")
        self.tamanio_pagina = min(int(tamanio_pagina), 5000)
        self.max_reintentos = max_reintentos
        self.backoff_base_s = backoff_base_s
        self.timeout_s = timeout_s
        self.session = session or requests.Session()
        self._dormir = dormir

    # ------------------------------------------------------------------ helpers
    def _limpiar(self, texto: str) -> str:
        return texto.replace(self._key, "***")

    def _espera(self, intento: int) -> float:
        return self.backoff_base_s * (2**intento) + random.uniform(0, self.backoff_base_s / 4)

    def _get(self, url: str, params: list[tuple[str, str]]) -> dict[str, Any]:
        params_con_key = [("api_key", self._key), *params]
        ultimo_error = ""
        for intento in range(self.max_reintentos + 1):
            try:
                resp = self.session.get(url, params=params_con_key, timeout=self.timeout_s)
            except (requests.ConnectionError, requests.Timeout) as exc:
                ultimo_error = f"{type(exc).__name__}: {self._limpiar(str(exc))}"
            else:
                if resp.status_code == 200:
                    try:
                        cuerpo = resp.json()
                    except ValueError as exc:
                        raise EIAApiError(f"Respuesta no JSON de {url}") from exc
                    if "error" in cuerpo:
                        raise EIAApiError(self._mensaje_error(cuerpo, url, 200))
                    return cuerpo
                if resp.status_code not in ESTADOS_REINTENTABLES:
                    try:
                        cuerpo = resp.json()
                    except ValueError:
                        cuerpo = {"error": resp.text[:300]}
                    raise EIAApiError(self._mensaje_error(cuerpo, url, resp.status_code))
                ultimo_error = f"HTTP {resp.status_code}"

            if intento < self.max_reintentos:
                espera = self._espera(intento)
                log.warning(
                    "Falla transitoria en %s (%s). Reintento %d/%d en %.1fs",
                    url, ultimo_error, intento + 1, self.max_reintentos, espera,
                )
                self._dormir(espera)

        raise EIAApiError(
            f"Se agotaron los {self.max_reintentos} reintentos contra {url}. "
            f"Último error: {ultimo_error}"
        )

    def _mensaje_error(self, cuerpo: dict[str, Any], url: str, status: int) -> str:
        err = cuerpo.get("error", cuerpo)
        if isinstance(err, dict):
            detalle = f"{err.get('code', '')} {err.get('message', '')}".strip()
        else:
            detalle = str(err)
        pista = ""
        if "API_KEY" in detalle.upper():
            pista = " Revisá la variable EIA_API_KEY."
        elif status == 404:
            pista = " La ruta no existe en la API v2: verificá 'ruta' en config/pipeline.yaml."
        return self._limpiar(f"Error de la EIA (HTTP {status}) en {url}: {detalle}.{pista}")

    # ------------------------------------------------------------------ pública
    def fetch_data(
        self,
        ruta: str,
        frecuencia: str,
        inicio: str | None = None,
        facetas: dict[str, list[str]] | None = None,
        fin: str | None = None,
        columnas: tuple[str, ...] = ("value",),
        orden: tuple[str, ...] = ("period", "series"),
    ) -> ResultadoConsulta:
        """Descarga todas las filas de `ruta` recorriendo las páginas (length/offset).

        `columnas` y `orden` permiten rutas que no son series de tiempo (por ejemplo, el
        inventario de generadores, que trae latitud, longitud y capacidad).
        """
        endpoint = f"{self.base_url}/{ruta.strip('/')}/data/"
        base: list[tuple[str, str]] = [("frequency", frecuencia)]
        base += [(f"data[{i}]", c) for i, c in enumerate(columnas)]
        for i, c in enumerate(orden):
            base += [(f"sort[{i}][column]", c), (f"sort[{i}][direction]", "asc")]
        if inicio:
            base.append(("start", inicio))
        if fin:
            base.append(("end", fin))
        for faceta, valores in (facetas or {}).items():
            base.extend((f"facets[{faceta}][]", v) for v in valores)

        filas: list[dict[str, Any]] = []
        advertencias: list[str] = []
        offset, paginas, total = 0, 0, 0
        while True:
            params = [*base, ("offset", str(offset)), ("length", str(self.tamanio_pagina))]
            cuerpo = self._get(endpoint, params)
            resp = cuerpo.get("response")
            if not isinstance(resp, dict) or not isinstance(resp.get("data"), list):
                raise EIAApiError(f"Respuesta sin 'response.data' en {endpoint}")
            for w in resp.get("warnings", []) or []:
                texto = self._limpiar(str(w.get("description", w)))
                advertencias.append(texto)
                log.warning("Advertencia de la EIA en %s: %s", ruta, texto)
            datos = resp["data"]
            total = int(resp.get("total") or 0)
            filas.extend(datos)
            paginas += 1
            offset += len(datos)
            if not datos or offset >= total:
                break

        if total and len(filas) < total:
            raise EIAApiError(
                f"Paginación incompleta en {ruta}: {len(filas)} filas de {total} informadas"
            )
        parametros: dict[str, Any] = {"frequency": frecuencia, "start": inicio, "end": fin,
                                      "facets": facetas or {}, "length": self.tamanio_pagina}
        log.info("%s [%s]: %d filas en %d página(s)", ruta, frecuencia, len(filas), paginas)
        return ResultadoConsulta(filas, total, paginas, endpoint, parametros, advertencias)
