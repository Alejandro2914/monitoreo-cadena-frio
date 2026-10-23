


import json
import random
import time
import uuid
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from config import ID_ACOPIO, ID_CAMARA, TOPICO_LECTURAS, MQTT_QOS
from mqtt_cliente import crear_cliente_mqtt, AWS_IOT_ENDPOINT


# Configuracion del sensor
RANGO_MIN = 2.0
RANGO_MAX = 8.0
INTERVALO_SEGUNDOS = 5


def generar_lectura():
    temperatura = round(random.uniform(1, 12), 2)
    humedad = round(random.uniform(60, 90), 2)

    if RANGO_MIN <= temperatura <= RANGO_MAX:
        estado = "NORMAL"
        tipo_alerta = "ninguna"
    else:
        estado = "FUERA DE RANGO"
        tipo_alerta = "temperatura_fuera_rango"

    return {
        "id_lectura": str(uuid.uuid4()),
        "id_acopio": ID_ACOPIO,
        "id_camara": ID_CAMARA,
        "topico": TOPICO_LECTURAS,
        "temperatura_c": temperatura,
        "humedad_pct": humedad,
        "marca_tiempo": datetime.now(timezone.utc).isoformat(),
        "qos": MQTT_QOS,
        "rango_min_c": RANGO_MIN,
        "rango_max_c": RANGO_MAX,
        "estado_conexion": "conectado",
        "estado_temperatura": estado,
        "tipo_alerta": tipo_alerta
    }


def ejecutar_sensor():
    cliente = crear_cliente_mqtt()
    conectado = False

    def on_connect(client, userdata, flags, reason_code, properties):
        nonlocal conectado

        conectado = reason_code == 0

        if conectado:
            print("Conexion MQTT exitosa con AWS IoT Core")
        else:
            print(f"Conexion MQTT rechazada: {reason_code}")

    def on_disconnect(
        client, userdata, disconnect_flags, reason_code, properties
    ):
        nonlocal conectado

        conectado = False
        print(f"Conexion MQTT finalizada: {reason_code}")

    cliente.on_connect = on_connect
    cliente.on_disconnect = on_disconnect

    print("Conectando el sensor con AWS IoT Core...")

    try:
        cliente.connect(
            AWS_IOT_ENDPOINT,
            port=8883,
            keepalive=60
        )

        cliente.loop_start()

        while True:
            if not conectado:
                print("Esperando conexion MQTT...")
                time.sleep(2)
                continue

            lectura = generar_lectura()

            mensaje_json = json.dumps(
                lectura,
                ensure_ascii=False
            )

            resultado = cliente.publish(
                topic=TOPICO_LECTURAS,
                payload=mensaje_json,
                qos=MQTT_QOS
            )

            if resultado.rc != mqtt.MQTT_ERR_SUCCESS:
                print(
                    f"Error al solicitar publicacion MQTT: "
                    f"{resultado.rc}"
                )
            else:
                try:
                    resultado.wait_for_publish(timeout=10)

                    if resultado.is_published():
                        print("--------------------------------")
                        print("Lectura MQTT confirmada por el broker")
                        print(f"Centro: {lectura['id_acopio']}")
                        print(f"Camara: {lectura['id_camara']}")
                        print(
                            f"Temperatura: "
                            f"{lectura['temperatura_c']} °C"
                        )
                        print(
                            f"Humedad: "
                            f"{lectura['humedad_pct']} %"
                        )
                        print(
                            f"Estado: "
                            f"{lectura['estado_temperatura']}"
                        )
                        print(f"Topico: {TOPICO_LECTURAS}")
                        print(f"ID: {lectura['id_lectura']}")
                    else:
                        print(
                            "Publicacion pendiente de confirmacion MQTT"
                        )

                except (RuntimeError, ValueError) as error:
                    print(f"Error al confirmar publicacion: {error}")

            time.sleep(INTERVALO_SEGUNDOS)

    except KeyboardInterrupt:
        print("\nSimulador detenido por el usuario")

    except (OSError, ValueError) as error:
        print(f"Error de conexion MQTT: {error}")

    finally:
        cliente.disconnect()
        cliente.loop_stop()
        print("Cliente MQTT detenido")


if __name__ == "__main__":
    ejecutar_sensor()
