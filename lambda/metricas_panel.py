
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

REGION = os.environ.get("AWS_REGION", "us-east-2")
NOMBRE_TABLA = os.environ["DYNAMODB_TABLE"]

NAMESPACE = "AgroLink/CadenaFrio"

CAMARAS = [
    f"ACOPIO{numero:02d}#CAMARA01"
    for numero in range(1, 9)
]


def obtener_servicios():
    dynamodb = boto3.resource(
        "dynamodb",
        region_name=REGION,
    )

    cloudwatch = boto3.client(
        "cloudwatch",
        region_name=REGION,
    )

    return dynamodb.Table(NOMBRE_TABLA), cloudwatch


def obtener_ultima_lectura(tabla, camara_id):
    """
    Consulta la ultima lectura por marca temporal.

    Las lecturas utilizan una clave de ordenamiento
    con el formato:

    2026-10-26T02:17:00Z#identificador

    El prefijo 20 permite excluir registros como:
    ESTADO#...
    NOTIFICACION#...
    """

    respuesta = tabla.query(
        KeyConditionExpression=(
            Key("camara_id").eq(camara_id)
            & Key("lectura_id").begins_with("20")
        ),
        ScanIndexForward=False,
        Limit=1,
        ConsistentRead=True,
    )

    elementos = respuesta.get("Items", [])

    if not elementos:
        return None

    return elementos[0]


def publicar_temperaturas(tabla, cloudwatch):
    """
    Publica la ultima temperatura almacenada
    para cada camara en CloudWatch.

    No genera valores ficticios cuando una camara
    no tiene lecturas.
    """

    metricas = []
    resultados = {}

    ahora = datetime.now(timezone.utc)

    for camara_id in CAMARAS:
        lectura = obtener_ultima_lectura(
            tabla,
            camara_id,
        )

        if lectura is None:
            resultados[camara_id] = {
                "estado": "SIN_LECTURAS",
            }

            logger.info(
                "Sin lecturas para %s",
                camara_id,
            )

            continue

        temperatura = lectura.get("temperatura_c")

        if temperatura is None:
            resultados[camara_id] = {
                "estado": "SIN_TEMPERATURA",
            }

            logger.warning(
                "Lectura sin temperatura para %s",
                camara_id,
            )

            continue

        temperatura = float(
            Decimal(str(temperatura))
        )

        metricas.append(
            {
                "MetricName": "UltimaTemperatura",
                "Dimensions": [
                    {
                        "Name": "CamaraId",
                        "Value": camara_id,
                    }
                ],
                "Timestamp": ahora,
                "Value": temperatura,
                "Unit": "None",
            }
        )

        resultados[camara_id] = {
            "estado": "PUBLICADA",
            "temperatura_c": temperatura,
            "lectura_id": lectura["lectura_id"],
            "marca_tiempo": lectura.get(
                "marca_tiempo"
            ),
        }

        logger.info(
            "Ultima temperatura: %s = %.2f C",
            camara_id,
            temperatura,
        )

    if metricas:
        cloudwatch.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=metricas,
        )

        logger.info(
            "Metricas publicadas en CloudWatch: %s",
            len(metricas),
        )

    return resultados


def lambda_handler(event, context):
    """
    Funcion invocada cada minuto por EventBridge.

    Consulta DynamoDB y actualiza las metricas
    personalizadas de temperatura.
    """

    tabla, cloudwatch = obtener_servicios()

    resultados = publicar_temperaturas(
        tabla,
        cloudwatch,
    )

    return {
        "statusCode": 200,
        "namespace": NAMESPACE,
        "camaras_configuradas": len(CAMARAS),
        "metricas_publicadas": sum(
            1
            for resultado in resultados.values()
            if resultado["estado"] == "PUBLICADA"
        ),
        "resultados": resultados,
    }
