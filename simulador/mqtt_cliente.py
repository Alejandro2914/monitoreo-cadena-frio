
import ssl
from pathlib import Path

import paho.mqtt.client as mqtt

from config import (
    ID_ACOPIO,
    ID_CAMARA,
    obtener_cliente_id,
)

BASE_DIR = Path(__file__).resolve().parent.parent
CERT_DIR = BASE_DIR / "certificados"

AWS_IOT_ENDPOINT = "a1mr8cv1qfl1zv-ats.iot.us-east-2.amazonaws.com"

CA_CERT = CERT_DIR / "AmazonRootCA1.pem"


def crear_cliente_mqtt(sensor=None):
    """
    Crea un cliente MQTT autenticado con certificados X.509.

    Si no se especifica un sensor, utiliza el primer dispositivo,
    conservando compatibilidad con los scripts existentes.
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

    # El primer sensor conserva los certificados originales.
    if id_acopio == "ACOPIO01" and id_camara == "CAMARA01" and id_sensor == "SENSOR01":
        certificado = CERT_DIR / "device.pem.crt"
        clave_privada = CERT_DIR / "private.pem.key"
    else:
        carpeta_sensor = CERT_DIR / cliente_id
        certificado = carpeta_sensor / "device.pem.crt"
        clave_privada = carpeta_sensor / "private.pem.key"

    # Verificar los archivos antes de intentar conectarse.
    for archivo in (CA_CERT, certificado, clave_privada):
        if not archivo.is_file():
            raise FileNotFoundError(
                f"Archivo de certificado no encontrado: {archivo}"
            )

    cliente = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=cliente_id,
        protocol=mqtt.MQTTv311,
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

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print("Conexion MQTT exitosa con AWS IoT Core")
        else:
            print(f"Conexion rechazada: {reason_code}")

    def on_disconnect(
        client, userdata, disconnect_flags, reason_code, properties
    ):
        print(f"Desconectado de AWS IoT Core: {reason_code}")

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
