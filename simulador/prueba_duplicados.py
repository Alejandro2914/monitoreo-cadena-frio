
import json
import time
import uuid
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from config import ID_ACOPIO, ID_CAMARA, TOPICO_LECTURAS, MQTT_QOS
from mqtt_cliente import crear_cliente_mqtt, AWS_IOT_ENDPOINT


def ejecutar_prueba():
    cliente = crear_cliente_mqtt()

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print("Conexion MQTT establecida")
        else:
            print(f"Conexion rechazada: {reason_code}")

    cliente.on_connect = on_connect

    # Se genera UNA sola lectura, con un UUID y fecha fijos.
    lectura = {
        "id_lectura": str(uuid.uuid4()),
        "id_acopio": ID_ACOPIO,
        "id_camara": ID_CAMARA,
        "topico": TOPICO_LECTURAS,
        "temperatura_c": 5.5,
        "humedad_pct": 75.0,
        "marca_tiempo": datetime.now(timezone.utc).isoformat(),
        "qos": MQTT_QOS,
        "rango_min_c": 2.0,
        "rango_max_c": 8.0,
        "estado_conexion": "conectado",
        "estado_temperatura": "NORMAL",
        "tipo_alerta": "ninguna",
        "prueba_duplicado": True
    }

    payload = json.dumps(lectura, ensure_ascii=False)

    try:
        cliente.connect(AWS_IOT_ENDPOINT, port=8883, keepalive=60)
        cliente.loop_start()

        # Esperar a que se establezca la conexion MQTT.
        for _ in range(20):
            if cliente.is_connected():
                break
            time.sleep(0.5)

        if not cliente.is_connected():
            print("No se pudo establecer la conexion MQTT")
            return

        print(f"ID original: {lectura['id_lectura']}")
        print(f"Fecha original: {lectura['marca_tiempo']}")

        # Publicar dos veces el MISMO mensaje.
        for numero in (1, 2):
            resultado = cliente.publish(
                topic=TOPICO_LECTURAS,
                payload=payload,
                qos=MQTT_QOS
            )

            if resultado.rc != mqtt.MQTT_ERR_SUCCESS:
                print(f"Publicacion {numero}: error {resultado.rc}")
                return

            resultado.wait_for_publish(timeout=10)

            if resultado.is_published():
                print(f"Publicacion {numero}: confirmada por MQTT")
            else:
                print(f"Publicacion {numero}: sin confirmacion")
                return

            time.sleep(2)

        print("Prueba terminada: mismo UUID y fecha enviados dos veces")

    except (OSError, RuntimeError, ValueError) as error:
        print(f"Error durante la prueba: {error}")

    finally:
        cliente.disconnect()
        cliente.loop_stop()


if __name__ == "__main__":
    ejecutar_prueba()
