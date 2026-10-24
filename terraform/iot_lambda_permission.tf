
resource "aws_lambda_permission" "iot_invocar_lecturas" {
  statement_id = "PermitirInvocacionDesdeIoT"

  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.procesar_lectura.function_name
  principal     = "iot.amazonaws.com"

  source_arn = aws_iot_topic_rule.lecturas_dynamodb.arn

  source_account = "619071328452"
}
