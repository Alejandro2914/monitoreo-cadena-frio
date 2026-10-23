
# ARN del certificado creado en AWS IoT Core
locals {
  sensor_01_certificate_arn = "arn:aws:iot:us-east-2:619071328452:cert/d25a28c7bf27a8eee9e6a45f08c50a8ff2b1334014faf977fc380329cb505e76"
}

# Asociar el certificado X.509 con el Thing
resource "aws_iot_thing_principal_attachment" "sensor_01" {
  thing     = aws_iot_thing.sensor_01.name
  principal = local.sensor_01_certificate_arn
}

# Asociar los permisos MQTT con el certificado
resource "aws_iot_policy_attachment" "sensor_01" {
  policy = aws_iot_policy.sensor_01.name
  target = local.sensor_01_certificate_arn
}
