
import json
import logging

import paho.mqtt.client as mqtt

from buffer_offline import (
    eliminar_lectura,
    obtener_pendientes,
    contar_pendientes,
)
from config import MQTT_QOS

logger = logging.getLogger(__name__)


def reenviar_pendientes(cliente, id_acopio, limite=100):
    """
    Reenvia las lecturas pendientes del centro indicado.

    Conserva el UUID y la marca temporal originales.

    Una lectura se elimina de SQLite solamente cuando el
    broker confirma su recepcion mediante MQTT QoS 1.
    """
    if not cliente.is_connected():
        print(f"{id_acopio}: sin conexion MQTT. Se conserva el buffer.")
        return 0

    lecturas = obtener_pendientes(
        id_acopio=id_acopio,
        limite=limite,
    )

    reenviadas = 0

    for lectura in lecturas:
        if not cliente.is_connected():
            print("Conexion perdida durante el reenvio.")
            break

        try:
            resultado = cliente.publish(
                topic=lectura["topico"],
                payload=json.dumps(lectura, ensure_ascii=False),
                qos=MQTT_QOS,
            )

            if resultado.rc != mqtt.MQTT_ERR_SUCCESS:
                print(
                    f"Error al publicar lectura pendiente: "
                    f"{resultado.rc}"
                )
                break

            resultado.wait_for_publish(timeout=10)

            if not resultado.is_published():
                print("Lectura sin confirmacion. Permanece en SQLite.")
                break

            eliminar_lectura(lectura["id_lectura"])
            reenviadas += 1

            print(
                f"{id_acopio}: lectura reenviada: "
                f"{lectura['id_lectura']}"
            )

        except (OSError, RuntimeError, ValueError) as error:
            logger.warning("Error durante reenvio MQTT: %s", error)
            break

    print(
        f"{id_acopio}: reenviadas={reenviadas}, "
        f"pendientes={contar_pendientes(id_acopio)}"
    )

    return reenviadas
