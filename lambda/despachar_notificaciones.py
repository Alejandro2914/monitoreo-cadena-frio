

import logging
import os
import time
import uuid

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


def reclamar_notificacion(
    tabla,
    camara_id,
    lectura_id,
    token_bloqueo,
):
    """
    Reclama la notificacion mediante un token unico.
    Permite recuperar bloqueos vencidos.
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
                "bloqueo_hasta = :bloqueo_hasta, "
                "token_bloqueo = :token"
            ),
            ConditionExpression=(
                "attribute_exists(camara_id) AND "
                "attribute_exists(lectura_id) AND "
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
                ":token": token_bloqueo,
            },
        )
        return True

    except ClientError as error:
        codigo = error.response["Error"]["Code"]

        if codigo == "ConditionalCheckFailedException":
            return False

        raise


def marcar_enviada(
    tabla,
    camara_id,
    lectura_id,
    message_id,
    token_bloqueo,
):
    """
    Marca ENVIADA solo si el bloqueo pertenece
    a esta ejecucion.
    """
    tabla.update_item(
        Key={
            "camara_id": camara_id,
            "lectura_id": lectura_id,
        },
        UpdateExpression=(
            "SET estado_envio = :enviada, "
            "sns_message_id = :message_id "
            "REMOVE bloqueo_hasta, token_bloqueo"
        ),
        ConditionExpression=(
            "estado_envio = :en_proceso AND "
            "token_bloqueo = :token"
        ),
        ExpressionAttributeValues={
            ":enviada": "ENVIADA",
            ":en_proceso": "EN_PROCESO",
            ":message_id": message_id,
            ":token": token_bloqueo,
        },
    )


def liberar_notificacion(
    tabla,
    camara_id,
    lectura_id,
    token_bloqueo,
):
    """
    Libera el evento solo si pertenece
    a la ejecucion actual.
    """
    tabla.update_item(
        Key={
            "camara_id": camara_id,
            "lectura_id": lectura_id,
        },
        UpdateExpression=(
            "SET estado_envio = :pendiente "
            "REMOVE bloqueo_hasta, token_bloqueo"
        ),
        ConditionExpression=(
            "estado_envio = :en_proceso AND "
            "token_bloqueo = :token"
        ),
        ExpressionAttributeValues={
            ":pendiente": "PENDIENTE",
            ":en_proceso": "EN_PROCESO",
            ":token": token_bloqueo,
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
        raise ValueError(
            "Registro de DynamoDB sin claves validas"
        )

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
        logger.info(
            "Evento no notificable: %s",
            evento,
        )
        return

    token_bloqueo = str(uuid.uuid4())

    if not reclamar_notificacion(
        tabla,
        camara_id,
        lectura_id,
        token_bloqueo,
    ):
        estado = tabla.get_item(
            Key={
                "camara_id": camara_id,
                "lectura_id": lectura_id,
            },
            ConsistentRead=True,
        ).get("Item", {}).get("estado_envio")

        if estado == "ENVIADA":
            logger.info(
                "Notificacion ya enviada: %s",
                lectura_id,
            )
            return

        raise RuntimeError(
            f"Notificacion ocupada o no disponible: {lectura_id}"
        )

    publicacion_confirmada = False

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

        publicacion_confirmada = True

        marcar_enviada(
            tabla,
            camara_id,
            lectura_id,
            resultado["message_id"],
            token_bloqueo,
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

        if not publicacion_confirmada:
            try:
                liberar_notificacion(
                    tabla,
                    camara_id,
                    lectura_id,
                    token_bloqueo,
                )
            except Exception:
                logger.exception(
                    "No se pudo liberar el evento: %s",
                    lectura_id,
                )
        else:
            logger.error(
                "SNS acepto la publicacion, pero no "
                "se confirmo el estado ENVIADA. "
                "Evento=%s. Requiere revision.",
                lectura_id,
            )

        raise


def lambda_handler(event, context):
    """
    Punto de entrada para DynamoDB Streams.
    """
    registros = event.get("Records", [])

    logger.info(
        "Registros recibidos: %s",
        len(registros),
    )

    for registro in registros:
        procesar_registro(registro)

    return {
        "statusCode": 200,
        "registros_recibidos": len(registros),
    }
