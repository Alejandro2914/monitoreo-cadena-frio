
# Registro del primer sensor de temperatura
resource "aws_iot_thing" "sensor_01" {
  name = "agrolink-acopio01-camara01-sensor01"

  attributes = {
    Acopio = "ACOPIO01"
    Camara = "CAMARA01"
    Tipo   = "temperatura_humedad"
  }
}
# Permisos MQTT del primer sensor
resource "aws_iot_policy" "sensor_01" {
  name = "agrolink-acopio01-camara01-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "iot:Connect"
        Resource = "arn:aws:iot:us-east-2:619071328452:client/agrolink-acopio01-camara01-sensor01"
        Condition = {
          Bool = {
            "iot:Connection.Thing.IsAttached" = "true"
          }
        }
      },
      {
        Effect   = "Allow"
        Action   = "iot:Publish"
        Resource = "arn:aws:iot:us-east-2:619071328452:topic/agrolink/ACOPIO01/CAMARA01/lecturas"
      }
    ]
  })
}