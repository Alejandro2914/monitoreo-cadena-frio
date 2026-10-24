

resource "aws_iot_topic_rule" "lecturas_dynamodb" {
  name        = "agrolink_lecturas_dynamodb"
  description = "Procesa lecturas MQTT mediante Lambda con deduplicacion estricta"

  enabled     = true
  sql_version = "2016-03-23"

  sql = <<-SQL
    SELECT *
    FROM 'agrolink/+/+/lecturas'
  SQL

  lambda {
    function_arn = aws_lambda_function.procesar_lectura.arn
  }
}
