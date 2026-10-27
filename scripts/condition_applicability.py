"""Run frozen applicability diagnostics with Python socket/DNS operations denied."""

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--network-evidence', type=Path, required=True)
    sub = parser.add_subparsers(dest='action', required=True)
    p, r, e = [sub.add_parser(n) for n in ('prepare', 'run', 'export')]
    p.add_argument('--parent', type=Path, default=Path('output/records_stage43_20261026/run_v01'))
    p.add_argument('--checks', type=Path, required=True)
    r.add_argument('--prepared', type=Path, required=True)
    e.add_argument('--captured', type=Path, required=True)
    for command in (p, r, e):
        command.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.network_evidence.exists():
        raise FileExistsError(args.network_evidence)
    attempts = []

    def guard(event, arguments):
        if event in ('socket.connect', 'socket.getaddrinfo', 'socket.gethostbyname', 'socket.gethostbyaddr', 'socket.sendto'):
            attempts.append(event)
            raise RuntimeError('Applicability CLI forbids Python socket/DNS operations')

    sys.addaudithook(guard)
    completed = False
    try:
        from app.evaluation.condition_applicability_run import export, prepare, run

        if args.action == 'prepare':
            result = prepare(args.parent, args.checks, args.output_dir)
        elif args.action == 'run':
            result = run(args.prepared, args.output_dir)
        else:
            result = export(args.captured, args.output_dir)
        completed = True
        print(json.dumps(result, ensure_ascii=False))
    finally:
        with args.network_evidence.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump({'completed': completed, 'blocked_socket_or_dns_attempts': attempts,
                'scope': 'CPython audited socket/DNS operations; not an OS firewall or native-library monitor'}, stream, indent=2)
            stream.write('\n')


if __name__ == '__main__':
    main()
