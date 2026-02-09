#!/bin/bash
# Script de test pour le workflow QE_to_TCAD

echo "=== Test du workflow QE to TCAD ==="
echo ""

# Activation de l'environnement virtuel
echo "1. Activation de l'environnement virtuel..."
source .venv/bin/activate

# Test avec différents éléments
elements=("Si" "Al")

for element in "${elements[@]}"; do
    echo ""
    echo "=== Test avec $element ==="
    
    # Exécution du fetcher
    python fetcher.py "$element"
    
    # Vérification des fichiers générés
    if [ -f "${element}.scf.in" ]; then
        echo "✓ Fichier ${element}.scf.in généré avec succès"
        echo "  Contenu (premières lignes):"
        head -20 "${element}.scf.in"
    else
        echo "✗ Erreur: ${element}.scf.in non généré"
    fi
    
    echo ""
done

# Liste des fichiers dans pseudopotentials
echo "=== Pseudopotentiels disponibles ==="
ls -lh pseudopotentials/

echo ""
echo "=== Test terminé ==="
