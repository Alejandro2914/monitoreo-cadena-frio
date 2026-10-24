

import json
import logging
import os
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError


# Configuracion de registros de ejecucion
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Conexion con DynamoDB
dynamodb = boto3.resource("dynamodb")

# Nombre de la tabla configurado mediante variable de entorno
TABLA_DYNAMODB = os.environ["DYNAMODB_TABLE"]
tabla = dynamodb.Table(TABLA_DYNAMODB)


def lambda_handler(event, context):
    """
    Procesa una lectura MQTT y la almacena en DynamoDB.

    Si la lectura ya existe, evita sobrescribirla mediante
    una escritura condicional.
    """

    try:
        # Obtener los datos de identificacion de la lectura
        id_acopio = event["id_acopio"]
        id_camara = event["id_camara"]
        id_lectura = event["id_lectura"]
        marca_tiempo = event["marca_tiempo"]

        # Construir las claves de DynamoDB
        camara_id = f"{id_acopio}#{id_camara}"
        lectura_id = f"{marca_tiempo}#{id_lectura}"

        # Convertir los valores numericos a Decimal
        # porque DynamoDB no acepta float directamente
        lectura = json.loads(
            json.dumps(event),
            parse_float=Decimal,
            parse_int=Decimal
        )

        # Agregar las claves necesarias para DynamoDB
        lectura["camara_id"] = camara_id
        lectura["lectura_id"] = lectura_id

        # Guardar solo si no existe un registro con esta clave
        tabla.put_item(
            Item=lectura,
            ConditionExpression=(
                "attribute_not_exists(camara_id) "
                "AND attribute_not_exists(lectura_id)"
            )
        )

        logger.info(
            "Lectura almacenada correctamente: %s",
            lectura_id
        )

        return {
            "statusCode": 200,
            "resultado": "almacenada",
            "camara_id": camara_id,
            "lectura_id": lectura_id
        }

    except ClientError as error:
        codigo_error = error.response["Error"]["Code"]

        if codigo_error == "ConditionalCheckFailedException":
            logger.info(
                "Lectura duplicada detectada. No se sobrescribio."
            )

            return {
                "statusCode": 200,
                "resultado": "duplicada"
            }

        logger.exception(
            "Error al almacenar la lectura en DynamoDB"
        )
        raise

    except (KeyError, TypeError, ValueError):
        logger.exception(
            "La lectura contiene datos invalidos o incompletos"
        )
        raise
