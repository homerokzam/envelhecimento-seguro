"""Uso: python -m etl build [--refresh] | python -m etl pilot"""
import argparse
import sys

from . import build


def main():
    parser = argparse.ArgumentParser(prog="etl")
    parser.add_argument("command", choices=("build",))
    parser.add_argument("--refresh", action="store_true", help="rebaixa os meses mais recentes")
    args = parser.parse_args()

    def show(done, total, stage):
        print(f"[{done}/{total}] {stage}", file=sys.stderr)

    manifest = build.run(progress=show, refresh=args.refresh)
    print("Versão ativa:", manifest["version"])


if __name__ == "__main__":
    main()
