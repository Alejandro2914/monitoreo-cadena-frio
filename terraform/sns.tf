
# Tema SNS para notificaciones del sistema AgroLink.
resource "aws_sns_topic" "alertas_cadena_frio" {
  name = "agrolink-alertas-cadena-frio"

  tags = {
    Proyecto      = "AgroLink"
    Ambiente      = "academico"
    GestionadoPor = "Terraform"
  }
}
