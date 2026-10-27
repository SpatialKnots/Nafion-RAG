"""Assess DSC source eligibility offline; deny connect/DNS/sendto before imports."""

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--network-evidence', type=Path, required=True)
    sub = parser.add_subparsers(dest='action', required=True)
    prepare = sub.add_parser('prepare')
    prepare.add_argument('--parent', type=Path, default=Path('output/records_stage47_20261027/run_v01'))
    for name in ('run', 'export'):
        command = sub.add_parser(name)
        command.add_argument('--source', type=Path, required=True)
        command.add_argument('--output-dir', type=Path, required=True)
    prepare.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.network_evidence.exists():
        raise FileExistsError(args.network_evidence)
    attempts = []

    def guard(event, arguments):
        if event in ('socket.connect', 'socket.getaddrinfo', 'socket.gethostbyname', 'socket.gethostbyaddr', 'socket.sendto'):
            attempts.append(event)
            raise RuntimeError('DSC admission CLI forbids Python socket/DNS operations')

    sys.addaudithook(guard)
    completed = False
    try:
        from app.evaluation.dsc_admission_run import execute, prepare

        result = prepare(args.parent, args.output_dir) if args.action == 'prepare' else execute(
            args.source, args.output_dir, export=args.action == 'export')
        completed = True
        print(json.dumps(result, ensure_ascii=False))
    finally:
        with args.network_evidence.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump({'completed': completed, 'blocked_socket_or_dns_attempts': attempts,
                'scope': 'CPython audited connect/DNS/sendto; not an OS/native-network firewall'}, stream, indent=2)
            stream.write('\n')


if __name__ == '__main__':
    main()
