
import json
import logging
import os
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CLAVE_ESTADO = "ESTADO#CONEXION"

UMBRAL_SEGUNDOS = int(
    os.environ.get("UMBRAL_INACTIVIDAD_SEGUNDOS", "120")
)

CAMARAS = [
    f"ACOPIO{numero:02d}#CAMARA01"
    for numero in range(1, 9)
]

EVENTOS_CONEXION = {
    "SENSOR_DESCONECTADO",
    "SENSOR_RECONECTADO",
}


def obtener_servicios():
    region = os.environ.get("AWS_REGION", "us-east-2")

    dynamodb = boto3.resource(
        "dynamodb",
        region_name=region,
    )

    sns = boto3.client(
        "sns",
        region_name=region,
    )

    tabla = dynamodb.Table(os.environ["DYNAMODB_TABLE"])

    return tabla, sns


def obtener_estado(tabla, camara_id):
    respuesta = tabla.get_item(
        Key={
            "camara_id": camara_id,
            "lectura_id": CLAVE_ESTADO,
        },
        ConsistentRead=True,
    )

    return respuesta.get("Item")


def determinar_estado(registro, ahora):
    ultima = int(registro["ultima_recepcion_epoch"])
    segundos = max(0, ahora - ultima)

    estado = (
        "DESCONECTADO"
        if segundos > UMBRAL_SEGUNDOS
        else "CONECTADO"
    )

    return estado, segundos


def actualizar_estado(
    tabla,
    camara_id,
    registro,
    nuevo_estado,
    ahora,
):
    anterior = registro.get("estado_supervision")
    ultima = registro["ultima_recepcion_epoch"]

    valores = {
        ":nuevo": nuevo_estado,
        ":ultima": ultima,
        ":ahora": ahora,
    }

    condicion = (
        "ultima_recepcion_epoch = :ultima "
        "AND attribute_not_exists(notificacion_pendiente)"
    )

    if anterior is None:
        condicion += (
            " AND attribute_not_exists(estado_supervision)"
        )
    else:
        condicion += " AND estado_supervision = :anterior"
        valores[":anterior"] = anterior

    expresion = (
        "SET estado_supervision = :nuevo, "
        "ultima_supervision_epoch = :ahora"
    )

    if anterior is not None:
        evento = (
            "SENSOR_DESCONECTADO"
            if nuevo_estado == "DESCONECTADO"
            else "SENSOR_RECONECTADO"
        )

        expresion += ", notificacion_pendiente = :evento"
        valores[":evento"] = evento

    try:
        tabla.update_item(
            Key={
                "camara_id": camara_id,
                "lectura_id": CLAVE_ESTADO,
            },
            UpdateExpression=expresion,
            ConditionExpression=condicion,
            ExpressionAttributeValues=valores,
        )

        return True

    except ClientError as error:
        if (
            error.response["Error"]["Code"]
            == "ConditionalCheckFailedException"
        ):
            logger.warning(
                "Actualizacion rechazada por concurrencia "
                "o notificacion pendiente: %s",
                camara_id,
            )
            return False

        raise


def enviar_notificacion(
    tabla,
    sns,
    camara_id,
    registro,
    ahora,
):
    evento = registro.get("notificacion_pendiente")

    if evento not in EVENTOS_CONEXION:
        return False

    id_acopio, id_camara = camara_id.split("#", 1)

    asunto = (
        f"AgroLink - Sensor desconectado {id_acopio}"
        if evento == "SENSOR_DESCONECTADO"
        else f"AgroLink - Sensor reconectado {id_acopio}"
    )

    mensaje = {
        "sistema": "AgroLink",
        "evento": evento,
        "centro_acopio": id_acopio,
        "camara": id_camara,
        "ultima_recepcion_utc": registro.get(
            "ultima_recepcion_utc"
        ),
        "fecha_supervision_utc": datetime.fromtimestamp(
            ahora,
            tz=timezone.utc,
        ).isoformat(),
        "umbral_segundos": UMBRAL_SEGUNDOS,
    }

    respuesta = sns.publish(
        TopicArn=os.environ["SNS_TOPIC_ARN"],
        Subject=asunto,
        Message=json.dumps(
            mensaje,
            ensure_ascii=False,
            indent=2,
        ),
    )

    tabla.update_item(
        Key={
            "camara_id": camara_id,
            "lectura_id": CLAVE_ESTADO,
        },
        UpdateExpression=(
            "SET ultimo_sns_message_id = :mensaje "
            "REMOVE notificacion_pendiente"
        ),
        ConditionExpression=(
            "notificacion_pendiente = :evento"
        ),
        ExpressionAttributeValues={
            ":mensaje": respuesta["MessageId"],
            ":evento": evento,
        },
    )

    logger.info(
        "Notificacion de conexion enviada: %s, evento=%s",
        camara_id,
        evento,
    )

    return True


def supervisar_camara(tabla, sns, camara_id, ahora):
    registro = obtener_estado(tabla, camara_id)

    if not registro:
        logger.info(
            "Camara sin actividad registrada: %s",
            camara_id,
        )
        return "SIN_DATOS"

    if "ultima_recepcion_epoch" not in registro:
        return "SIN_DATOS"

    # Procesar primero cualquier notificacion anterior.
    if registro.get("notificacion_pendiente"):
        enviar_notificacion(
            tabla,
            sns,
            camara_id,
            registro,
            ahora,
        )

        registro = obtener_estado(tabla, camara_id)

    nuevo_estado, segundos = determinar_estado(
        registro,
        ahora,
    )

    anterior = registro.get("estado_supervision")

    if anterior != nuevo_estado:
        actualizado = actualizar_estado(
            tabla,
            camara_id,
            registro,
            nuevo_estado,
            ahora,
        )

        if not actualizado:
            return "CONFLICTO"

        registro = obtener_estado(tabla, camara_id)

        if registro.get("notificacion_pendiente"):
            enviar_notificacion(
                tabla,
                sns,
                camara_id,
                registro,
                ahora,
            )

    logger.info(
        "Supervision: %s, estado=%s, sin lecturas=%ss",
        camara_id,
        nuevo_estado,
        segundos,
    )

    return nuevo_estado


def lambda_handler(event, context):
    tabla, sns = obtener_servicios()
    ahora = int(time.time())

    resultados = {}

    for camara_id in CAMARAS:
        try:
            resultados[camara_id] = supervisar_camara(
                tabla,
                sns,
                camara_id,
                ahora,
            )
        except Exception:
            logger.exception(
                "Error supervisando %s",
                camara_id,
            )
            resultados[camara_id] = "ERROR"

    if "ERROR" in resultados.values():
        raise RuntimeError(
            "Una o mas camaras no pudieron supervisarse"
        )

    return {
        "statusCode": 200,
        "umbral_segundos": UMBRAL_SEGUNDOS,
        "resultados": resultados,
    }
