
resource "aws_iam_role" "iot_dynamodb" {
  name = "agrolink-iot-dynamodb-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "iot.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Proyecto = "AgroLink"
  }
}

resource "aws_iam_role_policy" "iot_dynamodb" {
  name = "agrolink-iot-dynamodb-write"
  role = aws_iam_role.iot_dynamodb.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "dynamodb:PutItem"
        Resource = aws_dynamodb_table.lecturas.arn
      }
    ]
  })
}
