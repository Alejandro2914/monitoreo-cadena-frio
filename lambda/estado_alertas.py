
import os

import boto3
from botocore.exceptions import ClientError


CLAVE_ESTADO = "ESTADO#ALERTA_TEMPERATURA"


def obtener_tabla():
    """Obtiene la tabla DynamoDB configurada para Lambda."""
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(os.environ["DYNAMODB_TABLE"])


def obtener_estado(camara_id, tabla=None):
    """Consulta el estado persistente de una camara."""
    if tabla is None:
        tabla = obtener_tabla()

    respuesta = tabla.get_item(
        Key={
            "camara_id": camara_id,
            "lectura_id": CLAVE_ESTADO,
        },
        ConsistentRead=True,
    )

    item = respuesta.get("Item")

    if item is None:
        return None

    return {
        "inicio_anomalia": item.get("inicio_anomalia"),
        "alerta_activa": item.get("alerta_activa", False),
        "ultima_fecha_lectura": item.get("ultima_fecha_lectura"),
        "version": int(item.get("version", 0)),
    }


def guardar_estado(camara_id, nuevo_estado, estado_anterior=None, tabla=None):
    """
    Guarda el estado de alerta con control de concurrencia.

    True: escritura realizada.
    False: otra ejecucion modifico el estado.
    """
    if tabla is None:
        tabla = obtener_tabla()

    clave = {
        "camara_id": camara_id,
        "lectura_id": CLAVE_ESTADO,
    }

    inicio_anomalia = nuevo_estado.get("inicio_anomalia")

    if estado_anterior is None:
        item = {
            **clave,
            "tipo_registro": "ESTADO_ALERTA",
            "alerta_activa": nuevo_estado["alerta_activa"],
            "ultima_fecha_lectura": nuevo_estado["ultima_fecha_lectura"],
            "version": 1,
        }

        if inicio_anomalia is not None:
            item["inicio_anomalia"] = inicio_anomalia

        try:
            tabla.put_item(
                Item=item,
                ConditionExpression=(
                    "attribute_not_exists(camara_id) "
                    "AND attribute_not_exists(lectura_id)"
                ),
            )
            return True

        except ClientError as error:
            if (
                error.response["Error"]["Code"]
                == "ConditionalCheckFailedException"
            ):
                return False
            raise

    version_anterior = estado_anterior["version"]

    expresion = (
        "SET alerta_activa = :activa, "
        "ultima_fecha_lectura = :fecha, "
        "#version = :nueva_version"
    )

    valores = {
        ":activa": nuevo_estado["alerta_activa"],
        ":fecha": nuevo_estado["ultima_fecha_lectura"],
        ":nueva_version": version_anterior + 1,
        ":version_anterior": version_anterior,
    }

    if inicio_anomalia is None:
        expresion += " REMOVE inicio_anomalia"
    else:
        expresion += ", inicio_anomalia = :inicio"
        valores[":inicio"] = inicio_anomalia

    try:
        tabla.update_item(
            Key=clave,
            UpdateExpression=expresion,
            ConditionExpression=(
                "attribute_exists(camara_id) "
                "AND attribute_exists(lectura_id) "
                "AND #version = :version_anterior"
            ),
            ExpressionAttributeNames={
                "#version": "version"
            },
            ExpressionAttributeValues=valores,
        )

        return True

    except ClientError as error:
        if (
            error.response["Error"]["Code"]
            == "ConditionalCheckFailedException"
        ):
            return False
        raise
