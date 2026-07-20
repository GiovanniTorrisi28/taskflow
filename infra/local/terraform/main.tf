terraform {
  required_providers {
    multipass = {
      source  = "todoroff/multipass"
      version = "1.7.1"
    }
  }
}

resource "multipass_instance" "master" {
  name   = "taskflow-master"
  image  = "24.04"
  cpus   = var.cpus
  memory = var.memory
  disk   = var.disk
  networks {
    name = var.network
  }
}

resource "multipass_instance" "worker1" {
  name   = "taskflow-worker1"
  image  = "24.04"
  cpus   = var.cpus
  memory = var.memory
  disk   = var.disk
  networks {
    name = var.network
  }
}

resource "multipass_instance" "worker2" {
  name   = "taskflow-worker2"
  image  = "24.04"
  cpus   = var.cpus
  memory = var.memory
  disk   = var.disk
  networks {
    name = var.network
  }
}
