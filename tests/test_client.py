"""Cliente de la API: paginación, reintentos con backoff, errores claros y key nunca expuesta."""

from __future__ import annotations

import pytest
import requests
import responses
from responses import matchers

from eia_pulso.api.client import EIAApiError, EIAClient
from tests.conftest import fila_api

KEY = "CLAVE-SECRETA-123"
URL = "https://api.eia.gov/v2/petroleum/pri/spt/data/"


def _cliente(**kw):
    esperas: list[float] = []
    c = EIAClient(KEY, tamanio_pagina=2, backoff_base_s=0.5, dormir=esperas.append, **kw)
    return c, esperas


def _pagina(filas, total):
    return {"response": {"total": str(total), "data": filas}}


@responses.activate
def test_paginacion_recorre_todas_las_paginas():
    filas = [fila_api("RWTC", f"2026-01-0{i}", 70 + i) for i in range(1, 6)]
    for offset in (0, 2, 4):
        responses.get(
            URL,
            json=_pagina(filas[offset: offset + 2], 5),
            match=[matchers.query_param_matcher({"offset": str(offset), "length": "2"},
                                                strict_match=False)],
        )
    c, _ = _cliente()
    res = c.fetch_data("petroleum/pri/spt", "daily", inicio="2026-01-01",
                       facetas={"series": ["RWTC"]})
    assert len(res.filas) == 5
    assert res.paginas == 3
    assert res.total_api == 5
    assert "api_key" not in res.parametros
    # la key viaja en la query, pero no en los metadatos
    assert f"api_key={KEY}" in responses.calls[0].request.url
    assert KEY not in str(res.parametros)


@responses.activate
def test_reintenta_con_backoff_exponencial_ante_5xx_y_429():
    responses.get(URL, status=503)
    responses.get(URL, status=429)
    responses.get(URL, json=_pagina([fila_api("RWTC", "2026-01-02", 70)], 1))
    c, esperas = _cliente()
    res = c.fetch_data("petroleum/pri/spt", "daily")
    assert len(res.filas) == 1
    assert len(esperas) == 2
    assert 0.5 <= esperas[0] < 0.7 and 1.0 <= esperas[1] < 1.2  # base*2^intento (+jitter)


@responses.activate
def test_reintenta_errores_de_conexion_y_se_agota():
    for _ in range(3):
        responses.get(URL, body=requests.ConnectionError(f"fallo con api_key={KEY}"))
    c, esperas = _cliente(max_reintentos=2)
    with pytest.raises(EIAApiError) as exc:
        c.fetch_data("petroleum/pri/spt", "daily")
    assert "reintentos" in str(exc.value)
    assert KEY not in str(exc.value)
    assert len(esperas) == 2


@responses.activate
def test_error_4xx_no_reintenta_y_da_mensaje_claro_sin_key():
    responses.get(URL, status=403,
                  json={"error": {"code": "API_KEY_INVALID", "message": f"bad key {KEY}"}})
    c, esperas = _cliente()
    with pytest.raises(EIAApiError) as exc:
        c.fetch_data("petroleum/pri/spt", "daily")
    msg = str(exc.value)
    assert "HTTP 403" in msg and "EIA_API_KEY" in msg
    assert KEY not in msg
    assert esperas == []


@responses.activate
def test_error_en_cuerpo_200_se_informa():
    responses.get(URL, json={"error": "Invalid facet"})
    c, _ = _cliente()
    with pytest.raises(EIAApiError, match="Invalid facet"):
        c.fetch_data("petroleum/pri/spt", "daily")


@responses.activate
def test_paginacion_incompleta_falla():
    responses.get(URL, json=_pagina([fila_api("RWTC", "2026-01-02", 70)], 3))
    responses.get(URL, json=_pagina([], 3))
    c, _ = _cliente()
    with pytest.raises(EIAApiError, match="Paginación incompleta"):
        c.fetch_data("petroleum/pri/spt", "daily")
