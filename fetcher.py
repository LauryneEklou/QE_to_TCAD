#!/usr/bin/env python3
import os
import sys
import argparse
import logging
import requests
from mp_api.client import MPRester
from pymatgen.io.cif import CifWriter
from pymatgen.io.vasp import Poscar
from pymatgen.io.pwscf import PWInput
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LOG = logging.getLogger("fetcher")

# UPDATED: Direct download URLs for pseudopotentials
UPF_BASE_URLS = [
    "https://pseudopotentials.quantum-espresso.org/upf_files/{}", # Official QE repo
    "https://raw.githubusercontent.com/pseudo-dojo/pseudo-dojo/main/pseudos/nc-sr-04_pbe_standard/{}", # PseudoDojo (check suffix)
    "https://raw.githubusercontent.com/dalcorso/pslibrary/master/upf/{}"  # PSLibrary (GitHub)
]

UPF_SUFFIXES = [
    ".UPF",
    ".upf",
    ".pbe-n-kjpaw_psl.1.0.0.UPF",
    ".pbe-n-rrkjus_psl.1.0.0.UPF",
    ".pbe-dn-kjpaw_psl.1.0.0.UPF", 
    ".pbe-dn-rrkjus_psl.1.0.0.UPF",
    ".pbe-dnl-kjpaw_psl.1.0.0.UPF",
    ".pbe-sp-van_ak.UPF",
    ".pbe-hgh.UPF",
    "_oncv_psp8.upf"
]

# Fallback dictionary for common elements (using Official QE Repository)
KNOWN_UPF_URLS = {
    "Si": "https://pseudopotentials.quantum-espresso.org/upf_files/Si.pbe-n-rrkjus_psl.1.0.0.UPF",
    "Ga": "https://pseudopotentials.quantum-espresso.org/upf_files/Ga.pbe-dn-kjpaw_psl.1.0.0.UPF",
    "N":  "https://pseudopotentials.quantum-espresso.org/upf_files/N.pbe-n-kjpaw_psl.1.0.0.UPF",
    "Al": "https://pseudopotentials.quantum-espresso.org/upf_files/Al.pbe-n-kjpaw_psl.1.0.0.UPF",
    "C":  "https://pseudopotentials.quantum-espresso.org/upf_files/C.pbe-n-kjpaw_psl.1.0.0.UPF",
    "O":  "https://pseudopotentials.quantum-espresso.org/upf_files/O.pbe-n-kjpaw_psl.1.0.0.UPF",
    "Na": "https://pseudopotentials.quantum-espresso.org/upf_files/Na.pbe-sp-van_ak.UPF",
    "Zn": "https://pseudopotentials.quantum-espresso.org/upf_files/Zn.pbe-dnl-kjpaw_psl.1.0.0.UPF",
}

def download_upf(element, output_dir):
    """Downloads a UPF file for the given element."""
    # 1. Try known URLs first for reliability
    if element in KNOWN_UPF_URLS:
        url = KNOWN_UPF_URLS[element]
        try:
            LOG.info(f"Attempting download from known URL for {element}...")
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                local_filename = os.path.join(output_dir, f"{element}.UPF")
                with open(local_filename, "wb") as f:
                    f.write(response.content)
                LOG.info(f"Successfully downloaded {local_filename} (Standard PBE)")
                return local_filename
            else:
                LOG.warning(f"Known URL failed with status {response.status_code}. Trying generic search...")
        except requests.RequestException as e:
            LOG.warning(f"Known URL connection failed: {e}")

    # 2. Generic search
    for base_url in UPF_BASE_URLS:
        for suffix in UPF_SUFFIXES:
            filename_remote = f"{element}{suffix}"
            url = base_url.format(filename_remote)
            try:
                # LOG.info(f"Checking: {url}")
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    local_filename = os.path.join(output_dir, f"{element}.UPF")
                    with open(local_filename, "wb") as f:
                        f.write(response.content)
                    LOG.info(f"Successfully downloaded {local_filename} from {url}")
                    return local_filename
            except requests.RequestException:
                continue
    
    LOG.error(f"Could not download UPF for element {element} from any checked source. Please download it manually.")
    return None

def get_most_stable_structure(api_key, formula):
    """Fetches the most stable structure for a given formula."""
    try:
        with MPRester(api_key) as mpr:
            # Search for materials with the given formula
            # UPDATED: Use mpr.materials.summary and correct field energy_above_hull
            docs = mpr.materials.summary.search(formula=formula, fields=["material_id", "structure", "energy_above_hull", "is_stable"])

            if not docs:
                LOG.error(f"No materials found for formula {formula}")
                return None

            # Sort by energy above hull (stability)
            # We want the one closest to 0 (stable)
            sorted_docs = sorted(docs, key=lambda x: x.energy_above_hull)
            best_doc = sorted_docs[0]

            LOG.info(f"Found {len(docs)} structures. Selected most stable: {best_doc.material_id} (energy_above_hull={best_doc.energy_above_hull})")
            return best_doc.structure

    except Exception as e:
        LOG.error(f"Error communicating with Materials Project: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Fetch structure and pseudopotentials for a chemical formula.")
    parser.add_argument("formula", type=str, help="Chemical formula (e.g., Si, GaN)")
    # Defaults to env var, then to the provided key if env var is missing
    default_key = os.environ.get("MP_API_KEY", "GBCjLUpcDdcfYKnksM5lF4yVIqD5dtF7")
    parser.add_argument("--api_key", type=str, default=default_key, help="Materials Project API Key")
    parser.add_argument("--out_dir", type=str, default=".", help="Output directory")

    args = parser.parse_args()

    if not args.api_key:
        LOG.error("API Key is required. Set MP_API_KEY env var or pass --api_key.")
        sys.exit(1)

    if not os.path.exists(args.out_dir):
        os.makedirs(args.out_dir)
    
    # Create pseudopotentials subdirectory
    upf_dir = os.path.join(args.out_dir, "pseudopotentials")
    if not os.path.exists(upf_dir):
        os.makedirs(upf_dir)

    # 1. Fetch Structure
    structure = get_most_stable_structure(args.api_key, args.formula)
    if not structure:
        sys.exit(1)

    # 2. Save Structure
    # Save as CIF
    cif_path = os.path.join(args.out_dir, "structure.cif")
    try:
        CifWriter(structure).write_file(cif_path)
        LOG.info(f"Structure saved to {cif_path}")
    except Exception as e:
        LOG.error(f"Failed to save CIF: {e}")

    # Save as POSCAR (useful for VASP or conversion tools)
    poscar_path = os.path.join(args.out_dir, "POSCAR")
    try:
        Poscar(structure).write_file(poscar_path)
        LOG.info(f"Structure saved to {poscar_path}")
    except Exception as e:
        LOG.error(f"Failed to save POSCAR: {e}")

    # 3. Download UPFs
    elements = [str(el) for el in structure.composition.elements]
    LOG.info(f"Elements in structure: {elements}")

    for el in elements:
        download_upf(el, upf_dir)

    # 4. Generate QE input file
    qe_input_path = os.path.join(args.out_dir, f"{args.formula}.scf.in")
    try:
        LOG.info("Generating Quantum Espresso input file...")
        
        # Create pseudo dictionary from downloaded files
        pseudo_dict = {}
        for el in elements:
            upf_file = None
            # Look for the downloaded UPF file
            for file in os.listdir(upf_dir):
                if file.startswith(el) and file.endswith('.UPF'):
                    upf_file = file
                    break
            if upf_file:
                pseudo_dict[el] = upf_file
            else:
                LOG.warning(f"No UPF found for {el}, QE input generation may fail")
        
        # Set up control parameters
        control = {
            'calculation': 'scf',
            'restart_mode': 'from_scratch',
            'prefix': args.formula,
            'pseudo_dir': './pseudopotentials',
            'outdir': './out/',
            'verbosity': 'high',
        }
        
        # System parameters
        system = {
            'ecutwfc': 50.0,
            'ecutrho': 200.0,
            'occupations': 'smearing',
            'smearing': 'marzari-vanderbilt',
            'degauss': 0.02,
        }
        
        # Electrons parameters
        electrons = {
            'conv_thr': 1.0e-8,
            'mixing_beta': 0.7,
        }
        
        # Create PWInput
        pw_input = PWInput(
            structure=structure,
            pseudo=pseudo_dict,
            control=control,
            system=system,
            electrons=electrons,
            kpoints_mode='automatic',
            kpoints_grid=(4, 4, 4, 1, 1, 1),
        )
        
        # Write to file
        pw_input.write_file(qe_input_path)
        LOG.info(f"QE input file saved to {qe_input_path}")
        
    except Exception as e:
        LOG.error(f"Failed to generate QE input file: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

