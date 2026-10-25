

import json
import logging
import os
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from alertas_temperatura import evaluar_temperatura
from estado_alertas import obtener_estado, guardar_estado


logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")

TABLA_DYNAMODB = os.environ["DYNAMODB_TABLE"]
tabla = dynamodb.Table(TABLA_DYNAMODB)

MAX_INTENTOS_ESTADO = 5


def es_error_condicional(error):
    return (
        error.response["Error"]["Code"]
        == "ConditionalCheckFailedException"
    )


def actualizar_alerta(camara_id, lectura):
    """
    Evalua y persiste el estado de temperatura de una camara.

    Ante un conflicto de concurrencia, vuelve a consultar
    el estado y recalcula la evaluacion.
    """
    for intento in range(1, MAX_INTENTOS_ESTADO + 1):
        estado_anterior = obtener_estado(
            camara_id,
            tabla=tabla,
        )

        evaluacion = evaluar_temperatura(
            lectura,
            estado_anterior,
        )

        evento = evaluacion["evento"]

        if evento == "LECTURA_ATRASADA":
            logger.info(
                "Lectura atrasada ignorada para alerta: %s",
                camara_id,
            )
            return evento

        guardado = guardar_estado(
            camara_id,
            evaluacion["estado"],
            estado_anterior=estado_anterior,
            tabla=tabla,
        )

        if guardado:
            if evento in (
                "ALERTA_ACTIVADA",
                "TEMPERATURA_RECUPERADA",
            ):
                logger.warning(
                    "Evento de temperatura: %s, camara=%s",
                    evento,
                    camara_id,
                )
            else:
                logger.info(
                    "Estado de temperatura: %s, camara=%s",
                    evento,
                    camara_id,
                )

            return evento

        logger.warning(
            "Conflicto de estado en %s, intento %s/%s",
            camara_id,
            intento,
            MAX_INTENTOS_ESTADO,
        )

    raise RuntimeError(
        f"No se pudo actualizar el estado de {camara_id} "
        "por conflictos concurrentes"
    )


def lambda_handler(event, context):
    """
    Guarda lecturas MQTT con deduplicacion estricta
    y actualiza el seguimiento de alertas sostenidas.

    Si la lectura ya existe, recupera la version original
    para completar el estado si un intento anterior fallo.
    """
    try:
        id_acopio = event["id_acopio"]
        id_camara = event["id_camara"]
        id_lectura = event["id_lectura"]
        marca_tiempo = event["marca_tiempo"]

        camara_id = f"{id_acopio}#{id_camara}"
        lectura_id = f"{marca_tiempo}#{id_lectura}"

        lectura = json.loads(
            json.dumps(event),
            parse_float=Decimal,
            parse_int=Decimal,
        )

        lectura["camara_id"] = camara_id
        lectura["lectura_id"] = lectura_id

        duplicada = False

        try:
            tabla.put_item(
                Item=lectura,
                ConditionExpression=(
                    "attribute_not_exists(camara_id) "
                    "AND attribute_not_exists(lectura_id)"
                ),
            )

            logger.info(
                "Lectura almacenada correctamente: %s",
                lectura_id,
            )

        except ClientError as error:
            if not es_error_condicional(error):
                raise

            duplicada = True

            logger.info(
                "Lectura duplicada detectada: %s",
                lectura_id,
            )

            # Recuperar los valores que quedaron almacenados.
            # No confiar en los datos de una nueva publicacion
            # que utilice el mismo identificador.
            respuesta = tabla.get_item(
                Key={
                    "camara_id": camara_id,
                    "lectura_id": lectura_id,
                },
                ConsistentRead=True,
            )

            lectura_original = respuesta.get("Item")

            if lectura_original is None:
                raise RuntimeError(
                    "No se encontro la lectura duplicada "
                    "en DynamoDB"
                )

            lectura = lectura_original

        evento_alerta = actualizar_alerta(
            camara_id,
            lectura,
        )

        return {
            "statusCode": 200,
            "resultado": (
                "duplicada" if duplicada else "almacenada"
            ),
            "camara_id": camara_id,
            "lectura_id": lectura_id,
            "evento_alerta": evento_alerta,
        }

    except ClientError:
        logger.exception(
            "Error de DynamoDB al procesar la lectura"
        )
        raise

    except (KeyError, TypeError, ValueError, RuntimeError):
        logger.exception(
            "Error al procesar la lectura o su alerta"
        )
        raise
