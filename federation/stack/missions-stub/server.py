"""A stub of the Missions service for the whole-stack compose, so that the stack runs WITHOUT Oracle.

It serves a RELEASED Missions dataset with the contract's read operations. The stack serves release 1.2 (300 missions): six real
pages, missions-1.xml to missions-6.xml, in one folder, and the folder is given. A single file (release 1.0, the file missions.xml with
its 31 missions) can be given instead. Whatever the layout, the missions are listed in the
contract's order (stardate, priority, missionId), never in file order. The operations are: GET /missions/{missionId} and GET /missions with the contract's filters, page and pageSize, and the
contract's error bodies (INVALID_MISSION_ID, MISSION_NOT_FOUND, INVALID_REQUEST). It is read-only, holds no state and
makes no outbound call. It is NOT the Missions service: the real service (Spring Boot on Oracle) is the real-service mode.
The behaviour mirrors the stub of the Missions adapter's own tests (StubMissions.java), which serves the same file.

Usage: python -B server.py <missions.xml | folder of missions-N.xml pages> [port]
(host 0.0.0.0 inside the container; the compose file publishes nothing)
"""
import re
import sys
from decimal import Decimal
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

NS = 'urn:starfleet:missions:v1'
KNOWN = ('type', 'classification', 'status', 'priority', 'issuingAuthority', 'commandingOfficerId', 'assignedCrewId',
         'assignedAssetId', 'locationType', 'page', 'pageSize')
HEAD = '<?xml version="1.0" encoding="UTF-8"?>\n'


def error(code):
    return HEAD + f'<error xmlns="{NS}"><code>{code}</code><message>Illustrative message.</message></error>'


def field(block, name):
    found = re.search(r'(?s)<' + name + r'>(.*?)</' + name + '>', block)
    return found.group(1) if found else None


def matches(block, parameters):
    location = field(block, 'location')
    top = re.sub(r'(?s)<location>.*?</location>', '', block, count=1)
    for name, values in parameters.items():
        value = values[0]
        if name in ('type', 'classification', 'status', 'priority', 'issuingAuthority', 'commandingOfficerId'):
            ok = value == field(top, name)
        elif name == 'locationType':
            ok = value == field(location, 'type')
        elif name == 'assignedCrewId':
            ok = f'<crewId>{value}</crewId>' in block
        elif name == 'assignedAssetId':
            ok = f'<assetId>{value}</assetId>' in block
        else:
            ok = True
        if not ok:
            return False
    return True


def contract_order(blocks):
    """The contract's order of a mission list: stardate ascending, priority ascending, missionId ascending."""
    return sorted(blocks, key=lambda block: (Decimal(field(block, 'stardate')), int(field(block, 'priority')), field(block, 'missionId')))


def read_blocks(source):
    """The mission blocks of a released file, or of the numbered pages in a released folder, in the contract's order."""
    source = Path(source)
    if source.is_dir():
        files = sorted(source.glob('missions-*.xml'), key=lambda page: int(re.fullmatch(r'missions-([1-9][0-9]*)\.xml', page.name).group(1)))
    else:
        files = [source]
    text = ''
    for file in files:
        with open(file, encoding='utf-8', newline='') as handle:
            text += handle.read().replace('\r\n', '\n')
    return contract_order(re.findall(r'(?s)<mission>.*?</mission>', text))


def make_handler(blocks):
    blocks = contract_order(blocks)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return

        def reply(self, status, body):
            data = body.encode('utf-8')
            self.send_response(status)
            if data:
                self.send_header('Content-Type', 'application/xml;charset=UTF-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            parts = urlsplit(self.path)
            if parts.path == '/missions':
                return self.list(parts.query)
            if parts.path.startswith('/missions/') and '/' not in parts.path[10:]:
                mission_id = unquote(parts.path[10:])
                if not re.fullmatch(r'ST-[A-Z0-9]{9}', mission_id):
                    return self.reply(400, error('INVALID_MISSION_ID'))
                for block in blocks:
                    if field(block, 'missionId') == mission_id:
                        return self.reply(200, HEAD + block.replace('<mission>', f'<mission xmlns="{NS}">', 1))
                return self.reply(404, error('MISSION_NOT_FOUND'))
            return self.reply(404, '')

        def list(self, raw_query):
            parameters = parse_qs(raw_query, keep_blank_values=True)
            if any(name not in KNOWN or len(values) != 1 for name, values in parameters.items()):
                return self.reply(400, error('INVALID_REQUEST'))
            page = parameters.get('page', ['1'])[0]
            page_size = parameters.get('pageSize', ['20'])[0]
            valid = (re.fullmatch(r'[1-9][0-9]*', page) and re.fullmatch(r'[1-9]|[1-4][0-9]|50', page_size)
                     and re.fullmatch(r'[1-5]', parameters.get('priority', ['1'])[0])
                     and re.fullmatch(r'C-[1-9][0-9]*', parameters.get('commandingOfficerId', ['C-1'])[0])
                     and re.fullmatch(r'C-[1-9][0-9]*', parameters.get('assignedCrewId', ['C-1'])[0])
                     and re.fullmatch(r'[A-Z]{2,5}-[1-9][0-9]*', parameters.get('assignedAssetId', ['EQ-1'])[0]))
            if not valid:
                return self.reply(400, error('INVALID_REQUEST'))
            matching = [block for block in blocks if matches(block, parameters)]
            size = int(page_size)
            start = (int(page) - 1) * size
            window = matching[start:start + size]
            pages = (len(matching) + size - 1) // size
            return self.reply(200, HEAD + f'<missionList xmlns="{NS}"><page>{page}</page><pageSize>{page_size}</pageSize>'
                                          f'<totalCount>{len(matching)}</totalCount><totalPages>{pages}</totalPages>' + ''.join(window) + '</missionList>')

    return Handler


def main(argv):
    blocks = read_blocks(argv[0])
    if not blocks:
        print('server.py: no mission found in ' + argv[0], file=sys.stderr)
        return 1
    port = int(argv[1]) if len(argv) > 1 else 8083
    ThreadingHTTPServer(('0.0.0.0', port), make_handler(blocks)).serve_forever()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
