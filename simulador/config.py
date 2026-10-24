

# Configuracion general de AgroLink

# Sensor predeterminado: mantiene compatibilidad con el sistema actual.
ID_ACOPIO = "ACOPIO01"
ID_CAMARA = "CAMARA01"

# Nivel de calidad de servicio MQTT: al menos una entrega.
MQTT_QOS = 1

# Centros de acopio que participaran en la simulacion.
# Cada centro tiene inicialmente una camara y un sensor.
SENSORES = [
    {"id_acopio": "ACOPIO01", "id_camara": "CAMARA01", "id_sensor": "SENSOR01"},
    {"id_acopio": "ACOPIO02", "id_camara": "CAMARA01", "id_sensor": "SENSOR01"},
    {"id_acopio": "ACOPIO03", "id_camara": "CAMARA01", "id_sensor": "SENSOR01"},
    {"id_acopio": "ACOPIO04", "id_camara": "CAMARA01", "id_sensor": "SENSOR01"},
    {"id_acopio": "ACOPIO05", "id_camara": "CAMARA01", "id_sensor": "SENSOR01"},
    {"id_acopio": "ACOPIO06", "id_camara": "CAMARA01", "id_sensor": "SENSOR01"},
    {"id_acopio": "ACOPIO07", "id_camara": "CAMARA01", "id_sensor": "SENSOR01"},
    {"id_acopio": "ACOPIO08", "id_camara": "CAMARA01", "id_sensor": "SENSOR01"},
]


def obtener_topico_lecturas(id_acopio, id_camara):
    """Construye el topico MQTT de una camara."""
    return f"agrolink/{id_acopio}/{id_camara}/lecturas"


def obtener_cliente_id(id_acopio, id_camara, id_sensor):
    """Construye un identificador MQTT unico por sensor."""
    return (
        f"agrolink-{id_acopio.lower()}-"
        f"{id_camara.lower()}-{id_sensor.lower()}"
    )


# Compatibilidad con el sensor actual y la prueba de deduplicacion.
TOPICO_LECTURAS = obtener_topico_lecturas(ID_ACOPIO, ID_CAMARA)
