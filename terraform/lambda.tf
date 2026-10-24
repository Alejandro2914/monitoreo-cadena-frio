
data "archive_file" "lambda_lecturas" {
  type        = "zip"
  source_file = "${path.module}/../lambda/procesar_lectura.py"
  output_path = "${path.module}/lambda_lecturas.zip"
}

resource "aws_lambda_function" "procesar_lectura" {
  function_name = "agrolink-procesar-lectura"
  description   = "Almacena lecturas de sensores sin sobrescribir duplicados"

  filename         = data.archive_file.lambda_lecturas.output_path
  source_code_hash = data.archive_file.lambda_lecturas.output_base64sha256

  role    = aws_iam_role.lambda_lecturas.arn
  handler = "procesar_lectura.lambda_handler"
  runtime = "python3.13"

  timeout     = 15
  memory_size = 128

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.lecturas.name
    }
  }

  depends_on = [
    aws_iam_role_policy.lambda_lecturas
  ]

  tags = {
    Proyecto = "AgroLink"
    Ambiente = "academico"
  }
}
