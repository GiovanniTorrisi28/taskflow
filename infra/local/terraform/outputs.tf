output "master_name" {
  value = multipass_instance.master.name
}

output "worker_names" {
  value = [
    multipass_instance.worker1.name,
    multipass_instance.worker2.name,
  ]
}

output "next_step" {
  value = "Esegui: multipass list — poi aggiorna inventory.ini con gli IP della colonna IPv4"
}
