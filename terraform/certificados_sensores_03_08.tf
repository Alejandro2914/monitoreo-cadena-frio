
# Certificados de los sensores ACOPIO03 a ACOPIO08.
# Los certificados ya fueron generados en AWS IoT Core.
# No se almacenan claves privadas en Terraform.

locals {
  certificados_sensores_03_08 = {
    ACOPIO03 = "arn:aws:iot:us-east-2:619071328452:cert/a96c176cc5a42837812107515604cd7a710c41e8e777f15256bed30afe44122f"
    ACOPIO04 = "arn:aws:iot:us-east-2:619071328452:cert/1135e3cb4a600bb882195c12c3e6076132c02bfc6c5052cafdc7731039506e38"
    ACOPIO05 = "arn:aws:iot:us-east-2:619071328452:cert/254eb853e8c883fbc0602dc3ae60be83be6a8eb41b1384cd40bb1f9b91f6cad4"
    ACOPIO06 = "arn:aws:iot:us-east-2:619071328452:cert/4f4924ab57fabd1b060cca835763977b1ff017eb3b91fad5d04577c0313efec3"
    ACOPIO07 = "arn:aws:iot:us-east-2:619071328452:cert/21de96d7aacc7b735b2bad76df5fc5b1151049a43a7bd5491fc43be02bdf571c"
    ACOPIO08 = "arn:aws:iot:us-east-2:619071328452:cert/cd1150d8809614996ead30deb18d1ab9ac93f020ff3d28694f26ed7fb2410b9a"
  }
}

# Asociar cada certificado con su Thing.
resource "aws_iot_thing_principal_attachment" "sensores_03_08" {
  for_each = local.certificados_sensores_03_08

  thing = aws_iot_thing.sensores_adicionales[each.key].name

  principal = each.value
}

# Asociar la politica MQTT compartida con cada certificado.
resource "aws_iot_policy_attachment" "sensores_03_08" {
  for_each = local.certificados_sensores_03_08

  policy = aws_iot_policy.sensores_compartida.name

  target = each.value
}
