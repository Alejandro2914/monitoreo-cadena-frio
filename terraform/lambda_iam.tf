
resource "aws_iam_role" "lambda_lecturas" {
  name = "agrolink-lambda-lecturas-role"

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

resource "aws_iam_role_policy" "lambda_lecturas" {
  name = "agrolink-lambda-lecturas-policy"
  role = aws_iam_role.lambda_lecturas.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "AdministrarLecturasYEstadosDeAlertas"
        Effect = "Allow"

        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem"
        ]

        Resource = aws_dynamodb_table.lecturas.arn
      },
      {
        Sid    = "PublicarNotificacionesAgroLink"
        Effect = "Allow"

        Action = [
          "sns:Publish"
        ]

        Resource = aws_sns_topic.alertas_cadena_frio.arn
      },
      {
        Sid    = "CrearGrupoDeLogs"
        Effect = "Allow"

        Action = [
          "logs:CreateLogGroup"
        ]

        Resource = "arn:aws:logs:us-east-2:619071328452:*"
      },
      {
        Sid    = "RegistrarEjecucionesLambda"
        Effect = "Allow"

        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]

        Resource = "arn:aws:logs:us-east-2:619071328452:log-group:/aws/lambda/agrolink-procesar-lectura:*"
      }
    ]
  })
}
