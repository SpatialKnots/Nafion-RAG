"""Freeze DSC experiment or inspect supplied bytes offline; never send API requests."""

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--network-evidence', type=Path, required=True)
    sub = parser.add_subparsers(dest='action', required=True)
    prepare = sub.add_parser('prepare')
    prepare.add_argument('--parent', type=Path, default=Path('output/records_stage48_20261027/run_v01'))
    for name in ('run', 'export', 'inspect-response'):
        command = sub.add_parser(name)
        command.add_argument('--source', type=Path, required=True)
        command.add_argument('--output-dir', type=Path, required=True)
        if name == 'inspect-response':
            command.add_argument('--response', type=Path, required=True)
    prepare.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.network_evidence.exists():
        raise FileExistsError(args.network_evidence)
    attempts = []

    def guard(event, arguments):
        if event in ('socket.connect', 'socket.getaddrinfo', 'socket.gethostbyname', 'socket.gethostbyaddr', 'socket.sendto'):
            attempts.append(event)
            raise RuntimeError('DSC experiment CLI forbids Python connect/DNS/sendto operations')

    sys.addaudithook(guard)
    completed = False
    try:
        from app.evaluation.dsc_experiment_run import execute, inspect_offline, prepare

        if args.action == 'prepare':
            result = prepare(args.parent, args.output_dir)
        elif args.action == 'inspect-response':
            result = inspect_offline(args.source, args.response, args.output_dir)
        else:
            result = execute(args.source, args.output_dir, export=args.action == 'export')
        completed = True
        print(json.dumps(result, ensure_ascii=False))
    finally:
        with args.network_evidence.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump({'completed': completed, 'blocked_socket_or_dns_attempts': attempts,
                'scope': 'CPython audited connect/DNS/sendto; not an OS/native firewall'}, stream, indent=2)
            stream.write('\n')


if __name__ == '__main__':
    main()
