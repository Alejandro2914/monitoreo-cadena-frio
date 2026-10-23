
import ssl
from pathlib import Path
import paho.mqtt.client as mqtt

from config import ID_ACOPIO, ID_CAMARA, MQTT_QOS

# Carpeta principal del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# Ubicación local de los certificados
CERT_DIR = BASE_DIR / "certificados"

# Dirección del broker de AWS
AWS_IOT_ENDPOINT = "a1mr8cv1qfl1zv-ats.iot.us-east-2.amazonaws.com"

# Rutas de los certificados
CA_CERT = CERT_DIR / "AmazonRootCA1.pem"
DEVICE_CERT = CERT_DIR / "device.pem.crt"
PRIVATE_KEY = CERT_DIR / "private.pem.key"


def crear_cliente_mqtt():
    # Cada sensor tendrá su propia identidad MQTT
    cliente_id = f"agrolink-{ID_ACOPIO.lower()}-{ID_CAMARA.lower()}-sensor01"


    cliente = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=cliente_id,
        protocol=mqtt.MQTTv311
    )

    # Configuración de la conexión segura TLS
    cliente.tls_set(
        ca_certs=str(CA_CERT),
        certfile=str(DEVICE_CERT),
        keyfile=str(PRIVATE_KEY),
        tls_version=ssl.PROTOCOL_TLS_CLIENT
    )

    return cliente

def probar_conexion():
    cliente = crear_cliente_mqtt()

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print("Conexión MQTT exitosa con AWS IoT Core")
        else:
            print(f"Conexión rechazada: {reason_code}")

    def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
        print(f"Desconectado de AWS IoT Core: {reason_code}")

    cliente.on_connect = on_connect
    cliente.on_disconnect = on_disconnect

    print("Intentando conectar con AWS IoT Core...")

    try:
        cliente.connect(AWS_IOT_ENDPOINT, port=8883, keepalive=60)
        cliente.loop_forever()
    except (OSError, ssl.SSLError) as error:
        print(f"Error de conexión: {error}")


if __name__ == "__main__":
    probar_conexion()

