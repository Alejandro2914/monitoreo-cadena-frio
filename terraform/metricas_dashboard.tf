
# ==========================================
# AgroLink - Metricas y dashboard operativo
# ==========================================

# Rol de ejecucion de la Lambda de metricas.
resource "aws_iam_role" "lambda_metricas_panel" {
  name = "agrolink-lambda-metricas-panel-role"

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

# Permisos minimos de la Lambda de metricas.
resource "aws_iam_role_policy" "lambda_metricas_panel" {
  name = "agrolink-lambda-metricas-panel-policy"
  role = aws_iam_role.lambda_metricas_panel.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "ConsultarUltimasLecturas"
        Effect = "Allow"

        Action = [
          "dynamodb:Query"
        ]

        Resource = aws_dynamodb_table.lecturas.arn
      },
      {
        Sid    = "PublicarMetricasAgroLink"
        Effect = "Allow"

        Action = [
          "cloudwatch:PutMetricData"
        ]

        Resource = "*"

        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "AgroLink/CadenaFrio"
          }
        }
      },
      {
        Sid    = "RegistrarLogsMetricas"
        Effect = "Allow"

        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]

        Resource = "${aws_cloudwatch_log_group.lambda_metricas_panel.arn}:*"
      }
    ]
  })
}

# Logs con retencion controlada.
resource "aws_cloudwatch_log_group" "lambda_metricas_panel" {
  name              = "/aws/lambda/agrolink-metricas-panel"
  retention_in_days = 7

  tags = {
    Proyecto = "AgroLink"
  }
}

# Lambda de publicacion de temperaturas.
resource "aws_lambda_function" "metricas_panel" {
  function_name = "agrolink-metricas-panel"

  description = "Publica la ultima temperatura persistida de cada camara en CloudWatch"

  filename         = data.archive_file.lambda_lecturas.output_path
  source_code_hash = data.archive_file.lambda_lecturas.output_base64sha256

  role    = aws_iam_role.lambda_metricas_panel.arn
  handler = "metricas_panel.lambda_handler"
  runtime = "python3.13"

  timeout     = 30
  memory_size = 128

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.lecturas.name
    }
  }

  depends_on = [
    aws_iam_role_policy.lambda_metricas_panel,
    aws_cloudwatch_log_group.lambda_metricas_panel
  ]

  tags = {
    Proyecto = "AgroLink"
    Ambiente = "academico"
  }
}

# Ejecucion automatica cada minuto.
resource "aws_cloudwatch_event_rule" "metricas_panel" {
  name                = "agrolink-actualizar-metricas-panel"
  description         = "Actualiza las temperaturas del panel cada minuto"
  schedule_expression = "rate(1 minute)"

  tags = {
    Proyecto = "AgroLink"
  }
}

resource "aws_cloudwatch_event_target" "metricas_panel" {
  rule      = aws_cloudwatch_event_rule.metricas_panel.name
  target_id = "agrolink-metricas-panel"
  arn       = aws_lambda_function.metricas_panel.arn
}

resource "aws_lambda_permission" "eventbridge_metricas_panel" {
  statement_id  = "PermitirMetricasDesdeEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.metricas_panel.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.metricas_panel.arn
}

# ==========================================
# Dashboard exigido en el punto 6
# ==========================================

resource "aws_cloudwatch_dashboard" "agrolink_operativo" {
  dashboard_name = "AgroLink-Cadena-Frio-Operativo-IaC"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 24
        height = 7

        properties = {
          title  = "AgroLink - Volumen de mensajes de lectura"
          region = var.aws_region
          view   = "timeSeries"
          period = 60
          stat   = "Sum"

          metrics = [
            [
              "AWS/IoT",
              "TopicMatch",
              "RuleName",
              aws_iot_topic_rule.lecturas_dynamodb.name,
              {
                label = "Mensajes MQTT coincidentes"
              }
            ]
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 7
        width  = 24
        height = 8

        properties = {
          title  = "AgroLink - Ultima temperatura almacenada por camara"
          region = var.aws_region
          view   = "singleValue"
          period = 60
          stat   = "Maximum"

          setPeriodToTimeRange = false

          metrics = [
            for numero in range(1, 9) : [
              "AgroLink/CadenaFrio",
              "UltimaTemperatura",
              "CamaraId",
              format("ACOPIO%02d#CAMARA01", numero),
              {
                label = format("ACOPIO%02d / CAMARA01 (C)", numero)
              }
            ]
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 15
        width  = 24
        height = 7

        properties = {
          title  = "AgroLink - Errores de enrutamiento AWS IoT"
          region = var.aws_region
          view   = "timeSeries"
          period = 60
          stat   = "Sum"

          metrics = [
            [
              "AWS/IoT",
              "ParseError",
              "RuleName",
              aws_iot_topic_rule.lecturas_dynamodb.name,
              {
                label = "Errores al interpretar JSON"
              }
            ],
            [
              {
                expression = "SEARCH('{AWS/IoT,RuleName,ActionType} MetricName=\"Failure\" RuleName=\"agrolink_lecturas_dynamodb\"', 'Sum', 60)"
                id         = "errores_acciones"
                label      = "Fallo accion IoT"
              }
            ]
          ]
        }
      }
    ]
  })
}
