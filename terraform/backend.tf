
terraform {
  backend "s3" {
    bucket       = "monitoreo-cadena-frio-tfstate-619071328452"
    key          = "cadena-frio/terraform.tfstate"
    region       = "us-east-2"
    encrypt      = true
    use_lockfile = true
  }
}
