"""Audit frozen sample/table references with Python socket/DNS operations denied."""

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--network-evidence', type=Path, required=True)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--parent', type=Path, default=Path('output/records_stage44_20261027/run_v01'))
    p.add_argument('--history', type=Path, default=Path('output/records_stage23_20261021/run_v01'))
    p.add_argument('--windows', type=Path, default=Path('output/records_stage19_20261021/run_v01'))
    p.add_argument('--checks', type=Path, required=True)
    for name in ('run', 'export'):
        cmd = sub.add_parser(name)
        cmd.add_argument('--source', type=Path, required=True)
        cmd.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.network_evidence.exists():
        raise FileExistsError(args.network_evidence)
    attempts = []

    def guard(event, arguments):
        if event in ('socket.connect', 'socket.getaddrinfo', 'socket.gethostbyname', 'socket.gethostbyaddr', 'socket.sendto'):
            attempts.append(event)
            raise RuntimeError('Identifier CLI forbids Python socket/DNS operations')

    sys.addaudithook(guard)
    completed = False
    try:
        from app.evaluation.sample_identifiers_run import execute, prepare

        if args.action == 'prepare':
            result = prepare(args.parent, args.history, args.windows, args.checks, args.output_dir)
        else:
            result = execute(args.source, args.output_dir, export=args.action == 'export')
        completed = True
        print(json.dumps(result, ensure_ascii=False))
    finally:
        with args.network_evidence.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump({'completed': completed, 'blocked_socket_or_dns_attempts': attempts,
                'scope': 'CPython audited socket/DNS operations; not an OS firewall or native-library monitor'}, stream, indent=2)
            stream.write('\n')


if __name__ == '__main__':
    main()
