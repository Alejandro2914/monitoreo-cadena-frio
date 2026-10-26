
import logging
import time
from datetime import datetime, timezone

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

CLAVE_ACTIVIDAD = "ESTADO#CONEXION"


def clave_actividad(camara_id):
    """
    Construye la clave del registro de actividad
    de una camara.
    """
    return {
        "camara_id": camara_id,
        "lectura_id": CLAVE_ACTIVIDAD,
    }


def registrar_actividad(tabla, camara_id, ahora_epoch=None):
    """
    Registra la ultima comunicacion recibida por AWS.

    Usa la hora de recepcion en AWS y no la marca de tiempo
    original de la lectura, porque esta puede provenir
    del buffer offline.

    No modifica estado_conexion: ese atributo pertenece
    exclusivamente al supervisor de sensores.
    """
    if ahora_epoch is None:
        ahora_epoch = int(time.time())

    ahora_epoch = int(ahora_epoch)

    fecha_recepcion = datetime.fromtimestamp(
        ahora_epoch,
        tz=timezone.utc,
    ).isoformat()

    try:
        respuesta = tabla.update_item(
            Key=clave_actividad(camara_id),
            UpdateExpression=(
                "SET ultima_recepcion_epoch = :ahora, "
                "ultima_recepcion_utc = :fecha, "
                "tipo_registro = :tipo"
            ),
            ConditionExpression=(
                "attribute_not_exists(ultima_recepcion_epoch) "
                "OR ultima_recepcion_epoch <= :ahora"
            ),
            ExpressionAttributeValues={
                ":ahora": ahora_epoch,
                ":fecha": fecha_recepcion,
                ":tipo": "ESTADO_CONEXION",
            },
            ReturnValues="ALL_OLD",
        )

        logger.info(
            "Actividad recibida: camara=%s, fecha=%s",
            camara_id,
            fecha_recepcion,
        )

        return respuesta.get("Attributes", {})

    except ClientError as error:
        codigo = error.response["Error"]["Code"]

        if codigo == "ConditionalCheckFailedException":
            logger.info(
                "Actualizacion antigua de actividad ignorada: %s",
                camara_id,
            )
            return None

        raise
