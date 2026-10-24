
# Certificado X.509 del sensor ACOPIO02.
# El certificado fue creado manualmente en AWS IoT Core.

locals {
  sensor_02_certificate_arn = "arn:aws:iot:us-east-2:619071328452:cert/522bcd4fb6e03bee603165a9babdec840f4b907143c7db32a259767c818098c2"
}

# Asociar el certificado con el Thing de ACOPIO02.
resource "aws_iot_thing_principal_attachment" "sensor_02" {
  thing = aws_iot_thing.sensores_adicionales["ACOPIO02"].name

  principal = local.sensor_02_certificate_arn
}

# Asociar la politica MQTT compartida al certificado.
resource "aws_iot_policy_attachment" "sensor_02" {
  policy = aws_iot_policy.sensores_compartida.name

  target = local.sensor_02_certificate_arn
}
