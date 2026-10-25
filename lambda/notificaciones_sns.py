
import json
import logging
import os

import boto3

logger = logging.getLogger(__name__)

EVENTOS_NOTIFICABLES = {
    "ALERTA_ACTIVADA",
    "TEMPERATURA_RECUPERADA",
}


def publicar_notificacion(camara_id, lectura, evento):
    """
    Publica una notificacion en Amazon SNS cuando una
    alerta se activa o cuando la temperatura se recupera.
    """

    if evento not in EVENTOS_NOTIFICABLES:
        return {
            "publicada": False,
            "motivo": "Evento no notificable",
        }

    topic_arn = os.environ["SNS_TOPIC_ARN"]

    cliente_sns = boto3.client("sns")

    id_acopio = lectura["id_acopio"]
    id_camara = lectura["id_camara"]
    temperatura = float(lectura["temperatura_c"])
    fecha = lectura["marca_tiempo"]

    if evento == "ALERTA_ACTIVADA":
        asunto = f"AgroLink - Alerta de temperatura {id_acopio}"

        descripcion = (
            "Se detecto una temperatura sostenida "
            "fuera del rango permitido."
        )
    else:
        asunto = f"AgroLink - Temperatura recuperada {id_acopio}"

        descripcion = (
            "La temperatura de la camara regreso "
            "al rango permitido."
        )

    mensaje = {
        "sistema": "AgroLink",
        "evento": evento,
        "centro_acopio": id_acopio,
        "camara": id_camara,
        "camara_id": camara_id,
        "temperatura_c": temperatura,
        "fecha_lectura": fecha,
        "descripcion": descripcion,
    }

    respuesta = cliente_sns.publish(
        TopicArn=topic_arn,
        Subject=asunto[:100],
        Message=json.dumps(
            mensaje,
            ensure_ascii=False,
            indent=2,
        ),
    )

    logger.info(
        "Notificacion SNS publicada. Evento=%s, Camara=%s, MessageId=%s",
        evento,
        camara_id,
        respuesta["MessageId"],
    )

    return {
        "publicada": True,
        "message_id": respuesta["MessageId"],
    }
