
# Registro del primer sensor de temperatura
resource "aws_iot_thing" "sensor_01" {
  name = "agrolink-acopio01-camara01-sensor01"

  attributes = {
    Acopio = "ACOPIO01"
    Camara = "CAMARA01"
    Tipo   = "temperatura_humedad"
  }
}
