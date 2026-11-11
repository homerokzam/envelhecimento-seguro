"""Uso: python -m etl build [--refresh] [--sample | --years 2023,2024 --ufs DF,GO,AP]"""
import argparse
import logging
import sys

from . import build


def main():
    parser = argparse.ArgumentParser(prog="etl")
    parser.add_argument("command", choices=("build",))
    parser.add_argument("--refresh", action="store_true", help="rebaixa os meses mais recentes")
    parser.add_argument("--years", help="anos separados por vírgula (padrão: 2015–2025)")
    parser.add_argument("--ufs", help="UFs separadas por vírgula: gera uma amostra real, só para uso local")
    parser.add_argument("--workers", type=int, help="UFs lidas ao mesmo tempo (padrão: ETL_WORKERS ou 6)")
    parser.add_argument("--sample", action="store_true",
                        help=f"atalho para --years {build.SAMPLE_YEARS[0]} --ufs {','.join(build.SAMPLE_UFS)} (~72 arquivos)")
    args = parser.parse_args()
    years = [int(y) for y in args.years.split(",")] if args.years else build.SAMPLE_YEARS if args.sample else None
    ufs = [u.strip() for u in args.ufs.split(",")] if args.ufs else build.SAMPLE_UFS if args.sample else None

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    def show(done, total, stage, **detail):
        print(f"[{done}/{total}] {stage}", file=sys.stderr)

    manifest = build.run(progress=show, refresh=args.refresh, years=years, ufs=ufs, workers=args.workers)
    print("Versão ativa:", manifest["version"])


if __name__ == "__main__":
    main()
