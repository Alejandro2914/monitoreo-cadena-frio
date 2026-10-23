
resource "aws_iot_topic_rule" "lecturas_dynamodb" {
  name        = "agrolink_lecturas_dynamodb"
  description = "Almacena las lecturas MQTT de las camaras en DynamoDB"

  enabled     = true
  sql_version = "2016-03-23"

  sql = <<-SQL
    SELECT
      *,
      concat(id_acopio, '#', id_camara) AS camara_id,
      concat(marca_tiempo, '#', id_lectura) AS lectura_id
    FROM 'agrolink/+/+/lecturas'
  SQL

  dynamodbv2 {
    put_item {
      table_name = aws_dynamodb_table.lecturas.name
    }

    role_arn = aws_iam_role.iot_dynamodb.arn
  }

  depends_on = [
    aws_iam_role_policy.iot_dynamodb
  ]
}
