
# Sensores adicionales de AgroLink.
# ACOPIO01 ya existe y se conserva sin modificaciones.

locals {
  sensores_adicionales = {
    for numero in range(2, 9) :
    format("ACOPIO%02d", numero) => {
      camara = "CAMARA01"
      sensor = "sensor01"
    }
  }
}

# Registrar siete Things adicionales en AWS IoT Core.
resource "aws_iot_thing" "sensores_adicionales" {
  for_each = local.sensores_adicionales

  name = "agrolink-${lower(each.key)}-${lower(each.value.camara)}-${each.value.sensor}"

  attributes = {
    Acopio = each.key
    Camara = each.value.camara
    Tipo   = "temperatura_humedad"
  }
}

# Una politica reutilizable para los siete nuevos sensores.
resource "aws_iot_policy" "sensores_compartida" {
  name = "agrolink-sensores-politica-compartida"

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"
        Action = "iot:Connect"

        Resource = "arn:aws:iot:us-east-2:619071328452:client/$${iot:Connection.Thing.ThingName}"

        Condition = {
          Bool = {
            "iot:Connection.Thing.IsAttached" = "true"
          }
        }
      },
      {
        Effect = "Allow"
        Action = "iot:Publish"

        Resource = "arn:aws:iot:us-east-2:619071328452:topic/agrolink/$${iot:Connection.Thing.Attributes[Acopio]}/$${iot:Connection.Thing.Attributes[Camara]}/lecturas"
      }
    ]
  })
}
