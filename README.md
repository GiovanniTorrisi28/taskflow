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

## Struttura

```
taskflow/
├── services/
│   ├── user-service/
│   ├── project-service/
│   └── activity-service/
├── frontend/
├── infra/          # Terraform + Ansible (fasi successive: K8s locale, poi AWS)
├── docker-compose.yml
└── .github/workflows/   # CI/CD 
```
