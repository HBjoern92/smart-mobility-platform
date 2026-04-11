# Smart Mobility Platform

Eine verteilte Ride-Sharing-Plattform (ähnlich wie Uber) als Microservice-Architektur mit Kafka, SAGA-Pattern und Kubernetes-Deployment.

---

## Architektur-Übersicht

```
Customer / Driver
       │
       ▼ REST
  API Gateway :8000
       │
       ├──► Ride Service    :8001  (PostgreSQL)
       ├──► Driver Service  :8002  (Redis)
       ├──► Payment Service :8003  (in-memory)
       └──► Analytics       :8004  (MongoDB + Spark)

Alle Services kommunizieren asynchron über Kafka
```

### Microservices

| Service | Port | Datenbank | Aufgabe |
|---|---|---|---|
| API Gateway | 8000 | – | Einziger Eintrittspunkt, leitet alle Requests weiter |
| Ride Service | 8001 | PostgreSQL | Fahrten buchen, SAGA orchestrieren, Positionen tracken |
| Driver Service | 8002 | Redis | Fahrerverwaltung, Verfügbarkeit, Zuweisung |
| Payment Service | 8003 | In-Memory | Zahlungsabwicklung (simuliert) |
| Analytics Service | 8004 | MongoDB | Spark Batch Job, KPI-Berechnung |
| Frontend | 3000 | – | Dashboard (Vanilla HTML/JS) |

---

## SAGA-Pattern

Die Fahrtbuchung ist eine verteilte Transaktion über 3 Schritte:

```
Schritt 1:  Ride Service    → publiziert ride.created
Schritt 2:  Payment Service → hört ride.created
                            → publiziert payment.processed  ✅
                            → publiziert payment.failed     ❌
Schritt 3:  Driver Service  → hört payment.processed (implizit via ride.created)
                            → publiziert driver.assigned    ✅
                            → publiziert driver.not_found   ❌
```

### Compensating Transactions (Fehlerfall)

| Fehler | Auslöser | Kompensation |
|---|---|---|
| `payment.failed` | Payment Service | Ride Service setzt Fahrt auf CANCELLED |
| `driver.not_found` | Driver Service | Ride Service setzt Fahrt auf CANCELLED |
| `ride.cancelled` | Ride Service | Payment Service erstattet Zahlung (REFUNDED) |

### Kafka Topics

| Topic | Publisher | Subscriber |
|---|---|---|
| `ride.created` | Ride Service | Payment Service, Driver Service |
| `payment.processed` | Payment Service | Ride Service |
| `payment.failed` | Payment Service | Ride Service |
| `driver.assigned` | Driver Service | Ride Service |
| `driver.not_found` | Driver Service | Ride Service |
| `ride.completed` | Driver Service | Ride Service |
| `ride.cancelled` | Ride Service | Payment Service, Driver Service |
| `location.updated` | Ride Service | (Frontend polling) |

---

## Ordnerstruktur

```
smart-mobility/
├── docker-compose.yml
├── README.md
├── k8s/
│   ├── 00-configmap.yaml
│   ├── 01-secrets.yaml
│   ├── 02-postgres.yaml
│   ├── 03-redis.yaml
│   ├── 04-mongodb.yaml
│   ├── 05-ride-service.yaml
│   ├── 06-driver-service.yaml
│   ├── 07-payment-service.yaml
│   ├── 08-api-gateway.yaml
│   ├── 09-analytics-service.yaml
│   ├── 10-frontend.yaml
│   ├── 11-ingress.yaml
│   └── rolling-update-demo.sh
├── ride-service/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env
│   └── app/
│       ├── config.py
│       ├── main.py
│       ├── models.py
│       ├── schemas.py
│       ├── pricing.py
│       ├── kafka_producer.py
│       └── kafka_consumer.py
├── driver-service/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env
│   └── app/
│       ├── config.py
│       ├── main.py
│       ├── schemas.py
│       ├── store.py
│       ├── kafka_producer.py
│       └── kafka_consumer.py
├── payment-service/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env
│   └── app/
│       ├── config.py
│       ├── main.py
│       ├── schemas.py
│       ├── store.py
│       ├── kafka_producer.py
│       └── kafka_consumer.py
├── api-gateway/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env
│   └── app/
│       ├── config.py
│       ├── main.py
│       ├── client.py
│       ├── routes_rides.py
│       ├── routes_drivers.py
│       └── routes_payments.py
├── analytics-service/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env
│   └── app/
│       ├── config.py
│       ├── main.py
│       ├── mongo.py
│       ├── spark_job.py
│       └── scheduler.py
└── frontend/
    ├── Dockerfile
    ├── index.html
    └── nginx.conf
```

---

## Lokale Entwicklung

### Voraussetzungen

- Docker Desktop installiert
- Python 3.11+
- kubectl installiert

### Alles starten mit docker-compose

```bash
cd smart-mobility
docker-compose up --build
```

Danach sind folgende URLs verfügbar:

| URL | Beschreibung |
|---|---|
| http://localhost:3000 | Frontend Dashboard |
| http://localhost:8000/docs | API Gateway Swagger UI |
| http://localhost:8001/docs | Ride Service Swagger UI |
| http://localhost:8002/docs | Driver Service Swagger UI |
| http://localhost:8003/docs | Payment Service Swagger UI |
| http://localhost:8004/docs | Analytics Service Swagger UI |
| http://localhost:8080 | Kafka UI |

### Services einzeln starten (ohne Docker)

```bash
# Terminal 1 – Ride Service
cd ride-service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# Terminal 2 – Driver Service
cd driver-service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8002

# Terminal 3 – Payment Service
cd payment-service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8003

# Terminal 4 – API Gateway
cd api-gateway
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

---

## Deployment auf Kubernetes (Uni-Cluster)

### Voraussetzung: kubeconfig einrichten

```bash
cp gruppe-3-kubeconfig.yaml ~/.kube/config
kubectl get nodes   # Verbindung testen
```

> Cluster ist nur im Uni-Netzwerk / VPN erreichbar: `141.72.176.21:6443`

### Docker Images bauen

```bash
cd smart-mobility

docker build -t ride-service:latest    ./ride-service
docker build -t driver-service:latest  ./driver-service
docker build -t payment-service:latest ./payment-service
docker build -t api-gateway:latest     ./api-gateway
docker build -t analytics-service:latest ./analytics-service
docker build -t frontend:latest        ./frontend
```

### Images in den Cluster laden

```bash
# Für k3s (wie der Uni-Cluster):
docker save ride-service:latest    | kubectl exec -i $(kubectl get pod -l app=ride-service -o jsonpath='{.items[0].metadata.name}') -- ctr images import -

# Einfacher: direkt auf dem Cluster-Node bauen
# → Images in eine Registry pushen (z.B. Docker Hub) und
#   imagePullPolicy: Always in den YAML-Dateien setzen
```

### Alles deployen

```bash
kubectl apply -f k8s/
```

### Status prüfen

```bash
kubectl get pods
kubectl get services
kubectl get ingress
```

### Logs eines Services anzeigen

```bash
kubectl logs -f deployment/ride-service
kubectl logs -f deployment/driver-service
```

---

## Zero-Downtime Rolling Update

Der Ride Service ist mit Rolling Update konfiguriert (`maxSurge: 1`, `maxUnavailable: 0`). Demo für die Präsentation:

```bash
chmod +x k8s/rolling-update-demo.sh
./k8s/rolling-update-demo.sh
```

Manuell:
```bash
# Neues Image deployen
kubectl set image deployment/ride-service ride-service=ride-service:v2

# Update-Fortschritt beobachten
kubectl rollout status deployment/ride-service

# Bei Problemen: Rollback
kubectl rollout undo deployment/ride-service
```

---

## Typischer Ablauf (Happy Path)

```bash
# 1. Fahrer registrieren
curl -X POST http://localhost:8000/drivers \
  -H "Content-Type: application/json" \
  -d '{"driver_id": "driver-01", "name": "Max Mustermann"}'

# 2. Fahrt buchen
curl -X POST http://localhost:8000/rides \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alice",
    "start_lat": 48.1351, "start_lon": 11.5820,
    "end_lat":   48.1900, "end_lon":   11.6200
  }'

# 3. Status abfragen (RIDE_ID aus Schritt 2 einsetzen)
curl http://localhost:8000/rides/{RIDE_ID}

# 4. Fahrt abschließen (wenn Status = DRIVER_ASSIGNED)
curl -X POST http://localhost:8000/drivers/rides/{RIDE_ID}/complete \
  -H "Content-Type: application/json" \
  -d '{"driver_id": "driver-01"}'

# 5. Zahlung prüfen
curl http://localhost:8000/payments/{RIDE_ID}
```

## SAGA Fehlerfall testen

```bash
# In payment-service/.env setzen:
SIMULATE_FAILURE_RATE=0.8

# Dann Ride buchen → 80% der Zahlungen schlagen fehl
# → Ride Status wird automatisch CANCELLED
```

---

## Vereinfachungen (laut Aufgabenstellung)

- Keine echte Authentifizierung – Benutzername als Query-Parameter
- Fahrzeit/Preis via Haversine-Formel (Luftlinie) + konstanter Geschwindigkeit (40 km/h)
- Bezahlung simuliert (`return true`) – aber vollständig in SAGA eingebunden
- Nicht alle Fehlerfälle abgedeckt – nur die geforderten SAGA-Kompensationen

---

## Abgabe-Checkliste

- [x] Microservice-Zerlegung (5 Services + Gateway + Frontend)
- [x] Synchrone Kommunikation (REST via API Gateway)
- [x] Asynchrone Kommunikation (Kafka Event Streaming)
- [x] SAGA-Transaktion mit 3 Schritten + Compensating Transactions
- [x] Kommunikationsdiagramm (siehe Architektur-Übersicht)
- [x] Dockerfile für jeden Microservice
- [x] Kubernetes Deployment (alle Manifeste in `k8s/`)
- [x] Datenbank als eigenes Deployment (PostgreSQL, Redis, MongoDB)
- [x] Zero-Downtime Rolling Update (ride-service, `k8s/05-ride-service.yaml`)
- [x] Spark Batch Job für Analytics
- [ ] GitHub Repository mit Code
- [ ] Präsentation + README
