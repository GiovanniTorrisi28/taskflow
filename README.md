# TaskFlow

Task manager collaborativo a microservizi — progetto per il corso di Sistemi Cloud (vedi `../StrutturaProgettoCloud.md`).

## Architettura

3 microservizi Flask indipendenti, ognuno padrone del proprio database PostgreSQL (database separato, stesso container Postgres in locale):

- **user-service** (`users_db`) — registrazione, login, emissione JWT
- **project-service** (`projects_db`) — progetti, membri, task
- **activity-service** (`activities_db`) — log attività e commenti sui task

Il frontend (HTML/CSS/JS vanilla) parla con i tre servizi tramite un reverse proxy nginx che espone path unificati (`/api/auth`, `/api/users`, `/api/projects`, `/api/tasks`, `/api/activities`, `/api/comments`), così il codice frontend non cambia tra ambiente locale e Kubernetes (dove lo stesso ruolo lo farà l'Ingress).


## Sviluppo locale

```bash
docker compose up --build
```

- **Frontend (usare questo per l'app)**: http://localhost:8080

Le porte dei singoli servizi sono esposte solo per debug diretto via `curl`/Postman (API, non pagine web — visitarle nel browser dà 404 sulla root):
- user-service: http://localhost:5001 (provare `GET /health`)
- project-service: http://localhost:5002 (provare `GET /health`)
- activity-service: http://localhost:5003 (provare `GET /health`)

## Test

Ogni servizio ha la sua suite pytest, indipendente dagli altri (usa SQLite in-memory al posto di PostgreSQL):

```bash
cd services/<nome-servizio>
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements-dev.txt
pytest -q
```

## Deploy su Kubernetes locale (Multipass + k3s)

Guida completa per far girare l'app su un cluster k3s reale a 3 nodi (1 master + 2 worker), partendo da zero. Pensata per essere seguita da chi non ha mai lanciato questo progetto — utile per rifare il deploy da capo o per chi deve solo valutare/provare il progetto.

### Prerequisiti

- **Multipass** installato ([multipass.run](https://multipass.run)) — su Windows usa il backend VirtualBox (Hyper-V spesso non disponibile su Windows Home)
- **Terraform** installato
- **Docker Desktop** installato e in esecuzione (serve solo per buildare le immagini, non deve restare acceso durante il resto del deploy)
- **WSL2** con una distribuzione Linux (es. Ubuntu) con **Ansible** installato — Ansible non gira nativamente su Windows
- Non serve `kubectl` sul PC Windows: in questa guida i comandi Kubernetes girano direttamente sul nodo master tramite Ansible

### Architettura del deploy

- 3 VM Multipass su rete bridged Wi-Fi (necessaria per farle comunicare tra loro e per raggiungerle da WSL2)
- k3s con **Traefik** come ingress controller (incluso di default in k3s, non lo disabilitiamo)
- Le 4 immagini Docker (3 servizi + frontend) vengono buildate in locale e **importate direttamente** nei nodi via SSH — nessun registry esterno necessario in questa fase (il push su un registry è la Fase C, CI/CD)
- Nessuna persistenza dati (Postgres perde i dati se il pod viene ricreato) — scelta accettabile per un progetto didattico

### Passaggi

**1. Build ed esporta le immagini Docker**

```bash
cd taskflow
docker compose build
docker save taskflow-user-service:latest -o infra/local/images/taskflow-user-service.tar
docker save taskflow-project-service:latest -o infra/local/images/taskflow-project-service.tar
docker save taskflow-activity-service:latest -o infra/local/images/taskflow-activity-service.tar
docker save taskflow-frontend:latest -o infra/local/images/taskflow-frontend.tar
```

**2. Crea le 3 VM con Terraform**

```powershell
cd infra/local/terraform
terraform init
terraform apply
```

Conferma con `yes`. Crea `taskflow-master`, `taskflow-worker1`, `taskflow-worker2` (1 CPU, 2GB RAM, 8GB disco ciascuna) su rete bridged Wi-Fi. Ci vogliono un paio di minuti.

> Se la creazione va in timeout o le VM restano "Running" senza mai diventare raggiungibili, vedi la sezione **Troubleshooting** in fondo prima di insistere.

**3. Recupera gli IP delle VM**

```powershell
multipass list
```

Annota l'IP di ciascuna VM.

**4. Prepara la chiave SSH per Ansible (dentro WSL2)**

Se non esiste già una chiave dedicata:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/ansible_key -N ""
```

Inietta la chiave pubblica in tutte e 3 le VM (da Windows — funziona anche se la rete bridged non è ancora del tutto pronta, perché `multipass exec` usa il canale di gestione interno, non la rete bridged):

```powershell
$pubkey = (wsl -- cat ~/.ssh/ansible_key.pub).Trim()
multipass exec taskflow-master  -- bash -c "mkdir -p ~/.ssh && echo '$pubkey' >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
multipass exec taskflow-worker1 -- bash -c "mkdir -p ~/.ssh && echo '$pubkey' >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
multipass exec taskflow-worker2 -- bash -c "mkdir -p ~/.ssh && echo '$pubkey' >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
```

> Usa sempre `>>` (append), mai `>` (overwrite): le VM hanno già la chiave interna di Multipass in `authorized_keys` — sovrascriverla rompe `multipass exec`.

**5. Aggiorna l'inventory Ansible**

Apri `infra/local/ansible/inventory.ini` e sostituisci gli IP con quelli ottenuti al passo 3 (sia `ansible_host` che `static_ip` per ogni nodo devono avere lo **stesso valore** — è l'IP DHCP attuale che il passo successivo renderà statico). Controlla anche che `gateway` corrisponda al gateway della tua rete (di solito il primo indirizzo della sottorete, es. `192.168.1.1`).

**6. Configura IP statici** (sopravvivono ai riavvii delle VM)

Da WSL2:

```bash
cd "/mnt/c/Users/<tuo-utente>/Universita/Sistemi cloud/taskflow/infra/local/ansible"
ansible-playbook -i inventory.ini playbook-static-ip.yaml
```

**7. Installa k3s**

```bash
ansible-playbook -i inventory.ini playbook-k3s.yaml
```

Installa k3s server sul master (Traefik incluso) e k3s agent sui worker, poi verifica che tutti i nodi siano `Ready`. Richiede qualche minuto — **meglio lanciarlo direttamente nel terminale** (non tramite un assistente/chat) per evitare timeout.

**8. Importa le immagini Docker nei nodi**

```bash
ansible-playbook -i inventory.ini playbook-images.yaml
```

Copia via SSH e importa in containerd le 4 immagini su tutti e 3 i nodi (~250MB a nodo, richiede qualche minuto).

**9. Copia i manifest Kubernetes sul master e applicali**

```bash
ansible master -i inventory.ini -m copy -a "src='<percorso-progetto>/taskflow/k8s/' dest=/home/ubuntu/k8s/"
ansible master -i inventory.ini -m shell -a 'sudo kubectl apply -f /home/ubuntu/k8s/ --recursive' --become
```

> Se la prima esecuzione fallisce con errori tipo `namespace "taskflow" not found` su alcune risorse, è una race condition transitoria (il namespace non è ancora pienamente propagato quando vengono applicate le risorse successive). **Rilancia lo stesso comando** — `kubectl apply` è idempotente, la seconda volta va a buon fine.

**10. Verifica**

```bash
ansible master -i inventory.ini -m shell -a 'sudo kubectl get nodes' --become
ansible master -i inventory.ini -m shell -a 'sudo kubectl get pods -n taskflow' --become
```

Tutti e 3 i nodi devono essere `Ready`, tutti i pod `Running` e `1/1`. Alcuni riavvii iniziali dei pod applicativi sono normali: partono prima che Postgres sia pronto ad accettare connessioni e Kubernetes li riavvia automaticamente finché non si connettono con successo.

**11. Apri l'app**

Vai su `http://<IP-DEL-MASTER>/` nel browser (l'IP di `taskflow-master` ottenuto al passo 3).

### Fermare e riprendere il cluster

```powershell
multipass stop taskflow-master taskflow-worker1 taskflow-worker2
# ... in un secondo momento ...
multipass start taskflow-master taskflow-worker1 taskflow-worker2
```

Grazie agli IP statici configurati al passo 6, il cluster riparte con gli stessi indirizzi e k3s si riavvia da solo (è un servizio systemd) — non serve rifare l'installazione.

### Distruggere tutto

```powershell
cd infra/local/terraform
terraform destroy
```

Cancella le 3 VM. Verifica con `multipass list` che non resti nulla.

## Struttura

```
taskflow/
├── services/
│   ├── user-service/
│   ├── project-service/
│   └── activity-service/
├── frontend/
├── k8s/                  # Manifest Kubernetes (namespace, secret, deployment/service per servizio, ingress)
├── infra/
│   ├── local/
│   │   ├── terraform/    # Provisioning VM Multipass (k3s locale)
│   │   ├── ansible/      # Configurazione IP statici, installazione k3s, import immagini
│   │   └── images/       # Immagini Docker esportate (.tar, non versionate)
│   └── aws/              # Fase successiva: EC2 + k3s + RDS (non ancora implementata)
├── docker-compose.yml
└── .github/workflows/    # CI/CD (fase successiva, non ancora implementata)
```
