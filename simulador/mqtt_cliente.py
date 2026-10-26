
import json
import ssl
from pathlib import Path

import paho.mqtt.client as mqtt

from config import (
    ID_ACOPIO,
    ID_CAMARA,
    MQTT_QOS,
    obtener_cliente_id,
)

BASE_DIR = Path(__file__).resolve().parent.parent
CERT_DIR = BASE_DIR / "certificados"

AWS_IOT_ENDPOINT = (
    "a1mr8cv1qfl1zv-ats.iot.us-east-2.amazonaws.com"
)

CA_CERT = CERT_DIR / "AmazonRootCA1.pem"


def obtener_topico_estado(id_acopio, id_camara):
    """
    Devuelve el topico MQTT de estado de una camara.
    """
    return f"agrolink/{id_acopio}/{id_camara}/estado"


def crear_cliente_mqtt(sensor=None):
    """
    Crea un cliente MQTT autenticado con certificados X.509.

    Incluye Last Will and Testament (LWT) para que
    AWS IoT Core publique un mensaje cuando detecte
    una desconexion inesperada del sensor.
    """
    if sensor is None:
        sensor = {
            "id_acopio": ID_ACOPIO,
            "id_camara": ID_CAMARA,
            "id_sensor": "SENSOR01",
        }

    id_acopio = sensor["id_acopio"]
    id_camara = sensor["id_camara"]
    id_sensor = sensor["id_sensor"]

    cliente_id = obtener_cliente_id(
        id_acopio,
        id_camara,
        id_sensor,
    )

    if (
        id_acopio == "ACOPIO01"
        and id_camara == "CAMARA01"
        and id_sensor == "SENSOR01"
    ):
        certificado = CERT_DIR / "device.pem.crt"
        clave_privada = CERT_DIR / "private.pem.key"
    else:
        carpeta_sensor = CERT_DIR / cliente_id
        certificado = carpeta_sensor / "device.pem.crt"
        clave_privada = carpeta_sensor / "private.pem.key"

    for archivo in (
        CA_CERT,
        certificado,
        clave_privada,
    ):
        if not archivo.is_file():
            raise FileNotFoundError(
                f"Archivo de certificado no encontrado: {archivo}"
            )

    cliente = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=cliente_id,
        protocol=mqtt.MQTTv311,
    )

    # Mensaje que publicara AWS IoT Core si el sensor
    # desaparece sin enviar MQTT DISCONNECT.
    topico_estado = obtener_topico_estado(
        id_acopio,
        id_camara,
    )

    mensaje_lwt = {
        "sistema": "AgroLink",
        "evento": "DESCONEXION_INESPERADA",
        "id_acopio": id_acopio,
        "id_camara": id_camara,
        "id_sensor": id_sensor,
        "cliente_id": cliente_id,
        "estado_conexion": "desconectado",
        "origen": "MQTT_LAST_WILL",
    }

    cliente.will_set(
        topic=topico_estado,
        payload=json.dumps(
            mensaje_lwt,
            ensure_ascii=False,
        ),
        qos=MQTT_QOS,
        retain=False,
    )

    cliente.tls_set(
        ca_certs=str(CA_CERT),
        certfile=str(certificado),
        keyfile=str(clave_privada),
        tls_version=ssl.PROTOCOL_TLS_CLIENT,
    )

    return cliente


def probar_conexion(sensor=None):
    cliente = crear_cliente_mqtt(sensor)

    def on_connect(
        client,
        userdata,
        flags,
        reason_code,
        properties,
    ):
        if reason_code == 0:
            print("Conexion MQTT exitosa con AWS IoT Core")
            print("Mensaje LWT configurado")
        else:
            print(f"Conexion rechazada: {reason_code}")

    def on_disconnect(
        client,
        userdata,
        disconnect_flags,
        reason_code,
        properties,
    ):
        print(
            f"Desconectado de AWS IoT Core: {reason_code}"
        )

    cliente.on_connect = on_connect
    cliente.on_disconnect = on_disconnect

    print("Intentando conectar con AWS IoT Core...")

    try:
        cliente.connect(
            AWS_IOT_ENDPOINT,
            port=8883,
            keepalive=60,
        )

        cliente.loop_forever()

    except (OSError, ssl.SSLError) as error:
        print(f"Error de conexion: {error}")


if __name__ == "__main__":
    probar_conexion()
