
# Rol de ejecucion del supervisor de sensores.
resource "aws_iam_role" "lambda_supervision" {
  name = "agrolink-lambda-supervision-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "lambda.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Proyecto = "AgroLink"
  }
}

# Permisos de ejecucion del supervisor.
resource "aws_iam_role_policy" "lambda_supervision" {
  name = "agrolink-lambda-supervision-policy"
  role = aws_iam_role.lambda_supervision.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "ConsultarYActualizarActividad"
        Effect = "Allow"

        Action = [
          "dynamodb:GetItem",
          "dynamodb:UpdateItem"
        ]

        Resource = aws_dynamodb_table.lecturas.arn
      },
      {
        Sid    = "PublicarAlertasDeConexion"
        Effect = "Allow"

        Action = [
          "sns:Publish"
        ]

        Resource = aws_sns_topic.alertas_cadena_frio.arn
      },
      {
        Sid    = "EscribirRegistrosCloudWatch"
        Effect = "Allow"

        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]

        Resource = "${aws_cloudwatch_log_group.lambda_supervision.arn}:*"
      }
    ]
  })
}

# Grupo de logs del supervisor.
resource "aws_cloudwatch_log_group" "lambda_supervision" {
  name              = "/aws/lambda/agrolink-supervisar-sensores"
  retention_in_days = 7

  tags = {
    Proyecto = "AgroLink"
  }
}

# Lambda de supervision.
resource "aws_lambda_function" "supervisar_sensores" {
  function_name = "agrolink-supervisar-sensores"

  description = "Detecta camaras sin lecturas y cambios de conexion"

  filename         = data.archive_file.lambda_lecturas.output_path
  source_code_hash = data.archive_file.lambda_lecturas.output_base64sha256

  role    = aws_iam_role.lambda_supervision.arn
  handler = "supervisar_sensores.lambda_handler"
  runtime = "python3.13"

  timeout     = 30
  memory_size = 128

  environment {
    variables = {
      DYNAMODB_TABLE              = aws_dynamodb_table.lecturas.name
      SNS_TOPIC_ARN               = aws_sns_topic.alertas_cadena_frio.arn
      UMBRAL_INACTIVIDAD_SEGUNDOS = "120"
    }
  }

  depends_on = [
    aws_iam_role_policy.lambda_supervision,
    aws_cloudwatch_log_group.lambda_supervision
  ]

  tags = {
    Proyecto = "AgroLink"
    Ambiente = "academico"
  }
}

# Comprobacion automatica cada minuto.
resource "aws_cloudwatch_event_rule" "supervision_sensores" {
  name                = "agrolink-supervision-sensores"
  description         = "Verifica sensores inactivos cada minuto"
  schedule_expression = "rate(1 minute)"

  tags = {
    Proyecto = "AgroLink"
  }
}

# Asociar la regla de EventBridge con la Lambda.
resource "aws_cloudwatch_event_target" "supervision_sensores" {
  rule      = aws_cloudwatch_event_rule.supervision_sensores.name
  target_id = "agrolink-supervisar-sensores"
  arn       = aws_lambda_function.supervisar_sensores.arn
}

# Permitir que EventBridge invoque la Lambda.
resource "aws_lambda_permission" "eventbridge_supervision" {
  statement_id  = "PermitirSupervisionDesdeEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.supervisar_sensores.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.supervision_sensores.arn
}
