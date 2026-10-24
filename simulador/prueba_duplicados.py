
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
            print("Conexion MQTT establecida correctamente")
        else:
            print(f"Error de conexion MQTT: {reason_code}")

    cliente.on_connect = on_connect

    # Una identidad unica para ambas publicaciones
    id_lectura = str(uuid.uuid4())
    marca_tiempo = datetime.now(timezone.utc).isoformat()

    lectura_original = {
        "id_lectura": id_lectura,
        "id_acopio": ID_ACOPIO,
        "id_camara": ID_CAMARA,
        "topico": TOPICO_LECTURAS,
        "temperatura_c": 5.5,
        "humedad_pct": 75.0,
        "marca_tiempo": marca_tiempo,
        "qos": MQTT_QOS,
        "rango_min_c": 2.0,
        "rango_max_c": 8.0,
        "estado_conexion": "conectado",
        "estado_temperatura": "NORMAL",
        "tipo_alerta": "ninguna",
        "prueba_deduplicacion": True
    }

    # Copia con la MISMA identidad, pero diferente temperatura
    lectura_duplicada = lectura_original.copy()
    lectura_duplicada["temperatura_c"] = 11.2
    lectura_duplicada["estado_temperatura"] = "FUERA DE RANGO"
    lectura_duplicada["tipo_alerta"] = "temperatura_fuera_rango"

    try:
        print("Conectando con AWS IoT Core...")
        cliente.connect(AWS_IOT_ENDPOINT, port=8883, keepalive=60)
        cliente.loop_start()

        for _ in range(20):
            if cliente.is_connected():
                break
            time.sleep(0.5)

        if not cliente.is_connected():
            print("No se pudo establecer la conexion MQTT")
            return

        print("Conexion MQTT exitosa")
        print(f"UUID compartido: {id_lectura}")
        print(f"Fecha compartida: {marca_tiempo}")
        print(f"Camara: {ID_ACOPIO}#{ID_CAMARA}")

        mensajes = [
            ("ORIGINAL", lectura_original),
            ("DUPLICADA", lectura_duplicada)
        ]

        for numero, (nombre, lectura) in enumerate(mensajes, start=1):
            payload = json.dumps(lectura, ensure_ascii=False)

            print("-----------------------------------")
            print(f"Publicacion {numero}: {nombre}")
            print(f"Temperatura: {lectura['temperatura_c']} C")

            resultado = cliente.publish(
                topic=TOPICO_LECTURAS,
                payload=payload,
                qos=MQTT_QOS
            )

            if resultado.rc != mqtt.MQTT_ERR_SUCCESS:
                print(f"Error MQTT: {resultado.rc}")
                return

            resultado.wait_for_publish(timeout=10)

            if not resultado.is_published():
                print("No se recibio confirmacion MQTT")
                return

            print("Publicacion confirmada por el broker")

            # Permitir que AWS procese la primera lectura
            # antes de enviar la segunda
            time.sleep(3)

        print("-----------------------------------")
        print("Prueba MQTT finalizada")
        print("Verificar el resultado en CloudWatch y DynamoDB")
        print("La temperatura almacenada debe permanecer en 5.5 C")

    except (OSError, RuntimeError, ValueError) as error:
        print(f"Error durante la prueba: {error}")

    finally:
        if cliente.is_connected():
            cliente.disconnect()
        cliente.loop_stop()


if __name__ == "__main__":
    ejecutar_prueba()
