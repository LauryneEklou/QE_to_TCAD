#!/usr/bin/env python3
"""
Quantum Espresso Input Generator
Converts crystal structures to QE input files (.in) with automatic pseudopotential linking
"""
import os
import sys
import argparse
import logging
from pathlib import Path
from pymatgen.core import Structure
from pymatgen.io.pwscf import PWInput

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LOG = logging.getLogger("qe_input_generator")


def find_pseudopotential(element, pseudo_dir="./pseudopotentials"):
    """
    Find the pseudopotential file for a given element.
    
    Args:
        element: Chemical symbol (e.g., 'Si', 'Al')
        pseudo_dir: Directory containing .UPF files
        
    Returns:
        Filename of the pseudopotential or None if not found
    """
    pseudo_path = Path(pseudo_dir)
    if not pseudo_path.exists():
        LOG.warning(f"Pseudopotential directory {pseudo_dir} does not exist")
        return None

    # Pattern: Element.*.UPF or Element.UPF
    patterns = [
        f"{element}.UPF",
        f"{element}.upf",
    ]
    
    for pattern in patterns:
        for upf_file in pseudo_path.glob(f"{element}*.UPF"):
            LOG.info(f"Found pseudopotential for {element}: {upf_file.name}")
            return upf_file.name
        for upf_file in pseudo_path.glob(f"{element}*.upf"):
            LOG.info(f"Found pseudopotential for {element}: {upf_file.name}")
            return upf_file.name
    
    LOG.warning(f"No pseudopotential found for element {element} in {pseudo_dir}")
    return None


def get_atomic_mass(element):
    """Get atomic mass for common elements (simplified)."""
    from pymatgen.core import Element
    return Element(element).atomic_mass


def generate_qe_input(structure_file, output_file="generated_inputs/pwscf.in", 
                      calculation_type="scf", pseudo_dir="./pseudopotentials",
                      ecutwfc=50.0, ecutrho=None, k_points=(4, 4, 4)):
    """
    Generate Quantum Espresso input file from crystal structure.
    
    Args:
        structure_file: Path to structure file (CIF, POSCAR, etc.)
        output_file: Output .in file path
        calculation_type: Type of calculation ('scf', 'relax', 'vc-relax', 'nscf')
        pseudo_dir: Directory containing pseudopotentials
        ecutwfc: Kinetic energy cutoff for wavefunctions (Ry)
        ecutrho: Kinetic energy cutoff for charge density (Ry), defaults to 4*ecutwfc
        k_points: K-points grid (tuple of 3 integers)
        
    Returns:
        Path to generated input file
    """
    LOG.info(f"Reading structure from {structure_file}")
    
    # Load structure using pymatgen
    try:
        structure = Structure.from_file(structure_file)
    except Exception as e:
        LOG.error(f"Failed to read structure file: {e}")
        return None
    
    # Get unique elements
    elements = [str(el) for el in structure.composition.elements]
    LOG.info(f"Elements in structure: {elements}")
    
    # Find pseudopotentials for each element
    pseudo_dict = {}
    for el in elements:
        upf_file = find_pseudopotential(el, pseudo_dir)
        if upf_file:
            pseudo_dict[el] = upf_file
        else:
            LOG.error(f"Missing pseudopotential for {el}. Cannot generate input file.")
            return None
    
    LOG.info(f"Pseudopotentials: {pseudo_dict}")
    
    # Set default ecutrho if not provided
    if ecutrho is None:
        ecutrho = 4 * ecutwfc
    
    # Prepare control parameters
    control = {
        'calculation': calculation_type,
        'restart_mode': 'from_scratch',
        'prefix': structure.composition.reduced_formula,
        'pseudo_dir': str(Path(pseudo_dir).resolve()),
        'outdir': str((Path.cwd() / 'out').resolve()),
        'verbosity': 'high',
    }
    
    # System parameters
    system = {
        'ecutwfc': ecutwfc,
        'ecutrho': ecutrho,
        'occupations': 'smearing',
        'smearing': 'marzari-vanderbilt',
        'degauss': 0.02,
    }
    
    # For metals, might need different occupation
    # This is a simplified heuristic
    if any(el in ['Al', 'Cu', 'Ag', 'Au', 'Fe', 'Ni', 'Co'] for el in elements):
        system['occupations'] = 'smearing'
        system['smearing'] = 'marzari-vanderbilt'
        system['degauss'] = 0.02
    
    # Electrons parameters
    electrons = {
        'conv_thr': 1.0e-8,
        'mixing_beta': 0.7,
    }
    
    # Ions parameters (for relax calculations)
    ions = {}
    if calculation_type in ['relax', 'vc-relax']:
        ions = {
            'ion_dynamics': 'bfgs',
        }
    
    # Cell parameters (for vc-relax)
    cell = {}
    if calculation_type == 'vc-relax':
        cell = {
            'cell_dynamics': 'bfgs',
        }
    
    # Create PWInput object
    try:
        # Build the input dictionary manually for better control
        pw_input = PWInput(
            structure=structure,
            pseudo=pseudo_dict,
            control=control,
            system=system,
            electrons=electrons,
            ions=ions if ions else None,
            cell=cell if cell else None,
            kpoints_mode='automatic',
            kpoints_grid=k_points + (1, 1, 1),  # Add shifts
        )
        
        # Write to file
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pw_input.write_file(str(output_path))
        LOG.info(f"Successfully generated QE input file: {output_file}")
        
        # Display summary
        LOG.info(f"  Calculation type: {calculation_type}")
        LOG.info(f"  Number of atoms: {len(structure)}")
        LOG.info(f"  Number of species: {len(elements)}")
        LOG.info(f"  Energy cutoff (wfc): {ecutwfc} Ry")
        LOG.info(f"  Energy cutoff (rho): {ecutrho} Ry")
        LOG.info(f"  K-points grid: {k_points}")
        
        return output_file
        
    except Exception as e:
        LOG.error(f"Failed to generate PWInput: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Generate Quantum Espresso input file from crystal structure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python qe_input_generator.py structure.cif
  python qe_input_generator.py POSCAR -o si.scf.in -t relax
  python qe_input_generator.py structure.cif -e 60 -k 6 6 6
        """
    )
    
    parser.add_argument("structure", type=str, 
                       help="Input structure file (CIF, POSCAR, etc.)")
    parser.add_argument("-o", "--output", type=str, default="generated_inputs/pwscf.in",
                       help="Output .in file (default: generated_inputs/pwscf.in)")
    parser.add_argument("-t", "--type", type=str, default="scf",
                       choices=['scf', 'relax', 'vc-relax', 'nscf'],
                       help="Calculation type (default: scf)")
    parser.add_argument("-p", "--pseudo_dir", type=str, default="./pseudopotentials",
                       help="Pseudopotential directory (default: ./pseudopotentials)")
    parser.add_argument("-e", "--ecutwfc", type=float, default=50.0,
                       help="Wavefunction energy cutoff in Ry (default: 50)")
    parser.add_argument("--ecutrho", type=float, default=None,
                       help="Charge density energy cutoff in Ry (default: 4*ecutwfc)")
    parser.add_argument("-k", "--kpoints", type=int, nargs=3, default=[4, 4, 4],
                       metavar=('NX', 'NY', 'NZ'),
                       help="K-points grid (default: 4 4 4)")
    
    args = parser.parse_args()
    
    # Check if structure file exists
    if not os.path.exists(args.structure):
        LOG.error(f"Structure file not found: {args.structure}")
        sys.exit(1)
    
    # Generate input file
    result = generate_qe_input(
        structure_file=args.structure,
        output_file=args.output,
        calculation_type=args.type,
        pseudo_dir=args.pseudo_dir,
        ecutwfc=args.ecutwfc,
        ecutrho=args.ecutrho,
        k_points=tuple(args.kpoints)
    )
    
    if result:
        LOG.info(f"✓ QE input file ready: {result}")
        sys.exit(0)
    else:
        LOG.error("✗ Failed to generate input file")
        sys.exit(1)


if __name__ == "__main__":
    main()
