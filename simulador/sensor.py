
import json
import random
import time
import uuid
from datetime import datetime, timezone
from threading import Event

import paho.mqtt.client as mqtt

from config import ID_ACOPIO, ID_CAMARA, TOPICO_LECTURAS, MQTT_QOS
from mqtt_cliente import crear_cliente_mqtt, AWS_IOT_ENDPOINT
from buffer_offline import (
    guardar_lectura,
    contar_pendientes,
    inicializar_buffer,
)
from reenvio_pendientes import reenviar_pendientes


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
        "tipo_alerta": tipo_alerta,
    }


def ejecutar_sensor():
    inicializar_buffer()

    cliente = crear_cliente_mqtt()
    conexion_activa = Event()

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            conexion_activa.set()
            print("Conexion MQTT establecida con AWS IoT Core")
        else:
            conexion_activa.clear()
            print(f"Conexion MQTT rechazada: {reason_code}")

    def on_disconnect(
        client, userdata, disconnect_flags, reason_code, properties
    ):
        conexion_activa.clear()
        print(f"Conexion MQTT interrumpida: {reason_code}")

    cliente.on_connect = on_connect
    cliente.on_disconnect = on_disconnect

    # Paho intentara reconectar despues de una interrupcion.
    cliente.reconnect_delay_set(min_delay=1, max_delay=30)

    try:
        print("Iniciando sensor AgroLink...")
        print(f"Centro: {ID_ACOPIO}")
        print(f"Camara: {ID_CAMARA}")

        # connect_async permite iniciar incluso sin internet.
        cliente.connect_async(
            AWS_IOT_ENDPOINT,
            port=8883,
            keepalive=60,
        )
        cliente.loop_start()

        while True:
            # Primero guardar la lectura en SQLite.
            lectura = generar_lectura()

            if not conexion_activa.is_set():
                lectura["estado_conexion"] = "desconectado"

            guardar_lectura(lectura)

            print("--------------------------------")
            print(f"Lectura generada: {lectura['id_lectura']}")
            print(f"Temperatura: {lectura['temperatura_c']} C")
            print(f"Centro: {ID_ACOPIO}")
            print(f"Pendientes: {contar_pendientes(ID_ACOPIO)}")

            if conexion_activa.is_set() and cliente.is_connected():
                # Reenviar pendientes, incluyendo la lectura nueva.
                try:
                    reenviar_pendientes(
                        cliente,
                        id_acopio=ID_ACOPIO,
                        limite=100,
                    )
                except Exception as error:
                    print(f"Error durante el reenvio: {error}")
            else:
                print("Sin conexion. Lectura conservada en SQLite.")

            time.sleep(INTERVALO_SEGUNDOS)

    except KeyboardInterrupt:
        print("\nSimulador detenido por el usuario")

    finally:
        conexion_activa.clear()
        if cliente.is_connected():
            cliente.disconnect()
        cliente.loop_stop()

        print(
            f"Lecturas que permanecen en SQLite: "
            f"{contar_pendientes(ID_ACOPIO)}"
        )
        print("Simulador finalizado")


if __name__ == "__main__":
    ejecutar_sensor()
