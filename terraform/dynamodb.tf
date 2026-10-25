
resource "aws_dynamodb_table" "lecturas" {
  name         = "agrolink-lecturas"
  billing_mode = "PAY_PER_REQUEST"

  hash_key         = "camara_id"
  range_key        = "lectura_id"
  stream_enabled   = true
  stream_view_type = "NEW_IMAGE"

  attribute {
    name = "camara_id"
    type = "S"
  }

  attribute {
    name = "lectura_id"
    type = "S"
  }

  ttl {
    attribute_name = "expira_en"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = false
  }

  tags = {
    Proyecto      = "AgroLink"
    Ambiente      = "academico"
    GestionadoPor = "Terraform"
  }
}
