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

## CI/CD (GitHub Actions)

Due workflow in `.github/workflows/`:

- **`ci.yml`** — esegue la suite pytest dei 3 servizi (matrix, uno per servizio) ad ogni push o pull request su `main`. Non richiede configurazione: parte così com'è.
- **`docker.yml`** — solo sui push a `main` **che toccano `services/`, `frontend/` o il workflow stesso** (un push che modifica solo README/documentazione non lo fa partire): rilancia gli stessi test e, se passano, builda e pusha su Docker Hub le 4 immagini (`taskflow-user-service`, `taskflow-project-service`, `taskflow-activity-service`, `taskflow-frontend`), taggate `latest` e con il commit SHA.

### Setup di `docker.yml` (da fare una sola volta)

**1. Genera un Access Token su Docker Hub**
- [hub.docker.com](https://hub.docker.com) → **Account Settings → Security → New Access Token**
- Nome a piacere (es. `taskflow-github-actions`), permessi **Read, Write**
- Copia il token — si vede solo in questo momento

**2. Aggiungi due secret al repository GitHub**
- Sul repository → **Settings → Secrets and variables → Actions → New repository secret**
- `DOCKERHUB_USERNAME` → il tuo username Docker Hub
- `DOCKERHUB_TOKEN` → il token copiato al passo 1

**3. Push su `main`**
Da questo momento, ogni push su `main` fa partire entrambi i workflow automaticamente — seguili dal tab **Actions** del repository su GitHub.

Senza questi secret configurati, `ci.yml` funziona comunque normalmente (i test partono lo stesso) — solo il job di build/push di `docker.yml` fallirebbe al login su Docker Hub.

## Deploy su Kubernetes locale (Multipass + k3s)

Guida completa per far girare l'app su un cluster k3s reale a 3 nodi (1 master + 2 worker), partendo da zero. Pensata per essere seguita da chi non ha mai lanciato questo progetto — utile per rifare il deploy da capo o per chi deve solo valutare/provare il progetto.

### Prerequisiti

- **Multipass** installato ([multipass.run](https://multipass.run)) — su Windows usa il backend VirtualBox (Hyper-V spesso non disponibile su Windows Home)
- **Terraform** installato
- **WSL2** con una distribuzione Linux (es. Ubuntu) con **Ansible** installato — Ansible non gira nativamente su Windows
- Non serve `kubectl` sul PC Windows: in questa guida i comandi Kubernetes girano direttamente sul nodo master tramite Ansible
- Non serve Docker Desktop sul PC che fa il deploy: le immagini sono già pubblicate su Docker Hub da GitHub Actions (vedi sezione **CI/CD** sopra) — serve solo che almeno un push su `main` sia già andato a buon fine prima del primo deploy

### Architettura del deploy

- 3 VM Multipass su rete bridged Wi-Fi (necessaria per farle comunicare tra loro e per raggiungerle da WSL2)
- k3s con **Traefik** come ingress controller (incluso di default in k3s, non lo disabilitiamo)
- Le 4 immagini Docker (3 servizi + frontend) vengono **tirate da Docker Hub** (`giovannitorrisi/taskflow-*:latest`, `imagePullPolicy: Always`) — pubblicate automaticamente da `docker.yml` ad ogni push su `main`. Il cluster non builda né importa nulla localmente.
- Nessuna persistenza dati (Postgres perde i dati se il pod viene ricreato) — scelta accettabile per un progetto didattico

### Passaggi

**1. Crea le 3 VM con Terraform**

```powershell
cd infra/local/terraform
terraform init
terraform apply
```

Conferma con `yes`. Crea `taskflow-master`, `taskflow-worker1`, `taskflow-worker2` (1 CPU, 2GB RAM, 8GB disco ciascuna) su rete bridged Wi-Fi. Ci vogliono un paio di minuti.

**2. Recupera gli IP delle VM**

```powershell
multipass list
```

Annota l'IP di ciascuna VM.

**3. Prepara la chiave SSH per Ansible (dentro WSL2)**

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

**4. Aggiorna l'inventory Ansible**

Apri `infra/local/ansible/inventory.ini` e sostituisci gli IP con quelli ottenuti al passo 2 (sia `ansible_host` che `static_ip` per ogni nodo devono avere lo **stesso valore** — è l'IP DHCP attuale che il passo successivo renderà statico). Controlla anche che `gateway` corrisponda al gateway della tua rete (di solito il primo indirizzo della sottorete, es. `192.168.1.1`).

**5. Configura IP statici** (sopravvivono ai riavvii delle VM)

Da WSL2:

```bash
cd "/mnt/c/Users/<tuo-utente>/Universita/Sistemi cloud/taskflow/infra/local/ansible"
ansible-playbook -i inventory.ini playbook-static-ip.yaml
```

**6. Installa k3s**

```bash
ansible-playbook -i inventory.ini playbook-k3s.yaml
```

Installa k3s server sul master (Traefik incluso) e k3s agent sui worker, poi verifica che tutti i nodi siano `Ready`. Richiede qualche minuto — **meglio lanciarlo direttamente nel terminale** (non tramite un assistente/chat) per evitare timeout.

**7. Copia i manifest Kubernetes sul master e applicali**

```bash
ansible master -i inventory.ini -m copy -a "src='<percorso-progetto>/taskflow/k8s/' dest=/home/ubuntu/k8s/"
ansible master -i inventory.ini -m shell -a 'sudo kubectl apply -f /home/ubuntu/k8s/ --recursive' --become
```

Kubernetes tirerà da solo le 4 immagini da Docker Hub (`imagePullPolicy: Always`) — nessun passaggio di build/import manuale.

> Se la prima esecuzione fallisce con errori tipo `namespace "taskflow" not found` su alcune risorse, è una race condition transitoria (il namespace non è ancora pienamente propagato quando vengono applicate le risorse successive). **Rilancia lo stesso comando** — `kubectl apply` è idempotente, la seconda volta va a buon fine.

**8. Verifica**

```bash
ansible master -i inventory.ini -m shell -a 'sudo kubectl get nodes' --become
ansible master -i inventory.ini -m shell -a 'sudo kubectl get pods -n taskflow' --become
```

Tutti e 3 i nodi devono essere `Ready`, tutti i pod `Running` e `1/1`. Alcuni riavvii iniziali dei pod applicativi sono normali: partono prima che Postgres sia pronto ad accettare connessioni e Kubernetes li riavvia automaticamente finché non si connettono con successo.

**9. Apri l'app**

Vai su `http://<IP-DEL-MASTER>/` nel browser (l'IP di `taskflow-master` ottenuto al passo 2).

### Aggiornare l'app dopo una modifica al codice

Non serve più rifare il deploy da capo:

```bash
git push origin main   # CI/CD builda e pubblica le nuove immagini su Docker Hub automaticamente
```

Poi, quando `docker.yml` è verde su GitHub, sul cluster:

```bash
ansible master -i inventory.ini -m shell -a 'sudo kubectl rollout restart deployment -n taskflow' --become
```

Questo forza ogni Deployment a ricreare i pod, tirando la versione più recente di `:latest` da Docker Hub grazie a `imagePullPolicy: Always`.

### Fermare e riprendere il cluster

```powershell
multipass stop taskflow-master taskflow-worker1 taskflow-worker2
# ... in un secondo momento ...
multipass start taskflow-master taskflow-worker1 taskflow-worker2
```

Grazie agli IP statici configurati al passo 5, il cluster riparte con gli stessi indirizzi e k3s si riavvia da solo (è un servizio systemd) — non serve rifare l'installazione.

### Distruggere tutto

```powershell
cd infra/local/terraform
terraform destroy
```

Cancella le 3 VM. Verifica con `multipass list` che non resti nulla.

## Deploy su AWS (EC2 + k3s + RDS)

Stessa applicazione, stessi manifest Kubernetes (a parte il database), ma su infrastruttura cloud reale invece che VM locali. **Comporta costi orari reali** — vedi la sezione costi in fondo, e ricordati sempre il cleanup a fine sessione.

### Prerequisiti

- **AWS CLI configurata** (`aws sts get-caller-identity` deve rispondere) con una regione di default (qui si usa `eu-west-1`)
- **Terraform** installato
- **Un Key Pair EC2 già creato** su AWS (nome di default nel codice: `aws-learning-key`) e il file `.pem` corrispondente sul disco
- **WSL2** con Ansible installato (stesso identico requisito della Fase locale)
- Le immagini Docker devono già esistere su Docker Hub (almeno un push su `main` con `docker.yml` verde) — altrimenti i pod restano in `ImagePullBackOff`

### Architettura del deploy

- **VPC dedicata** (`10.0.0.0/16`, non quella default di AWS): 1 subnet pubblica (le 3 EC2) + 2 subnet private in due Availability Zone diverse (richiesto da RDS anche per una singola istanza)
- **RDS PostgreSQL** (`db.t3.micro`) in subnet privata, **non pubblicamente accessibile** — il security group accetta connessioni sulla porta 5432 solo dal security group del cluster k3s, non da internet
- Un solo database RDS con **3 database logici** (`users_db`, `projects_db`, `activities_db`), stesso principio già adottato in locale — non 3 istanze separate, per contenere i costi
- Cluster k3s a 3 nodi su EC2 (master `t3.small` + 2 worker `t3.micro`), **Traefik** attivo come ingress controller, stessa configurazione della Fase locale
- Immagini Docker **tirate da Docker Hub** (`imagePullPolicy: Always`) — identico alla Fase locale, nessun import manuale nemmeno qui

### Passaggi

**1. Scegli una password per il database e creala in un file non versionato**

```bash
cd infra/aws/terraform
echo 'db_password = "una-password-a-piacere"' > terraform.tfvars
```

`terraform.tfvars` è già in `.gitignore` — non finisce mai nel repository.

**2. Crea VPC, RDS e le 3 EC2 con Terraform**

```bash
terraform init
terraform apply
```

Conferma con `yes`. La RDS impiega 5-10 minuti a diventare disponibile; le EC2 sono pronte in meno di un minuto. **Meglio lanciarlo direttamente nel terminale**, non tramite un assistente, per evitare timeout.

**3. Annota gli output**

```bash
terraform output
```

Servono `master_public_ip`, `master_private_ip`, `worker_public_ips`, `rds_address`.

**4. Verifica/copia la chiave `.pem` in WSL2**

```bash
cp /mnt/c/Users/<tuo-utente>/.ssh/aws-learning-key.pem ~/.ssh/
chmod 600 ~/.ssh/aws-learning-key.pem
```

**5. Aggiorna `infra/aws/ansible/inventory.ini`** con gli IP e l'endpoint RDS ottenuti al passo 3 (`ansible_host`/`k3s_private_ip` per il master, `ansible_host` per i worker, `rds_address`, `db_password` — la stessa scelta al passo 1).

**6. Installa k3s**

```bash
cd ../ansible
ansible-playbook -i inventory.ini playbook-k3s.yaml
```

Stesso comportamento della Fase locale (Traefik incluso) — lanciarlo direttamente nel terminale, richiede qualche minuto.

**7. Crea i database applicativi sulla RDS**

```bash
ansible-playbook -i inventory.ini playbook-rds-init.yaml
```

RDS non supporta uno script di init come il container Postgres locale: questo playbook installa `psql` sul master e crea `users_db`/`projects_db`/`activities_db` (idempotente, si può rilanciare senza problemi).

**8. Aggiorna `infra/aws/k8s/secret.yaml`** con l'endpoint RDS reale, la password scelta al passo 1, e un `JWT_SECRET` a piacere (es. generato con `python -c "import secrets; print(secrets.token_urlsafe(32))"`).

**9. Copia i manifest sul master e applicali**

```bash
ansible master -i inventory.ini -m copy -a "src='<percorso-progetto>/taskflow/infra/aws/k8s/' dest=/home/ubuntu/k8s/"
ansible master -i inventory.ini -m shell -a 'sudo kubectl apply -f /home/ubuntu/k8s/ --recursive' --become
```

> Stessa race condition transitoria vista nella Fase locale: se la prima esecuzione dà errori `namespace "taskflow" not found`, rilancia lo stesso comando.

**10. Verifica**

```bash
ansible master -i inventory.ini -m shell -a 'sudo kubectl get nodes' --become
ansible master -i inventory.ini -m shell -a 'sudo kubectl get pods -n taskflow' --become
```

**11. Apri l'app**

`http://<master_public_ip>/`

### Nota tecnica: connessioni RDS "stale"

Una connessione SQLAlchemy lasciata inattiva troppo a lungo (comune con RDS) può fallire al primo utilizzo successivo con `SSL error: decryption failed or bad record mac`. I 3 servizi backend configurano `SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}` per testare ogni connessione prima di usarla e sostituirla trasparentemente se non più valida — se lavori su questi servizi, mantieni questa opzione.

### Aggiornare l'app dopo una modifica al codice

Identico alla Fase locale:

```bash
git push origin main   # CI/CD pubblica le nuove immagini su Docker Hub
ansible master -i inventory.ini -m shell -a 'sudo kubectl rollout restart deployment -n taskflow' --become
```

### Cleanup — obbligatorio a fine sessione

A differenza delle VM Multipass, qui **non conviene "fermare e riprendere"**: le EC2 senza un IP elastico cambiano indirizzo ad ogni riavvio (rompendo l'inventory), e RDS continua comunque a costare mentre esiste. La pratica corretta è distruggere tutto a fine sessione e ricreare da capo la prossima volta:

```bash
cd infra/aws/terraform
terraform destroy
```

Conferma con `yes`. Verifica su console AWS (EC2 e RDS) che non resti nulla.

### Costo stimato

| Risorsa | Tipo | Costo/ora |
|---|---|---|
| Master | t3.small | ~$0.023 |
| Worker × 2 | t3.micro | ~$0.013 × 2 |
| RDS | db.t3.micro | idoneo al free tier nei primi 12 mesi, altrimenti ~$0.017 |
| **Totale** | | **~$0.066/ora** senza free tier |

Per una sessione di poche ore: pochi centesimi. Non lasciare le risorse attive inutilmente.

## Struttura

```
taskflow/
├── services/
│   ├── user-service/
│   ├── project-service/
│   └── activity-service/
├── frontend/
├── k8s/                  # Manifest Kubernetes (namespace, secret, deployment/service per servizio, ingress) — immagini da Docker Hub
├── infra/
│   ├── local/
│   │   ├── terraform/    # Provisioning VM Multipass (k3s locale)
│   │   └── ansible/      # Configurazione IP statici, installazione k3s
│   └── aws/
│       ├── terraform/    # VPC, security group, RDS, 3x EC2
│       ├── ansible/      # Installazione k3s, init database su RDS
│       └── k8s/          # Manifest Kubernetes per AWS (secret con endpoint RDS, niente postgres/)
├── docker-compose.yml
└── .github/workflows/    # CI/CD: test automatici + build/push immagini su Docker Hub
```
