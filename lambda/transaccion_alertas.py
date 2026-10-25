
import os
from decimal import Decimal

import boto3
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

from estado_alertas import CLAVE_ESTADO
from eventos_notificacion import (
    EVENTOS_NOTIFICABLES,
    crear_identificador_evento,
)


serializador = TypeSerializer()


def convertir_valores(valores):
    """Convierte los valores al formato de la API DynamoDB."""
    return {
        clave: serializador.serialize(valor)
        for clave, valor in valores.items()
    }


def guardar_estado_y_notificacion(
    camara_id,
    lectura,
    evento,
    nuevo_estado,
    estado_anterior,
    cliente=None,
    nombre_tabla=None,
):
    """
    Actualiza el estado y registra la notificacion
    mediante una unica transaccion de DynamoDB.

    True: transaccion confirmada.
    False: conflicto condicional; se debe recalcular.
    """

    if evento not in EVENTOS_NOTIFICABLES:
        raise ValueError(
            f"El evento no requiere notificacion: {evento}"
        )

    if cliente is None:
        cliente = boto3.client("dynamodb")

    if nombre_tabla is None:
        nombre_tabla = os.environ["DYNAMODB_TABLE"]

    clave_estado = {
        "camara_id": camara_id,
        "lectura_id": CLAVE_ESTADO,
    }

    identificador_evento = crear_identificador_evento(
        lectura["lectura_id"],
        evento,
    )

    notificacion = {
        "camara_id": camara_id,
        "lectura_id": identificador_evento,
        "tipo_registro": "NOTIFICACION",
        "evento": evento,
        "estado_envio": "PENDIENTE",
        "id_lectura_original": lectura["lectura_id"],
        "id_acopio": lectura["id_acopio"],
        "id_camara": lectura["id_camara"],
        "temperatura_c": Decimal(
            str(lectura["temperatura_c"])
        ),
        "marca_tiempo": lectura["marca_tiempo"],
    }

    # Primera creacion del registro de estado.
    if estado_anterior is None:
        item_estado = {
            **clave_estado,
            "tipo_registro": "ESTADO_ALERTA",
            "alerta_activa": nuevo_estado["alerta_activa"],
            "ultima_fecha_lectura": nuevo_estado[
                "ultima_fecha_lectura"
            ],
            "version": 1,
        }

        if nuevo_estado.get("inicio_anomalia") is not None:
            item_estado["inicio_anomalia"] = nuevo_estado[
                "inicio_anomalia"
            ]

        operacion_estado = {
            "Put": {
                "TableName": nombre_tabla,
                "Item": convertir_valores(item_estado),
                "ConditionExpression": (
                    "attribute_not_exists(camara_id)"
                ),
            }
        }

    else:
        valores = {
            ":activa": nuevo_estado["alerta_activa"],
            ":fecha": nuevo_estado["ultima_fecha_lectura"],
            ":version_actual": int(estado_anterior["version"]),
            ":version_nueva": int(estado_anterior["version"]) + 1,
        }

        expresion = (
            "SET alerta_activa = :activa, "
            "ultima_fecha_lectura = :fecha, "
            "#v = :version_nueva"
        )

        inicio = nuevo_estado.get("inicio_anomalia")

        if inicio is None:
            expresion += " REMOVE inicio_anomalia"
        else:
            expresion += ", inicio_anomalia = :inicio"
            valores[":inicio"] = inicio

        operacion_estado = {
            "Update": {
                "TableName": nombre_tabla,
                "Key": convertir_valores(clave_estado),
                "UpdateExpression": expresion,
                "ConditionExpression": (
                    "attribute_exists(camara_id) "
                    "AND #v = :version_actual"
                ),
                "ExpressionAttributeNames": {
                    "#v": "version",
                },
                "ExpressionAttributeValues": convertir_valores(
                    valores
                ),
            }
        }

    operacion_notificacion = {
        "Put": {
            "TableName": nombre_tabla,
            "Item": convertir_valores(notificacion),
            "ConditionExpression": (
                "attribute_not_exists(camara_id)"
            ),
        }
    }

    try:
        cliente.transact_write_items(
            TransactItems=[
                operacion_estado,
                operacion_notificacion,
            ]
        )

        return True

    except ClientError as error:
        codigo = error.response["Error"]["Code"]

        if codigo == "TransactionCanceledException":
            motivos = error.response.get(
                "CancellationReasons", []
            )

            # Un conflicto de version requiere recalcular
            # el estado antes de volver a intentarlo.
            if motivos and all(
                motivo.get("Code") in (
                    "None",
                    "ConditionalCheckFailed",
                )
                for motivo in motivos
            ) and any(
                motivo.get("Code") == "ConditionalCheckFailed"
                for motivo in motivos
            ):
                return False

        # Otros errores deben propagarse:
        # permisos, capacidad, validacion o fallos AWS.
        raise
