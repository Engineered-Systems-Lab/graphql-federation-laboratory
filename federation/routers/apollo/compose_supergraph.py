"""Compose the supergraph of the federation layer with Rover, from the four adapters' SDL, in a fixed order.

The supergraph is a BUILD PRODUCT checked in as evidence of the composition at a commit: the sources are the adapters' schemas and this
script, and a test regenerates it from the running adapters and fails when the committed file differs. The script

  1. fetches each adapter's SDL with `{ _service { sdl } }` (or reads <name>.graphql files from --sdl-dir),
  2. writes the SDL files and a Rover config into a work folder, the subgraphs in SORTED order of their names,
  3. runs Rover 1.0.0 with the composition plugin `supergraph` v2.9.3 (federation_version: =2.9.3) in the image built from
     federation/routers/apollo/rover/Dockerfile, and
  4. writes the supergraph to --out and prints its SHA-256.

The routing URL of every subgraph is its service name on the stack's network, the SAME in every mode (see ROUTING below), so the
supergraph does not depend on the host's ports; only the SDL is fetched through the host ports.

Rover's composition plugin is under the Elastic License 2.0. This script accepts nothing for you: it refuses to run unless the
environment variable APOLLO_ELV2_LICENSE is `accept`, which you set on purpose.

Usage (from the repository root, Docker running, the adapters up; federation/stack/start.sh does this for you):
  APOLLO_ELV2_LICENSE=accept python -B federation/routers/apollo/compose_supergraph.py
Options: --out PATH (default: federation/routers/apollo/supergraph.graphql, the committed file), --sdl-dir DIR (read DIR/<name>.graphql instead of fetching), --save-sdl DIR (keep the fetched SDL), --order a,b,c,d (test only:
compose in another order), --image NAME (the Rover image; default below).
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROVER_IMAGE = 'starfleet-federation-rover:1.0.0-supergraph-2.9.3'
FEDERATION_VERSION = '=2.9.3'
# name -> (service name on the stack's network, container port, environment variable of the host port, default host port).
# The routing URL is http://<service>:<container port>/graphql in every mode.
ROUTING = {
    'assets': ('assets-adapter', 8184, 'ASSETS_ADAPTER_HOST_PORT', 8184),
    'mapping': ('mapping-adapter', 8190, 'MAPPING_ADAPTER_HOST_PORT', 8190),
    'missions': ('missions-adapter', 8183, 'MISSIONS_ADAPTER_HOST_PORT', 8183),
    'personnel': ('personnel-adapter', 8182, 'PERSONNEL_ADAPTER_HOST_PORT', 8182),
}
SDL_QUERY = '{ _service { sdl } }'


def sorted_names():
    return sorted(ROUTING)


def routing_url(name):
    service, port, _, _ = ROUTING[name]
    return f'http://{service}:{port}/graphql'


def render_config(order):
    """The Rover config: LF only, the subgraphs in the order given, the files under /work."""
    lines = [f'federation_version: {FEDERATION_VERSION}', 'subgraphs:']
    for name in order:
        lines += [f'  {name}:', f'    routing_url: {routing_url(name)}', '    schema:', f'      file: /work/{name}.graphql']
    return '\n'.join(lines) + '\n'


def normalize_sdl(text):
    """LF line ends and exactly one trailing newline; nothing else is touched."""
    return text.replace('\r\n', '\n').rstrip('\n') + '\n'


def fetch_sdl(name, host='127.0.0.1', timeout=30):
    port = int(os.environ.get(ROUTING[name][2], ROUTING[name][3]))
    body = json.dumps({'query': SDL_QUERY}).encode('utf-8')
    request = urllib.request.Request(f'http://{host}:{port}/graphql', data=body,
                                     headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        answer = json.loads(response.read().decode('utf-8'))
    try:
        return answer['data']['_service']['sdl']
    except (KeyError, TypeError) as error:
        raise RuntimeError(f'The {name} adapter did not answer {SDL_QUERY}: {answer}') from error


def docker(args, timeout=600, check=True):
    result = subprocess.run(['docker'] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    stdout, stderr = result.stdout.decode('utf-8', 'replace'), result.stderr.decode('utf-8', 'replace')
    if check and result.returncode:
        raise RuntimeError('docker ' + ' '.join(args[:3]) + ' failed: ' + (stderr or stdout)[-2000:])
    return result.returncode, stdout, stderr


def require_license():
    if os.environ.get('APOLLO_ELV2_LICENSE') != 'accept':
        raise RuntimeError("Rover's composition plugin is under the Elastic License 2.0: set APOLLO_ELV2_LICENSE=accept to accept it on purpose")


def ensure_image(image):
    if docker(['image', 'inspect', image, '--format', '{{.Id}}'], check=False)[0] == 0:
        return
    docker(['build', '--build-arg', 'APOLLO_ELV2_LICENSE=accept', '-t', image, str(HERE / 'rover')], timeout=1800)


def compose(work, out, order, image=ROVER_IMAGE):
    """Compose the SDL files in `work` and write the supergraph to `out`. Returns the Rover version line."""
    require_license()
    ensure_image(image)
    (work / 'supergraph.yaml').write_bytes(render_config(order).encode('utf-8'))
    for stale in (work / 'supergraph.graphql',):
        if stale.exists():
            stale.unlink()
    env = ['-e', 'APOLLO_ELV2_LICENSE=accept', '-e', 'APOLLO_TELEMETRY_DISABLED=1']
    mount = ['--mount', f'type=bind,source={work},target=/work']
    docker(['run', '--rm', '--network', 'none'] + env + mount + [image, 'supergraph', 'compose', '--config', '/work/supergraph.yaml',
                                                                  '--output', '/work/supergraph.graphql'])
    version = docker(['run', '--rm', '--network', 'none'] + env + [image, '--version'])[1].strip()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes((work / 'supergraph.graphql').read_bytes().replace(b'\r\n', b'\n'))
    return version


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out', type=Path, default=HERE / 'supergraph.graphql')
    parser.add_argument('--sdl-dir', type=Path)
    parser.add_argument('--save-sdl', type=Path)
    parser.add_argument('--order', help='test only: comma-separated subgraph names in the order to compose (default: sorted)')
    parser.add_argument('--image', default=ROVER_IMAGE)
    args = parser.parse_args(argv)
    order = args.order.split(',') if args.order else sorted_names()
    if sorted(order) != sorted_names():
        parser.error('--order must name each of ' + ','.join(sorted_names()) + ' once')
    try:
        require_license()
        with tempfile.TemporaryDirectory(prefix='fed-compose-') as scratch:
            work = Path(scratch)
            for name in order:
                sdl = (args.sdl_dir / f'{name}.graphql').read_text(encoding='utf-8') if args.sdl_dir else fetch_sdl(name)
                (work / f'{name}.graphql').write_bytes(normalize_sdl(sdl).encode('utf-8'))
                if args.save_sdl:
                    args.save_sdl.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(work / f'{name}.graphql', args.save_sdl / f'{name}.graphql')
            version = compose(work, args.out, order, args.image)
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        print('compose_supergraph.py: ' + str(error), file=sys.stderr)
        return 1
    data = args.out.read_bytes()
    print(f'rover: {version}; federation_version {FEDERATION_VERSION}')
    print(f'supergraph: {hashlib.sha256(data).hexdigest()} {len(data)} bytes -> {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
