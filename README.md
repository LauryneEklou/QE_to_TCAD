# QE to TCAD Workflow

Pipeline automatisé pour convertir des structures cristallines en fichiers d'entrée Quantum Espresso.

## Fonctionnalités

### ✅ Étape 1 : Récupération de la structure et des pseudopotentiels
- Téléchargement automatique de la structure cristalline la plus stable depuis Materials Project
- Téléchargement automatique des pseudopotentiels UPF depuis les dépôts officiels
- Sauvegarde en formats CIF et POSCAR
- Organisation automatique des fichiers .UPF dans `pseudopotentials/`

### ✅ Étape 2 : Génération du fichier .in pour Quantum Espresso
- Conversion automatique de la structure en format QE
- Génération des paramètres de contrôle optimisés
- Liaison automatique des pseudopotentiels
- Support de différents types de calculs (scf, relax, vc-relax, nscf)

### ✅ Étape 3 : Exécution des calculs QE (pw.x)
- Lancement de `pw.x` via subprocess
- Gestion des logs (.out/.err) et timeouts
- Détection simple d'erreurs dans la sortie

## Installation

```bash
# Créer l'environnement virtuel
python3 -m venv .venv
source .venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt
```

## Configuration

Créer un fichier `.env` avec votre clé API Materials Project :
```bash
MP_API_KEY=votre_clé_ici
```

## Utilisation

### Workflow complet (recommandé)

```bash
# Active l'environnement virtuel
source .venv/bin/activate

# Récupère la structure, les pseudopotentiels ET génère le fichier .in
python fetcher.py Si
python fetcher.py GaN
python fetcher.py Al
```

**Fichiers générés :**
- `structure.cif` - Structure cristalline au format CIF
- `POSCAR` - Structure au format VASP
- `pseudopotentials/*.UPF` - Pseudopotentiels téléchargés
- `{formule}.scf.in` - Fichier d'entrée Quantum Espresso prêt à l'emploi

### Lancer un calcul Quantum Espresso (pw.x)

```bash
source .venv/bin/activate

# Exemple simple
python qe_runner.py generated_inputs/Si.scf.in

# Exemple MPI + timeout (en secondes)
python qe_runner.py generated_inputs/Si.scf.in --mpi mpirun -np 4 --timeout 7200
```

Les sorties sont écrites dans `qe_runs/` avec des fichiers `.out` et `.err`.

### Générateur d'input QE autonome

Si vous avez déjà une structure, utilisez le générateur directement :

```bash
source .venv/bin/activate

# Génération basique
python qe_input_generator.py structure.cif

# Avec options personnalisées
python qe_input_generator.py structure.cif -o gan.scf.in -t relax -e 60 -k 6 6 6
```

**Options disponibles :**
- `-o, --output` : Nom du fichier de sortie (défaut: pwscf.in)
- `-t, --type` : Type de calcul (scf, relax, vc-relax, nscf)
- `-p, --pseudo_dir` : Répertoire des pseudopotentiels
- `-e, --ecutwfc` : Cutoff énergie ondes de plan (Ry)
- `--ecutrho` : Cutoff densité de charge (Ry)
- `-k, --kpoints` : Grille de points k (ex: 6 6 6)

## Exemples

### Exemple 1 : Silicium

```bash
python fetcher.py Si
```

Génère `Si.scf.in` avec :
- Structure cubique diamant
- Pseudopotentiel PBE standard
- Calcul SCF avec smearing Marzari-Vanderbilt
- Grille k-points 4×4×4

### Exemple 2 : Nitrure de Gallium

```bash
python fetcher.py GaN
```

Génère `GaN.scf.in` avec :
- Structure wurtzite
- Pseudopotentiels pour Ga et N
- Paramètres optimisés pour semi-conducteurs

### Exemple 3 : Relaxation structurale

```bash
python qe_input_generator.py structure.cif -t relax -e 60 -k 8 8 8 -o relax.in
```

## Structure des fichiers

```
QE_to_TCAD/
├── fetcher.py                 # Script principal (structure + UPF + .in)
├── qe_input_generator.py      # Générateur .in autonome
├── qe_runner.py               # Lancement des calculs QE (pw.x)
├── requirements.txt           # Dépendances Python
├── .env                       # Configuration API
├── pseudopotentials/          # Pseudopotentiels UPF
│   ├── Si.UPF
│   ├── Ga.UPF
│   └── N.UPF
├── structure.cif              # Structure cristalline
├── POSCAR                     # Format VASP
└── *.scf.in                   # Fichiers d'entrée QE
```

## Technologies utilisées

- **pymatgen** : Manipulation de structures cristallines et génération PWInput
- **mp-api** : API Materials Project
- **requests** : Téléchargement des pseudopotentiels

## Paramètres par défaut

### Paramètres système
- `ecutwfc` : 50.0 Ry (ondes de plan)
- `ecutrho` : 200.0 Ry (densité de charge, 4×ecutwfc)
- `occupations` : smearing Marzari-Vanderbilt
- `degauss` : 0.02 Ry

### Paramètres de convergence
- `conv_thr` : 1.0e-8
- `mixing_beta` : 0.7

### Grille k-points
- 4×4×4 avec décalage (1,1,1)

## Prochaines étapes

- [ ] Étape 4 : Post-traitement et visualisation
- [ ] Étape 5 : Conversion vers TCAD

## Dépannage

### Problème : Module pymatgen non trouvé
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Problème : Pseudopotentiel manquant
Vérifiez que le dossier `pseudopotentials/` existe et contient les fichiers .UPF nécessaires.

### Problème : Erreur API Materials Project
Vérifiez votre clé API dans le fichier `.env` ou passez-la en argument :
```bash
python fetcher.py Si --api_key VOTRE_CLE_ICI
```
