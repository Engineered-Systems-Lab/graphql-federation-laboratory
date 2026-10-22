"""Validate dataset-003 package semantics/provenance and every page's frozen XSD."""
import argparse
from pathlib import Path
import subprocess
import sys
from xml_validation import COMPONENT, read, schema, cli


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True, type=Path)
    args = parser.parse_args()
    result = subprocess.run([sys.executable, '-B', str(COMPONENT / 'generator/generate_003.py'),
                             'validate', str(args.package)])
    if result.returncode:
        return result.returncode
    xsd = schema()
    for page in range(8):
        xsd.assertValid(read(args.package / f'page-{page:03}.xml'))
    print('PASS: all 8 dataset-003 pages validate against the unchanged frozen XSD.')


if __name__ == '__main__':
    sys.exit(cli(main))
