"""HTTP smoke against a running Crew & Personnel service (normal or unavailable)."""
import argparse
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from xml_validation import NS, SOAP, parse, schema, require, cli

Q = lambda name: '{' + NS + '}' + name
S = lambda name: '{' + SOAP + '}' + name


def check_response(raw, status, operation, fault, field, dataset_version, xsd):
    require(status == (500 if fault else 200), f'Unexpected HTTP status: {status}')
    doc = parse(raw)
    require(doc.tag == S('Envelope'), 'SOAP 1.1 Envelope required')
    require([n.tag for n in doc] in ([S('Body')], [S('Header'), S('Body')]), 'Envelope structure')
    body = doc.find(S('Body'))
    require(body is not None and len(body) == 1, 'Exactly one body payload')
    result = body[0]
    if fault:
        require(result.tag == S('Fault'), 'Expected SOAP Fault')
        require([n.tag for n in result] == ['faultcode', 'faultstring', 'detail'], 'SOAP fault structure')
        detail = result.find('detail')
        require(len(detail) == 1 and detail[0].tag == Q('CrewServiceFault'), 'Expected CrewServiceFault')
        payload = detail[0]
        require(payload.findtext(Q('code')) == fault, f'Expected {fault}')
        actual_field = payload.find(Q('field'))
        require((actual_field is None if field is None else actual_field is not None and actual_field.text == field),
                f'Expected fault field {field!r}')
        code = result.find('faultcode')
        parts = (code.text or '').strip().split(':')
        require(len(parts) in (1, 2), 'Wrong SOAP faultcode')
        prefix = parts[0] if len(parts) == 2 else None
        expected = 'Client' if fault in ('InvalidRequest', 'CrewNotFound') else 'Server'
        require(parts[-1] == expected and code.nsmap.get(prefix) == SOAP, 'Wrong SOAP faultcode')
        result = payload
    else:
        require(result.tag == Q(operation + 'Response'), 'Wrong response operation')
        require(result.findtext(Q('datasetVersion')) == dataset_version, 'Wrong datasetVersion')
        require(len(result.findall(Q('crewMember'))) <= 100, 'Response exceeds 100 records')
    xsd.assertValid(result)
    return result


def request(endpoint, operation, fields, fault, field, dataset_version, xsd):
    raw = (f'<s:Envelope xmlns:s="{SOAP}"><s:Body><{operation}Request xmlns="{NS}">'
           f'{fields}</{operation}Request></s:Body></s:Envelope>').encode('utf-8')
    req = Request(endpoint, data=raw, headers={'Content-Type': 'text/xml; charset=utf-8',
                  'SOAPAction': f'"{NS}:{operation}"'}, method='POST')
    try:
        response = urlopen(req, timeout=10)
    except HTTPError as exc:
        response = exc
    with response:
        return check_response(response.read(), response.status, operation, fault, field, dataset_version, xsd)


def check_large(invoke):
    records = []
    for offset in range(0, 800, 100):
        result = invoke('ListCrewMembers', f'<offset>{offset}</offset><limit>100</limit>')
        page = result.findall(Q('crewMember'))
        require(len(page) == 100 and result.findtext(Q('totalCount')) == '800'
                and result.findtext(Q('offset')) == str(offset) and result.findtext(Q('limit')) == '100'
                and result.findtext(Q('hasMore')) == ('true' if offset < 700 else 'false'), 'Wrong aggregate page')
        records.extend(page)
    ids = [r.findtext(Q('crewId')) for r in records]
    expected = [f'CRW-{i}' for i in range(1047, 1059)] + ['CRW-1100', 'CRW-1101'] + [f'CRW-{i}' for i in range(2000, 2786)]
    require(ids == expected, 'Aggregate IDs missing, duplicated or unordered')
    cross = invoke('ListCrewMembers', '<offset>95</offset><limit>20</limit>')
    require([r.findtext(Q('crewId')) for r in cross.findall(Q('crewMember'))] == ids[95:115], 'Storage boundary leaked into pagination')
    by_id = dict(zip(ids, records))
    for record in records:
        seen = set()
        current = record.findtext(Q('crewId'))
        while current is not None:
            require(current in by_id and current not in seen, 'Invalid aggregate supervisor graph')
            seen.add(current)
            current = by_id[current].findtext(Q('supervisorCrewId'))
    require(by_id['CRW-1050'].findtext(Q('department')) == 'SCIENCE'
            and by_id['CRW-1050'].findtext(Q('positionTitle')) == 'Science Department Lead', 'Wrong Data assignment')
    require(by_id['CRW-1055'].findtext(Q('supervisorCrewId')) == 'CRW-1050', 'Wrong Wesley supervisor')
    require(by_id['CRW-1056'].find(Q('supervisorCrewId')) is None, 'Guinan supervisor must be omitted')
    for status, count in [('ACTIVE', 719), ('ON_LEAVE', 40), ('INACTIVE', 41)]:
        result = invoke('ListCrewMembers', f'<dutyStatus>{status}</dutyStatus><limit>100</limit>')
        require(result.findtext(Q('totalCount')) == str(count), 'Wrong status count')
        require(all(r.findtext(Q('dutyStatus')) == status for r in result.findall(Q('crewMember'))), 'Wrong status filter')
    for crew_id in ['CRW-1052', 'CRW-1100', 'CRW-1101', 'CRW-2000', 'CRW-2785']:
        result = invoke('GetCrewMember', f'<crewId>{crew_id}</crewId>')
        require([(e.tag, e.text) for e in result.find(Q('crewMember'))] ==
                [(e.tag, e.text) for e in by_id[crew_id]], 'Get differs from aggregate')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', default='http://127.0.0.1:8081/soap/crew-personnel')
    parser.add_argument('--dataset-version', choices=('crew-v1-small-001', 'crew-v1-small-002', 'crew-v1-large-003'), default='crew-v1-small-002')
    parser.add_argument('--profile', choices=('normal', 'unavailable'), default='normal')
    args = parser.parse_args()
    xsd = schema()

    def invoke(op, fields='', fault=None, field=None):
        return request(args.endpoint, op, fields, fault, field, args.dataset_version, xsd)

    if args.profile == 'normal':
        result = invoke('GetCrewMember', '<crewId>CRW-1047</crewId>')
        require(result.findtext('.//' + Q('displayName')) == 'Jean-Luc Picard', 'Wrong crew member')
        result = invoke('ListCrewMembers', '<offset>2</offset><limit>2</limit>')
        count = {'crew-v1-small-001': 6, 'crew-v1-small-002': 12, 'crew-v1-large-003': 800}[args.dataset_version]
        require(len(result.findall(Q('crewMember'))) == 2 and result.findtext(Q('totalCount')) == str(count)
                and result.findtext(Q('hasMore')) == 'true', 'Wrong pagination')
        invoke('GetCrewMember', '<crewId>CRW-9999</crewId>', 'CrewNotFound', 'crewId')
        if args.dataset_version == 'crew-v1-large-003':
            check_large(invoke)
    else:
        invoke('GetCrewMember', '<crewId>CRW-9999</crewId>', 'ServiceUnavailable')
        invoke('ListCrewMembers', fault='ServiceUnavailable')
    invoke('ListCrewMembers', '<limit>0</limit>', 'InvalidRequest', 'limit')
    print(f'PASS: {args.profile} SOAP HTTP smoke at {args.endpoint}; statuses, payload XSD, '
          'fault code/field and dataset/pagination assertions.')


if __name__ == '__main__':
    sys.exit(cli(main))
