"""Write the machine-local study config for every scenario, with its provenance block, outside the repository.

    python -B study/launch/make_config.py --output <config.json> --plan <plan.json> --missions simulated|real --state-dir <folder>
        --mcp-python <python of the MCP virtual environment> --guide-file <guide for beta> [--accept-apollo-elv2] [--replace]

The scenarios (alpha to epsilon) come from this kit: each one's stack commands (launch.py up, down and service), its MCP server, its
warm-up calls and its `provenance` block, with the mode of every backend. The run plan is the operator's: --plan names a JSON file with
the keys of PLAN_KEYS (task set, scenario order, models, trials, seed, warm-up passes, limits and budgets), copied as given; the kit sets
no schedule and no budget. The config holds this machine's absolute paths and so is written outside the repository only. It holds no
credential: the Assets passwords are made by launch.py at each start, and no Missions login is needed.
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'study' / 'harness'))
import provenance  # noqa: E402  (the harness's own validator and hash, so the generated block is what the harness checks)

sys.path.insert(0, str(HERE))
import launch  # noqa: E402

PLAN_KEYS = ('task_set', 'scenario_order', 'models', 'trials', 'seed', 'warmup_passes', 'limits', 'budgets')
OPTIONAL_PLAN_KEYS = ('about',)

# Image names as federation/stack/compose.yaml and uss-enterprise/missions/compose.yaml give them by default (a test pins them).
IMAGES = {
    'missions-stub': 'python:3.13-slim-bookworm@sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641',
    'missions-real': 'starfleet-missions-service:1.0.0',
    'assets-service': 'starfleet-federation-stack-assets-service:1.0.0',
    'personnel-service': 'starfleet-federation-stack-personnel-service:2.0.0',
}
STACK_PROJECT = 'starfleet-federation-stack'
MISSIONS_DATASET = ROOT / 'uss-enterprise' / 'missions' / 'datasets' / 'releases' / '1.2'
ASSETS_DATASET = ROOT / 'uss-enterprise' / 'assets' / 'datasets' / 'releases' / '1.1'
MAPPING_RELEASES = ROOT / 'federation' / 'mapping-releases'
MCP = ROOT / 'study' / 'mcp'

SERVERS = {
    'alpha': {'port': 8191, 'kind': 'raw'},
    'beta': {'port': 8191, 'kind': 'raw'},
    'gamma': {'port': 8192, 'kind': 'adapters'},
    'delta': {'port': 8193, 'kind': 'graph', 'router_url': 'http://127.0.0.1:8170/', 'name': 'graph-apollo'},
    'epsilon': {'port': 8194, 'kind': 'graph', 'router_url': 'http://127.0.0.1:8171/graphql', 'name': 'graph-cosmo'},
}
UPSTREAMS = {
    'raw': {'missions': 'http://127.0.0.1:8083/', 'personnel': 'http://127.0.0.1:8082/', 'assets': 'http://127.0.0.1:8084/'},
    'adapters': {'http://127.0.0.1:8182/graphql': 'personnel-adapter', 'http://127.0.0.1:8183/graphql': 'missions-adapter',
                 'http://127.0.0.1:8184/graphql': 'assets-adapter', 'http://127.0.0.1:8190/graphql': 'mapping-adapter'},
}
MAPPING_WARMUP = [{'tool': 'read_mapping_release', 'arguments': {'release': '1.3'}}]


class Refused(Exception):
    pass


def graphql_warmup(**arguments):
    return [{'tool': 'graphql_query', 'arguments': dict({'query': '{ __typename }'}, **arguments)}]


def launch_command(launch_python, state_dir, mode, *words, env=None):
    command = {'argv': [launch_python, '-B', str(HERE / 'launch.py'), *words, '--missions', mode, '--state-dir', str(state_dir)]}
    if env:
        command['env'] = dict(env)
    return command


def mcp_server(scenario, mcp_python):
    server = SERVERS[scenario]
    if server['kind'] == 'raw':
        argv = [mcp_python, '-B', str(MCP / 'raw_server.py'), '--mapping-dir', str(MAPPING_RELEASES)]
    elif server['kind'] == 'adapters':
        argv = [mcp_python, '-B', str(MCP / 'adapters_server.py')]
    else:
        argv = [mcp_python, '-B', str(MCP / 'graph_server.py'), '--router-url', server['router_url'], '--name', server['name'],
                '--port', str(server['port'])]
    return {'argv': argv, 'background': True}


def stack(scenario, mode, launch_python, mcp_python, state_dir, start_env):
    def cmd(*words, env=None):
        return launch_command(launch_python, state_dir, mode, *words, env=env)
    return {
        'start': [cmd('up', scenario, env=start_env), mcp_server(scenario, mcp_python)],
        'teardown': [cmd('down', scenario)],
        'stop_service': {name: [cmd('service', 'stop', name, scenario)] for name in launch.OUTAGE_SERVICES},
        'start_service': {name: [cmd('service', 'start', name, scenario)] for name in launch.OUTAGE_SERVICES},
    }


def missions_backend(mode):
    if mode == 'real':
        return {'mode': 'real', 'service': '%s/missions' % launch.MISSIONS_PROJECT, 'image_ref': IMAGES['missions-real']}
    kind, digest = provenance.hash_path(MISSIONS_DATASET)
    if kind != 'folder':
        raise Refused('the Missions dataset release 1.2 cannot be read at %s' % MISSIONS_DATASET)
    return {'mode': 'simulated', 'service': 'missions-stub', 'image_ref': IMAGES['missions-stub'],
            'dataset': {'id': 'missions-1.2', 'path': str(MISSIONS_DATASET), 'sha256': digest}}


def assets_backend():
    kind, digest = provenance.hash_path(ASSETS_DATASET)
    if kind != 'folder':
        raise Refused('the Assets dataset release 1.1 cannot be read at %s' % ASSETS_DATASET)
    return {'mode': 'real', 'service': 'assets-service', 'image_ref': IMAGES['assets-service'],
            'dataset': {'id': 'assets-1.1', 'path': str(ASSETS_DATASET), 'sha256': digest}}


def provenance_block(scenario, mode):
    missions = missions_backend(mode)
    projects = [launch.MISSIONS_PROJECT, STACK_PROJECT] if mode == 'real' else [STACK_PROJECT]
    kind = SERVERS[scenario]['kind']
    if kind == 'raw':
        raw = UPSTREAMS['raw']
        endpoints = {raw['missions']: missions['service'], raw['personnel']: 'personnel-service', raw['assets']: 'assets-service'}
    elif kind == 'adapters':
        endpoints = dict(UPSTREAMS['adapters'])
    elif launch.router_of(scenario) == 'cosmo':
        endpoints = {SERVERS[scenario]['router_url']: 'cosmo-router'}
    else:
        endpoints = {SERVERS[scenario]['router_url']: 'router'}
    files = {'launch_script': launch.HERE / 'launch.py', 'stack_compose': launch.STACK_COMPOSE}
    if mode == 'real':
        files['missions_real_overlay'] = launch.REAL_OVERLAY
    else:
        files['stack_start'] = launch.START_SH
    if scenario in launch.LEGACY_SCENARIOS:
        files['legacy_ports'] = launch.LEGACY_PORTS
    return {
        'compose_projects': projects,
        'backends': {
            'missions': missions,
            'assets': assets_backend(),
            'personnel': {'mode': 'real', 'service': 'personnel-service', 'image_ref': IMAGES['personnel-service']},
        },
        'routing': {'endpoints': endpoints,
                    'env': {adapter: {variable: urls[mode]} for adapter, (variable, urls) in sorted(launch.ADAPTER_BACKEND_URLS.items())}},
        'launch_files': {label: str(path) for label, path in sorted(files.items())},
    }


def scenario_config(scenario, mode, launch_python, mcp_python, state_dir, guide_file, start_env):
    port = SERVERS[scenario]['port']
    kind = SERVERS[scenario]['kind']
    if kind == 'raw':
        warmup = MAPPING_WARMUP
    elif kind == 'adapters':
        warmup = graphql_warmup(service='personnel')
    else:
        warmup = graphql_warmup()
    out = {'mcp_url': 'http://127.0.0.1:%d/mcp' % port, 'ready_timeout_seconds': 900, 'warmup_calls': warmup}
    if scenario == 'beta':
        out['guide_file'] = str(guide_file)
    out['stack'] = stack(scenario, mode, launch_python, mcp_python, state_dir, start_env)
    out['provenance'] = provenance_block(scenario, mode)
    return out


def machine_facts_commands():
    facts = {'docker_version': ['docker', 'version', '--format', '{{.Server.Version}}'],
             'docker_share_ncpu_memtotal_bytes': ['docker', 'info', '--format', '{{.NCPU}} {{.MemTotal}}'],
             'docker_compose_version': ['docker', 'compose', 'version', '--short']}
    if os.name == 'nt':
        facts['cpu_name'] = ['powershell', '-NoProfile', '-Command', '(Get-CimInstance Win32_Processor).Name']
        facts['free_memory_kb_at_start'] = ['powershell', '-NoProfile', '-Command', '(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory']
    return facts


def read_plan(path):
    try:
        with open(path, encoding='utf-8-sig') as handle:
            plan = json.load(handle)
    except (OSError, ValueError) as error:
        raise Refused('the plan %s cannot be read as JSON: %s' % (path, error))
    if not isinstance(plan, dict):
        raise Refused('the plan must be a JSON object')
    missing = [key for key in PLAN_KEYS if key not in plan]
    unknown = sorted(set(plan) - set(PLAN_KEYS) - set(OPTIONAL_PLAN_KEYS))
    if missing:
        raise Refused('the plan lacks %s' % ', '.join(missing))
    if unknown:
        raise Refused('the plan may hold only %s; this kit writes the rest, so remove %s' % (', '.join(PLAN_KEYS), ', '.join(unknown)))
    order = plan['scenario_order']
    if not isinstance(order, list) or not order or any(name not in launch.SCENARIOS for name in order) or len(set(order)) != len(order):
        raise Refused('scenario_order must list distinct scenarios among %s' % ', '.join(launch.SCENARIOS))
    return plan


def build(plan, mode, launch_python, mcp_python, state_dir, guide_file, accept_elv2=False):
    if mode not in launch.MODES:
        raise Refused('--missions must be one of %s' % ', '.join(launch.MODES))
    start_env = {'APOLLO_ELV2_LICENSE': 'accept'} if accept_elv2 else None
    config = {'about': 'Machine-local study config written by study/launch/make_config.py with the Missions backend %s. It holds '
                       'this machine\'s paths and no credential; do not commit it.' % mode}
    config.update({key: plan[key] for key in PLAN_KEYS})
    config['scenarios'] = {name: scenario_config(name, mode, launch_python, mcp_python, state_dir, guide_file, start_env)
                           for name in plan['scenario_order']}
    for name, scenario in config['scenarios'].items():
        provenance.validate(name, scenario.get('provenance'))
    config['telemetry'] = {'apollo_router': 'anonymous telemetry off (APOLLO_TELEMETRY_DISABLED)',
                           'cosmo_router': 'anonymous telemetry off (COSMO_TELEMETRY_DISABLED)'}
    config['declared_settings'] = {
        'apollo_router': {'version': 'v2.18.0', 'supergraph.introspection': True, 'default': 'off'},
        'cosmo_router': {'version': '0.359.0', 'introspection.enabled': True, 'default': 'on'},
        'adapters': 'answer __schema on their own endpoints unchanged; the MCP servers hide _service and _entities',
        'missions_backend': mode,
    }
    config['facts_commands'] = machine_facts_commands()
    config['hash_files'] = {'mapping_release_1_3_manifest': str(MAPPING_RELEASES / '1.3' / 'manifest.json')}
    return config


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--output', required=True, help='the config file to write, outside the repository')
    parser.add_argument('--plan', required=True, help='the operator\'s run plan: a JSON object with %s' % ', '.join(PLAN_KEYS))
    parser.add_argument('--missions', required=True, choices=launch.MODES, help='the Missions backend of every scenario')
    parser.add_argument('--state-dir', required=True, help='launch.py\'s machine-local state folder, outside the repository')
    parser.add_argument('--mcp-python', default=os.environ.get('STUDY_MCP_PYTHON'),
                        help='the Python of the MCP virtual environment (default: STUDY_MCP_PYTHON)')
    parser.add_argument('--launch-python', default=sys.executable, help='the Python that runs launch.py (default: this one)')
    parser.add_argument('--guide-file', required=True, help='the integration guide of beta (Guided Direct Access)')
    parser.add_argument('--accept-apollo-elv2', action='store_true',
                        help='write APOLLO_ELV2_LICENSE=accept into the stack start commands: you accept the Elastic License 2.0 of '
                             'Rover\'s composition plugin')
    parser.add_argument('--replace', action='store_true', help='overwrite an existing output file')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if not args.mcp_python:
            raise Refused('give --mcp-python or set STUDY_MCP_PYTHON')
        output = launch.outside_repository(args.output, 'the output config')
        state_dir = launch.outside_repository(args.state_dir, 'the state folder')
        guide = Path(args.guide_file).resolve()
        if not guide.is_file():
            raise Refused('the guide file %s does not exist' % guide)
        if output.exists() and not args.replace:
            raise Refused('%s exists; give --replace to overwrite it' % output)
        config = build(read_plan(args.plan), args.missions, args.launch_python, args.mcp_python, state_dir, guide,
                       accept_elv2=args.accept_apollo_elv2)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, 'w', encoding='utf-8', newline='\n') as handle:
            json.dump(config, handle, indent=2)
            handle.write('\n')
    except (Refused, launch.Refused, ValueError) as error:
        print('make_config.py: refused: %s' % error, file=sys.stderr)
        return 1
    print('wrote %s (Missions %s, scenarios %s)' % (output, args.missions, ', '.join(config['scenarios'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
