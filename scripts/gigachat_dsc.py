"""Prepare offline, or explicitly dispatch one personal-token GigaChat DSC test."""

import argparse
import json
import os
from pathlib import Path

from dotenv import dotenv_values

from app.records.gigachat_dsc import dispatch, prepare


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'send'))
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--authorize-gigachat-test', action='store_true')
    args = parser.parse_args()
    if args.action == 'prepare':
        result = prepare(args.source, args.output_dir)
    else:
        values = dotenv_values(Path(__file__).resolve().parents[1] / '.env')

        def setting(name: str) -> str:
            return os.environ.get(name) or values.get(name) or ''

        ca_bundle = setting('GIGACHAT_CA_BUNDLE_FILE')
        result = dispatch(args.source, args.output_dir, credentials=setting('GIGACHAT_CREDENTIALS'),
            scope=setting('GIGACHAT_SCOPE'), authorized=args.authorize_gigachat_test,
            ca_bundle=Path(ca_bundle) if ca_bundle else None)
    # Only explicit public result fields. No exception traceback containing local
    # variables, tokens, credentials or OAuth response bodies is printed.
    print(json.dumps({k: result[k] for k in ('status', 'model_calls', 'request_bytes', 'model',
        'model_attempts', 'oauth_attempts', 'account_read_attempts', 'returned_model', 'usage', 'errors') if k in result},
        ensure_ascii=False))
    if result['status'] not in ('prepared', 'integrity_valid'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
