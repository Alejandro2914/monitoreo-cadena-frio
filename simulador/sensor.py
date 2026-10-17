
import random
import time
from datetime import datetime, timezone
import json
import uuid

# Identificación del sensor
ID_ACOPIO = "ACOPIO01"
ID_CAMARA = "CAMARA01"

# Rango de temperatura permitido
RANGO_MIN = 2.0
RANGO_MAX = 8.0

while True:
    # Generamos lecturas simuladas
    temperatura = round(random.uniform(1, 12), 2)
    humedad = round(random.uniform(60, 90), 2)

    # Comprobamos si la temperatura está permitida
    if RANGO_MIN <= temperatura <= RANGO_MAX:
        estado = "NORMAL"
    else:
        estado = "FUERA DE RANGO"

    # Mostramos los datos del sensor
    print("------------------------------")
    print(f"Centro: {ID_ACOPIO}")
    print(f"Cámara: {ID_CAMARA}")
    print(f"Temperatura: {temperatura} °C")
    print(f"Humedad: {humedad} %")
    print(f"Estado: {estado}")
    print(f"Fecha: {datetime.now(timezone.utc).isoformat()}")

    
    lectura = {
        "id_lectura": str(uuid.uuid4()),
        "id_acopio": ID_ACOPIO,
        "id_camara": ID_CAMARA,
        "topico": f"agrolink/{ID_ACOPIO}/{ID_CAMARA}/lecturas",
        "temperatura_c": temperatura,
        "humedad_pct": humedad,
        "marca_tiempo": datetime.now(timezone.utc).isoformat(),
        "qos": 1,
        "rango_min_c": RANGO_MIN,
        "rango_max_c": RANGO_MAX,
        "estado_conexion": "conectado",
        "tipo_alerta": "ninguna"
    }

    mensaje_json = json.dumps(
        lectura,
        indent=4,
        ensure_ascii=False
    )

    print(mensaje_json)

    # Esperamos 5 segundos antes de la siguiente lectura
    time.sleep(5)
