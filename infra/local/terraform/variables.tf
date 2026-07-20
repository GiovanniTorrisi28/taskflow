variable "cpus" {
  description = "Numero di CPU per ogni VM"
  type        = number
  default     = 1
}

variable "memory" {
  description = "RAM per ogni VM (1G causa memory starvation su k3s)"
  type        = string
  default     = "2G"
}

variable "disk" {
  description = "Disco per ogni VM"
  type        = string
  default     = "8G"
}

variable "network" {
  description = "Interfaccia di rete bridged per comunicazione inter-VM"
  type        = string
  default     = "Wi-Fi"
}

variable "worker_count" {
  description = "Numero di nodi worker"
  type        = number
  default     = 2
}
