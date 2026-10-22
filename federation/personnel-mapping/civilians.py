"""The civilians of the large Personnel v2 snapshot: about 200 people on the ship's roster without rank, department or clearance.

Four are inspired by Star Trek: The Next Generation (a child, a botanist, a child and a barber, named in CANON; the dataset states no
episode facts about them). The rest are generated families and residents: invented names, deterministic. Nothing is random: every pick
is the order of a SHA-256 over the fixed seed and a label, so the same code gives the same people on every machine and Python version.
The standard library only. This module belongs to the federation layer and is read at build time by crew_mapping.py; Personnel v2
never reads it.

  python -B federation/personnel-mapping/civilians.py     # print the people, one per line
"""
import hashlib
import sys

SEED = 'enterprise-d-2366-civilians-v1'
IDENTITY = 'personnel-civilians-v1'
ALGORITHM = 'sha256-order-v1'
FIRST_NUMBER = 3001  # above the migrated v1 numbers (1047..2785) and every earlier Personnel v2 identifier
COUNT = 199          # with the 801 other people the snapshot holds 1,000 (the Captain's "about 1,000 aboard")
FAMILY_LIMIT = 168   # members placed in families; the rest are single residents and civilian staff

CANON = (  # name, position title; all ACTIVE
    ('Alexander Rozhenko', 'Student'),
    ("Keiko O'Brien", 'Botanist'),
    ("Molly O'Brien", 'Student'),
    ('Mot', 'Barber'),
)
GIVEN = ('Adaeze Amara Anders Aroha Beatriz Bram Chiara Dmitri Elodie Farid Greta Hana Idris Ingrid Jamal Kenji Leila Mateo Nia Omar '
         'Priya Quentin Rosa Sven Tariq Uma Viktor Wanjiru Xavier Yuki Zainab Ahmad Bianca Carlos Dalia Emeka Freya Gael Hugo Ines '
         'Jonas Kalinda Liam Mei Nikolai Olga Pablo Rania Sanjay Thea Ulrich Vera Willem Ximena Yosef Zora Anika Boris Camila Dev '
         'Esme Finn Gita Henrik').split()
FAMILY = ('Abara Brandt Castellano Dahl Eze Fontaine Gallagher Hayashi Ibrahim Jovanovic Kowalski Lindqvist Moreau Nakamura Okafor '
          'Petrov Quintero Rahman Santos Tanaka Ueda Varga Whitfield Xu Yilmaz Zielinski Alvarez Bianchi Cho Dubois Eriksen Fischer '
          'Gupta Haddad Ivanova Jansen Kaplan Lombardi Mbeki Novak').split()
ADULT_TITLES = ('Resident', 'Teacher', 'Ten Forward Server', 'Botanist', 'Civilian Technician', 'Shopkeeper', 'Holodeck Technician',
                'Counselor Aide')
STAFF_TITLES = ('Resident', 'Civilian Technician', 'Ten Forward Server', 'Shopkeeper', 'Holodeck Technician', 'Teacher')


def order(label):
    return hashlib.sha256(f'{SEED}|{label}'.encode('utf-8')).digest()


def _status(label):
    pick = order('status|' + label)[0]
    return 'INACTIVE' if pick % 29 == 0 else 'ON_LEAVE' if pick % 17 == 0 else 'ACTIVE'


def _name(slot, surname, used):
    for given in sorted(GIVEN, key=lambda g: order(f'given|{slot}|{g}')):
        if f'{given} {surname}' not in used:
            return f'{given} {surname}'
    raise ValueError('no unused given name left')


def generate():
    """The people in identifier order: dicts with personnelId, displayName, positionTitle, dutyStatus and origin."""
    people = [dict(displayName=name, positionTitle=title, dutyStatus='ACTIVE', origin='canon-inspired') for name, title in CANON]
    used = {person['displayName'] for person in people}
    units = []
    placed = 0
    for surname in sorted(FAMILY, key=lambda s: order('family|' + s)):
        digest = order('unit|' + surname)
        adults, children = 1 + digest[0] % 2, digest[1] % 4
        if placed + adults + children > FAMILY_LIMIT:
            continue
        units.append((surname, adults, children))
        placed += adults + children
    for surname, adults, children in units:
        for role, count in (('adult', adults), ('child', children)):
            for k in range(count):
                slot = len(people)
                label = f'{surname}|{role}|{k}'
                if role == 'adult':
                    title = ADULT_TITLES[order('title|' + label)[0] % len(ADULT_TITLES)]
                else:
                    title = 'Preschooler' if order('title|' + label)[0] % 5 == 0 else 'Student'
                name = _name(slot, surname, used)
                used.add(name)
                people.append(dict(displayName=name, positionTitle=title, dutyStatus=_status(label) if role == 'adult' else 'ACTIVE',
                                   origin='synthetic'))
    while len(people) < COUNT:
        slot = len(people)
        surname = sorted(FAMILY, key=lambda s: order(f'single|{slot}|{s}'))[0]
        name = _name(slot, surname, used)
        used.add(name)
        title = STAFF_TITLES[order(f'title|single|{slot}')[0] % len(STAFF_TITLES)]
        people.append(dict(displayName=name, positionTitle=title, dutyStatus=_status(f'single|{slot}'), origin='synthetic'))
    if len(people) != COUNT:
        raise ValueError(f'expected {COUNT} civilians, built {len(people)}')
    for index, person in enumerate(people):
        person['personnelId'] = f'PRS-{FIRST_NUMBER + index:04d}'
    return people


if __name__ == '__main__':
    for person in generate():
        print(person['personnelId'], person['displayName'], '|', person['positionTitle'], '|', person['dutyStatus'], '|', person['origin'])
    sys.exit(0)
