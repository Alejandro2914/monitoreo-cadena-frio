
import json
import time
import uuid
from datetime import datetime, timezone

from config import MQTT_QOS
from mqtt_cliente import crear_cliente_mqtt, AWS_IOT_ENDPOINT


def main():
    sensor = {
        "id_acopio": "ACOPIO01",
        "id_camara": "CAMARA01",
        "id_sensor": "SENSOR01",
    }

    cliente = crear_cliente_mqtt(sensor)

    topico_propio = "agrolink/ACOPIO01/CAMARA01/lecturas"
    topico_ajeno = "agrolink/ACOPIO02/CAMARA01/lecturas"

    conexion = False

    def on_connect(client, userdata, flags, reason_code, properties):
        nonlocal conexion

        conexion = reason_code == 0

        print(
            "Conexion MQTT:",
            "ACEPTADA" if conexion else f"RECHAZADA: {reason_code}",
        )

    def on_disconnect(
        client,
        userdata,
        disconnect_flags,
        reason_code,
        properties,
    ):
        nonlocal conexion
        conexion = False
        print(f"Conexion finalizada: {reason_code}")

    cliente.on_connect = on_connect
    cliente.on_disconnect = on_disconnect

    identificador = str(uuid.uuid4())

    lectura = {
        "id_lectura": identificador,
        "id_acopio": "ACOPIO01",
        "id_camara": "CAMARA01",
        "temperatura_c": 5.0,
        "humedad_pct": 70.0,
        "marca_tiempo": datetime.now(timezone.utc).isoformat(),
        "prueba_seguridad": True,
    }

    try:
        cliente.connect(
            AWS_IOT_ENDPOINT,
            port=8883,
            keepalive=60,
        )

        cliente.loop_start()

        for _ in range(20):
            if conexion:
                break
            time.sleep(0.25)

        if not conexion:
            raise RuntimeError("No se establecio la conexion MQTT")

        print("--------------------------------")
        print("Certificado utilizado: ACOPIO01")
        print(f"Identificador de prueba: {identificador}")

        print("--------------------------------")
        print("Prueba 1: publicacion autorizada")
        print(f"Topico: {topico_propio}")

        resultado_propio = cliente.publish(
            topico_propio,
            json.dumps(lectura),
            qos=MQTT_QOS,
        )

        print(f"Resultado local: {resultado_propio.rc}")

        time.sleep(2)

        print("--------------------------------")
        print("Prueba 2: publicacion NO autorizada")
        print(f"Topico: {topico_ajeno}")

        resultado_ajeno = cliente.publish(
            topico_ajeno,
            json.dumps(lectura),
            qos=MQTT_QOS,
        )

        print(f"Resultado local: {resultado_ajeno.rc}")

        time.sleep(3)

        print("--------------------------------")
        print("Prueba terminada")
        print(
            "IMPORTANTE: rc=0 no confirma autorizacion AWS. "
            "Verificar MQTT test client y DynamoDB."
        )

    finally:
        if cliente.is_connected():
            cliente.disconnect()

        cliente.loop_stop()


if __name__ == "__main__":
    main()
