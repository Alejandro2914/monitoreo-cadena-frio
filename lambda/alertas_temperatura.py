
from datetime import datetime, timezone

# Tiempo que debe permanecer una temperatura fuera de rango.
# Inicialmente utilizaremos 60 segundos para las pruebas.
DURACION_ALERTA_SEGUNDOS = 60

RANGO_MIN_DEFAULT = 2.0
RANGO_MAX_DEFAULT = 8.0


def convertir_fecha(fecha):
    """Convierte una fecha ISO 8601 a UTC."""
    resultado = datetime.fromisoformat(
        str(fecha).replace("Z", "+00:00")
    )

    if resultado.tzinfo is None:
        raise ValueError("La fecha debe incluir zona horaria")

    return resultado.astimezone(timezone.utc)


def evaluar_temperatura(lectura, estado_anterior=None):
    """
    Evalua una lectura y devuelve el nuevo estado de alerta.

    No realiza operaciones sobre AWS.
    """
    temperatura = float(lectura["temperatura_c"])

    rango_min = float(
        lectura.get("rango_min_c", RANGO_MIN_DEFAULT)
    )
    rango_max = float(
        lectura.get("rango_max_c", RANGO_MAX_DEFAULT)
    )

    fecha_actual = convertir_fecha(lectura["marca_tiempo"])

    if rango_min >= rango_max:
        raise ValueError("El rango de temperatura es invalido")

    if estado_anterior is None:
        estado_anterior = {}

    ultima_fecha = estado_anterior.get("ultima_fecha_lectura")

    # Una lectura atrasada no debe modificar el estado actual.
    if ultima_fecha is not None:
        if fecha_actual <= convertir_fecha(ultima_fecha):
            return {
                "evento": "LECTURA_ATRASADA",
                "estado": dict(estado_anterior),
            }

    fuera_de_rango = (
        temperatura < rango_min
        or temperatura > rango_max
    )

    if not fuera_de_rango:
        estaba_en_alerta = bool(
            estado_anterior.get("alerta_activa", False)
        )

        return {
            "evento": (
                "TEMPERATURA_RECUPERADA"
                if estaba_en_alerta
                else "TEMPERATURA_NORMAL"
            ),
            "estado": {
                "inicio_anomalia": None,
                "alerta_activa": False,
                "ultima_fecha_lectura": fecha_actual.isoformat(),
            },
        }

    inicio_anomalia = estado_anterior.get("inicio_anomalia")

    if inicio_anomalia is None:
        inicio = fecha_actual
    else:
        inicio = convertir_fecha(inicio_anomalia)

    segundos_fuera = (
        fecha_actual - inicio
    ).total_seconds()

    alerta_activa = bool(
        estado_anterior.get("alerta_activa", False)
    )

    if alerta_activa:
        evento = "ALERTA_CONTINUA"
    elif segundos_fuera >= DURACION_ALERTA_SEGUNDOS:
        evento = "ALERTA_ACTIVADA"
        alerta_activa = True
    else:
        evento = "ANOMALIA_INICIAL"

    return {
        "evento": evento,
        "estado": {
            "inicio_anomalia": inicio.isoformat(),
            "alerta_activa": alerta_activa,
            "ultima_fecha_lectura": fecha_actual.isoformat(),
        },
    }
