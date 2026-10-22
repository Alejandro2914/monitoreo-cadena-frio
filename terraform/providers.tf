
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "monitoreo-cadena-frio"
      Environment = "dev"
      ManagedBy   = "Terraform"
    }
  }
}
