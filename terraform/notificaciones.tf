
# Rol IAM de la Lambda que envia notificaciones.
resource "aws_iam_role" "lambda_notificaciones" {
  name = "agrolink-lambda-notificaciones-role"

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

# Permisos exclusivos del consumidor de notificaciones.
resource "aws_iam_role_policy" "lambda_notificaciones" {
  name = "agrolink-lambda-notificaciones-policy"
  role = aws_iam_role.lambda_notificaciones.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "LeerDynamoDBStreams"
        Effect = "Allow"

        Action = [
          "dynamodb:DescribeStream",
          "dynamodb:GetRecords",
          "dynamodb:GetShardIterator"
        ]

        Resource = aws_dynamodb_table.lecturas.stream_arn
      },
      {
        Sid    = "ListarStreamsDynamoDB"
        Effect = "Allow"

        Action = [
          "dynamodb:ListStreams"
        ]

        Resource = "*"
      },
      {
        Sid    = "ActualizarEventosOutbox"
        Effect = "Allow"

        Action = [
          "dynamodb:GetItem",
          "dynamodb:UpdateItem"
        ]

        Resource = aws_dynamodb_table.lecturas.arn
      },
      {
        Sid    = "PublicarAlertasSNS"
        Effect = "Allow"

        Action = [
          "sns:Publish"
        ]

        Resource = aws_sns_topic.alertas_cadena_frio.arn
      },
      {
        Sid    = "EscribirLogsLambda"
        Effect = "Allow"

        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]

        Resource = "${aws_cloudwatch_log_group.lambda_notificaciones.arn}:*"
      }
    ]
  })
}

# Grupo de logs de la Lambda de notificaciones.
resource "aws_cloudwatch_log_group" "lambda_notificaciones" {
  name              = "/aws/lambda/agrolink-enviar-notificaciones"
  retention_in_days = 7

  tags = {
    Proyecto = "AgroLink"
  }
}

# Lambda encargada de enviar las alertas a SNS.
resource "aws_lambda_function" "enviar_notificaciones" {
  function_name = "agrolink-enviar-notificaciones"

  description = "Procesa eventos Outbox desde DynamoDB Streams y publica alertas en SNS"

  filename         = data.archive_file.lambda_lecturas.output_path
  source_code_hash = data.archive_file.lambda_lecturas.output_base64sha256

  role    = aws_iam_role.lambda_notificaciones.arn
  handler = "despachar_notificaciones.lambda_handler"
  runtime = "python3.13"

  timeout     = 30
  memory_size = 128

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.lecturas.name
      SNS_TOPIC_ARN  = aws_sns_topic.alertas_cadena_frio.arn
    }
  }

  depends_on = [
    aws_iam_role_policy.lambda_notificaciones,
    aws_cloudwatch_log_group.lambda_notificaciones
  ]

  tags = {
    Proyecto = "AgroLink"
    Ambiente = "academico"
  }
}

# Conectar DynamoDB Streams con la Lambda de notificaciones.
resource "aws_lambda_event_source_mapping" "notificaciones_stream" {
  event_source_arn  = aws_dynamodb_table.lecturas.stream_arn
  function_name     = aws_lambda_function.enviar_notificaciones.arn
  starting_position = "TRIM_HORIZON"

  batch_size = 1
  enabled    = true

  depends_on = [
    aws_iam_role_policy.lambda_notificaciones
  ]
}
