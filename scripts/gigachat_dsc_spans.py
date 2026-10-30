"""Explicit second GigaChat DSC experiment; prepare offline or send once."""

import argparse
import json
import os
from pathlib import Path

from dotenv import dotenv_values

from app.records.gigachat_dsc_spans import dispatch, prepare


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'send'))
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--authorize-gigachat-span-test', action='store_true')
    args = parser.parse_args()
    if args.action == 'prepare':
        if args.baseline is None:
            parser.error('prepare requires --baseline')
        result = prepare(args.source, args.baseline, args.output_dir)
    else:
        values = dotenv_values(Path(__file__).resolve().parents[1] / '.env')

        def setting(name: str) -> str:
            return os.environ.get(name) or values.get(name) or ''

        ca = setting('GIGACHAT_CA_BUNDLE_FILE')
        result = dispatch(args.source, args.output_dir, credentials=setting('GIGACHAT_CREDENTIALS'),
            scope=setting('GIGACHAT_SCOPE'), authorized=args.authorize_gigachat_span_test, ca_bundle=Path(ca) if ca else None)
    print(json.dumps({k: result[k] for k in ('status', 'model_calls', 'request_bytes', 'source_spans', 'model_attempts',
        'returned_model', 'usage', 'errors', 'evaluation') if k in result}, ensure_ascii=False))
    if result['status'] not in ('prepared', 'integrity_valid'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
