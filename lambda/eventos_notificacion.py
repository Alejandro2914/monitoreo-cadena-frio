
from botocore.exceptions import ClientError


EVENTOS_NOTIFICABLES = {
    "ALERTA_ACTIVADA",
    "TEMPERATURA_RECUPERADA",
}


def crear_identificador_evento(lectura_id, evento):
    """Construye una clave unica para cada evento."""
    return f"NOTIFICACION#{lectura_id}#{evento}"


def registrar_evento(
    tabla,
    camara_id,
    lectura,
    evento,
):
    """
    Guarda una notificacion pendiente en DynamoDB.

    Si el evento ya existe, no lo sobrescribe.
    """
    if evento not in EVENTOS_NOTIFICABLES:
        return None

    lectura_id = lectura["lectura_id"]
    identificador = crear_identificador_evento(
        lectura_id,
        evento,
    )

    item = {
        "camara_id": camara_id,
        "lectura_id": identificador,
        "tipo_registro": "NOTIFICACION",
        "evento": evento,
        "estado_envio": "PENDIENTE",
        "id_lectura_original": lectura_id,
        "id_acopio": lectura["id_acopio"],
        "id_camara": lectura["id_camara"],
        "temperatura_c": lectura["temperatura_c"],
        "marca_tiempo": lectura["marca_tiempo"],
    }

    try:
        tabla.put_item(
            Item=item,
            ConditionExpression=(
                "attribute_not_exists(camara_id) "
                "AND attribute_not_exists(lectura_id)"
            ),
        )

        return identificador

    except ClientError as error:
        if (
            error.response["Error"]["Code"]
            == "ConditionalCheckFailedException"
        ):
            return identificador

        raise
