variable "region" {
  description = "Regione AWS"
  type        = string
  default     = "eu-west-1"
}

variable "master_instance_type" {
  description = "Tipo istanza master — t3.small (2GB) necessario per k3s server"
  type        = string
  default     = "t3.small"
}

variable "worker_instance_type" {
  description = "Tipo istanza worker — t3.micro (1GB) sufficiente per k3s agent"
  type        = string
  default     = "t3.micro"
}

variable "key_name" {
  description = "Nome del Key Pair AWS per accesso SSH (già creato in Learning/aws/esempi/02-ec2)"
  type        = string
  default     = "aws-learning-key"
}

variable "worker_count" {
  description = "Numero di nodi worker"
  type        = number
  default     = 2
}

variable "db_instance_class" {
  description = "Classe istanza RDS"
  type        = string
  default     = "db.t3.micro"
}

variable "db_username" {
  description = "Master username RDS"
  type        = string
  default     = "taskflow"
}

variable "db_password" {
  description = "Master password RDS — passare con -var o terraform.tfvars (mai un default committato)"
  type        = string
  sensitive   = true
}
