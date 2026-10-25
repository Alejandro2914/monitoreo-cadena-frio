
# Empaquetar los archivos Python de la funcion Lambda.
data "archive_file" "lambda_lecturas" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda"
  output_path = "${path.module}/lambda_lecturas.zip"

  excludes = [
    "__pycache__",
    "*.pyc",
    "test_*.py",
    "tests/**",
    ".pytest_cache/**"
  ]
}

# Funcion Lambda que procesa las lecturas MQTT.
resource "aws_lambda_function" "procesar_lectura" {
  function_name = "agrolink-procesar-lectura"

  description = "Procesa lecturas MQTT, evita duplicados y evalua alertas de temperatura"

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
      SNS_TOPIC_ARN  = aws_sns_topic.alertas_cadena_frio.arn
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
