#!/bin/bash
# =============================================================
# Zero-Downtime Rolling Update Demo
# Demonstriert für die Präsentation wie ein Update ohne
# Downtime auf dem ride-service durchgeführt wird.
#
# Voraussetzung:
#   - kubectl konfiguriert (gruppe-3-kubeconfig.yaml)
#   - ride-service läuft im Cluster
# =============================================================

set -e

echo "========================================"
echo " Smart Mobility – Rolling Update Demo"
echo "========================================"
echo ""

# 1. Aktuellen Status zeigen
echo ">>> Aktueller Status der Pods:"
kubectl get pods -l app=ride-service
echo ""

# 2. Aktuelles Image zeigen
echo ">>> Aktuelles Image:"
kubectl get deployment ride-service \
  -o jsonpath='{.spec.template.spec.containers[0].image}'
echo ""
echo ""

# 3. Continuous health check im Hintergrund starten
echo ">>> Starte Health-Check im Hintergrund (alle 1s)..."
(
  while true; do
    STATUS=$(kubectl exec -it \
      $(kubectl get pod -l app=ride-service -o jsonpath='{.items[0].metadata.name}') \
      -- wget -qO- http://localhost:8001/health 2>/dev/null || echo "CHECKING...")
    echo "  [$(date +%H:%M:%S)] $STATUS"
    sleep 1
  done
) &
HEALTH_PID=$!

sleep 2

# 4. Rolling Update durchführen
# Strategie: maxSurge=1, maxUnavailable=0 → immer min. 2 Pods aktiv
echo ""
echo ">>> Starte Rolling Update auf ride-service:v2 ..."
kubectl set image deployment/ride-service \
  ride-service=ride-service:v2

# 5. Update-Verlauf beobachten
echo ""
echo ">>> Update-Verlauf (kubectl rollout status):"
kubectl rollout status deployment/ride-service

# 6. Health-Check stoppen
kill $HEALTH_PID 2>/dev/null

echo ""
echo ">>> Pods nach dem Update:"
kubectl get pods -l app=ride-service

echo ""
echo ">>> Deployment History:"
kubectl rollout history deployment/ride-service

echo ""
echo "========================================"
echo " Update erfolgreich – kein Downtime!"
echo "========================================"
echo ""
echo "Zum Rollback bei Problemen:"
echo "  kubectl rollout undo deployment/ride-service"
