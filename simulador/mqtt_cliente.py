
import ssl
from pathlib import Path
import paho.mqtt.client as mqtt

from config import ID_ACOPIO, ID_CAMARA, MQTT_QOS

# Carpeta principal del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# Ubicación local de los certificados
CERT_DIR = BASE_DIR / "certificados"

# Dirección del broker de AWS
AWS_IOT_ENDPOINT = ""

# Rutas de los certificados
CA_CERT = CERT_DIR / "AmazonRootCA1.pem"
DEVICE_CERT = CERT_DIR / "device.pem.crt"
PRIVATE_KEY = CERT_DIR / "private.pem.key"


def crear_cliente_mqtt():
    # Cada sensor tendrá su propia identidad MQTT
    cliente_id = f"{ID_ACOPIO}-{ID_CAMARA}"

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
