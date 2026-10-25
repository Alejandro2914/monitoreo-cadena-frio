
import logging
import os
import time

import boto3
from botocore.exceptions import ClientError

from notificaciones_sns import publicar_notificacion

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

EVENTOS_NOTIFICABLES = {
    "ALERTA_ACTIVADA",
    "TEMPERATURA_RECUPERADA",
}

SEGUNDOS_BLOQUEO = 90


def obtener_tabla():
    nombre_tabla = os.environ["DYNAMODB_TABLE"]

    dynamodb = boto3.resource(
        "dynamodb",
        region_name=os.environ.get("AWS_REGION", "us-east-2"),
    )

    return dynamodb.Table(nombre_tabla)


def reclamar_notificacion(tabla, camara_id, lectura_id):
    """
    Reserva temporalmente una notificacion pendiente.
    Evita que dos ejecuciones la publiquen simultaneamente.
    """
    ahora = int(time.time())
    bloqueo_hasta = ahora + SEGUNDOS_BLOQUEO

    try:
        tabla.update_item(
            Key={
                "camara_id": camara_id,
                "lectura_id": lectura_id,
            },
            UpdateExpression=(
                "SET estado_envio = :en_proceso, "
                "bloqueo_hasta = :bloqueo_hasta"
            ),
            ConditionExpression=(
                "attribute_exists(camara_id) AND "
                "(estado_envio = :pendiente OR "
                "(estado_envio = :en_proceso AND "
                "(attribute_not_exists(bloqueo_hasta) OR "
                "bloqueo_hasta < :ahora)))"
            ),
            ExpressionAttributeValues={
                ":pendiente": "PENDIENTE",
                ":en_proceso": "EN_PROCESO",
                ":bloqueo_hasta": bloqueo_hasta,
                ":ahora": ahora,
            },
        )
        return True

    except ClientError as error:
        codigo = error.response["Error"]["Code"]

        if codigo == "ConditionalCheckFailedException":
            return False

        raise


def marcar_enviada(tabla, camara_id, lectura_id, message_id):
    """
    Registra que SNS acepto la publicacion.
    """
    tabla.update_item(
        Key={
            "camara_id": camara_id,
            "lectura_id": lectura_id,
        },
        UpdateExpression=(
            "SET estado_envio = :enviada, "
            "sns_message_id = :message_id "
            "REMOVE bloqueo_hasta"
        ),
        ConditionExpression="estado_envio = :en_proceso",
        ExpressionAttributeValues={
            ":enviada": "ENVIADA",
            ":en_proceso": "EN_PROCESO",
            ":message_id": message_id,
        },
    )


def liberar_notificacion(tabla, camara_id, lectura_id):
    """
    Devuelve el evento a PENDIENTE si falla el procesamiento.
    """
    tabla.update_item(
        Key={
            "camara_id": camara_id,
            "lectura_id": lectura_id,
        },
        UpdateExpression=(
            "SET estado_envio = :pendiente "
            "REMOVE bloqueo_hasta"
        ),
        ConditionExpression="estado_envio = :en_proceso",
        ExpressionAttributeValues={
            ":pendiente": "PENDIENTE",
            ":en_proceso": "EN_PROCESO",
        },
    )


def procesar_registro(registro):
    """
    Procesa exclusivamente nuevos eventos Outbox.
    """
    if registro.get("eventName") != "INSERT":
        return

    claves = registro.get("dynamodb", {}).get("Keys", {})

    camara_id = claves.get("camara_id", {}).get("S")
    lectura_id = claves.get("lectura_id", {}).get("S")

    if not camara_id or not lectura_id:
        raise ValueError("Registro de DynamoDB sin claves validas")

    if not lectura_id.startswith("NOTIFICACION#"):
        return

    tabla = obtener_tabla()

    respuesta = tabla.get_item(
        Key={
            "camara_id": camara_id,
            "lectura_id": lectura_id,
        },
        ConsistentRead=True,
    )

    notificacion = respuesta.get("Item")

    if not notificacion:
        raise RuntimeError(
            f"No se encontro el evento Outbox: {lectura_id}"
        )

    evento = notificacion.get("evento")

    if evento not in EVENTOS_NOTIFICABLES:
        logger.info("Evento no notificable: %s", evento)
        return

    if not reclamar_notificacion(tabla, camara_id, lectura_id):
        estado = tabla.get_item(
            Key={
                "camara_id": camara_id,
                "lectura_id": lectura_id,
            },
            ConsistentRead=True,
        ).get("Item", {}).get("estado_envio")

        if estado == "ENVIADA":
            logger.info("Notificacion ya enviada: %s", lectura_id)
            return

        raise RuntimeError(
            f"Notificacion ocupada o no disponible: {lectura_id}"
        )

    try:
        lectura = {
            "id_acopio": notificacion["id_acopio"],
            "id_camara": notificacion["id_camara"],
            "temperatura_c": notificacion["temperatura_c"],
            "marca_tiempo": notificacion["marca_tiempo"],
        }

        resultado = publicar_notificacion(
            camara_id,
            lectura,
            evento,
        )

        if not resultado.get("publicada"):
            raise RuntimeError(
                f"SNS no publico el evento: {lectura_id}"
            )

        marcar_enviada(
            tabla,
            camara_id,
            lectura_id,
            resultado["message_id"],
        )

        logger.info(
            "Notificacion procesada: %s, MessageId=%s",
            lectura_id,
            resultado["message_id"],
        )

    except Exception:
        logger.exception(
            "Error al procesar notificacion: %s",
            lectura_id,
        )

        try:
            liberar_notificacion(tabla, camara_id, lectura_id)
        except Exception:
            logger.exception(
                "No se pudo liberar el evento: %s",
                lectura_id,
            )

        raise


def lambda_handler(event, context):
    """
    Punto de entrada para los eventos de DynamoDB Streams.
    """
    registros = event.get("Records", [])

    logger.info(
        "Registros recibidos desde DynamoDB Streams: %s",
        len(registros),
    )

    for registro in registros:
        procesar_registro(registro)

    return {
        "statusCode": 200,
        "registros_recibidos": len(registros),
    }
