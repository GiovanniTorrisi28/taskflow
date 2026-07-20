output "master_public_ip" {
  description = "IP pubblico del master (per SSH e kubectl)"
  value       = aws_instance.master.public_ip
}

output "master_private_ip" {
  description = "IP privato del master (per comunicazione interna k3s)"
  value       = aws_instance.master.private_ip
}

output "worker_public_ips" {
  description = "IP pubblici dei worker (per SSH Ansible)"
  value       = aws_instance.worker[*].public_ip
}

output "rds_address" {
  description = "Hostname della RDS (senza porta)"
  value       = aws_db_instance.taskflow.address
}

output "rds_endpoint" {
  description = "Hostname:porta della RDS"
  value       = aws_db_instance.taskflow.endpoint
}
