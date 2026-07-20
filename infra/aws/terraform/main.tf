terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

# --- Rete: VPC con subnet pubblica (EC2) e 2 subnet private in AZ diverse (RDS) ---

resource "aws_vpc" "taskflow" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "taskflow-vpc"
  }
}

resource "aws_internet_gateway" "taskflow" {
  vpc_id = aws_vpc.taskflow.id

  tags = {
    Name = "taskflow-igw"
  }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.taskflow.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.region}a"
  map_public_ip_on_launch = true

  tags = {
    Name = "taskflow-public"
  }
}

# RDS richiede un subnet group su almeno 2 Availability Zone diverse, anche per una singola istanza
resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.taskflow.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "${var.region}a"

  tags = {
    Name = "taskflow-private-a"
  }
}

resource "aws_subnet" "private_b" {
  vpc_id            = aws_vpc.taskflow.id
  cidr_block        = "10.0.3.0/24"
  availability_zone = "${var.region}b"

  tags = {
    Name = "taskflow-private-b"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.taskflow.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.taskflow.id
  }

  tags = {
    Name = "taskflow-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# Le subnet private non hanno route verso l'Internet Gateway: restano sulla route table
# principale della VPC (solo routing locale) — coerente con "subnet privata = nessun accesso da/verso internet".

# --- Security group ---

resource "aws_security_group" "k3s" {
  name        = "taskflow-k3s-sg"
  description = "Security group per cluster k3s"
  vpc_id      = aws_vpc.taskflow.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "k3s API server (kubectl)"
    from_port   = 6443
    to_port     = 6443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP (Traefik ingress)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Traffico interno tra nodi del cluster"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "taskflow-k3s-sg"
  }
}

resource "aws_security_group" "rds" {
  name        = "taskflow-rds-sg"
  description = "Permette PostgreSQL solo dai nodi del cluster k3s"
  vpc_id      = aws_vpc.taskflow.id

  ingress {
    description     = "PostgreSQL dal cluster k3s"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.k3s.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "taskflow-rds-sg"
  }
}

# --- RDS PostgreSQL (subnet private) ---

resource "aws_db_subnet_group" "taskflow" {
  name       = "taskflow-db-subnet-group"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]

  tags = {
    Name = "taskflow-db-subnet-group"
  }
}

resource "aws_db_instance" "taskflow" {
  identifier             = "taskflow-db"
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = var.db_instance_class
  allocated_storage      = 20
  db_name                = "taskflow"
  username               = var.db_username
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.taskflow.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  skip_final_snapshot    = true

  tags = {
    Name = "taskflow-db"
  }
}

# --- EC2: master + worker (subnet pubblica) ---

resource "aws_instance" "master" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.master_instance_type
  key_name                    = var.key_name
  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.k3s.id]
  associate_public_ip_address = true

  tags = {
    Name = "taskflow-master"
    Role = "master"
  }
}

resource "aws_instance" "worker" {
  count                       = var.worker_count
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.worker_instance_type
  key_name                    = var.key_name
  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.k3s.id]
  associate_public_ip_address = true

  tags = {
    Name = "taskflow-worker${count.index + 1}"
    Role = "worker"
  }
}
