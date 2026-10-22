"""Shared offline XSD validation. No DTDs, entity or external schema resolution."""
from pathlib import Path
import sys

try:
    from lxml import etree as E
except ImportError as exc:
    raise SystemExit('Missing lxml: install with python -m pip install -r uss-enterprise/requirements.txt') from exc

NS = 'urn:graphql-federation-lab:crew-personnel:v1'
SOAP = 'http://schemas.xmlsoap.org/soap/envelope/'
COMPONENT = Path(__file__).resolve().parents[1]


class DenyExternal(E.Resolver):
    def resolve(self, url, public_id, context):
        raise ValueError(f'External XML resource prohibited: {url}')


def parse(raw):
    parser = E.XMLParser(load_dtd=False, resolve_entities=False, no_network=True,
                         recover=False, remove_blank_text=False)
    parser.resolvers.add(DenyExternal())
    root = E.fromstring(raw, parser)
    # Checking parsed document metadata also catches UTF-16/32 encoded DTDs.
    if root.getroottree().docinfo.doctype:
        raise ValueError('DTD prohibited')
    return root


def read(path):
    return parse(Path(path).read_bytes())


def schema():
    return E.XMLSchema(read(COMPONENT / 'contracts/crew-personnel-v1.xsd'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def expect_schema(xsd, root, valid, label):
    accepted = xsd.validate(root)
    require(accepted == valid,
            f'{label}: unexpected schema {"acceptance" if accepted else "rejection"}: {xsd.error_log}')


def cli(main):
    try:
        return main() or 0
    except (ValueError, OSError, E.LxmlError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 1
