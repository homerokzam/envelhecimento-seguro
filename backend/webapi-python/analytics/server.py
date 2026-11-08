"""API HTTP local para o AppHost. Só este serviço Python acessa o SUS, e apenas sob demanda."""
import csv
import io
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from . import store
from .data import dashboard, load, parse_filters, reference_weights, years_of

EXPECTED_FILES = 27 * 12 * 10  # estimativa exibida antes do primeiro download (2015–2024)


class State:
    """Base ativa em memória. Troca atômica após cada carga."""

    def __init__(self, directory):
        self.directory = directory
        self.lock = threading.Lock()
        self.rows, self.weights, self.metadata = (), None, None
        self.reload()

    def reload(self):
        found = store.active(self.directory)
        if not found:
            return
        path, manifest = found
        rows = load(path)
        meta = {key: manifest.get(key) for key in (
            "version", "createdAt", "source", "pysusVersion", "populationEdition", "caseDefinition",
            "unit", "years", "incompleteYears", "exclusions", "ignoredSexAdmissions")}
        meta["pilotOk"] = bool(manifest.get("pilot", {}).get("ok"))
        with self.lock:
            self.rows, self.weights, self.metadata = rows, reference_weights(rows), meta

    def snapshot(self):
        with self.lock:
            return self.rows, self.weights, self.metadata


class Job:
    """Um download por vez, executado em thread; falha preserva a versão ativa."""

    def __init__(self, state):
        self.state = state
        self.lock = threading.Lock()
        self.info = {"state": "idle", "done": 0, "total": 0, "stage": "", "error": None, "startedAt": None}

    def snapshot(self):
        with self.lock:
            return dict(self.info)

    def start(self, refresh):
        with self.lock:
            if self.info["state"] == "running":
                return False
            self.info = {"state": "running", "done": 0, "total": 0, "stage": "Iniciando",
                         "error": None, "startedAt": time.time()}
        threading.Thread(target=self._run, args=(refresh,), daemon=True).start()
        return True

    def _progress(self, done, total, stage):
        with self.lock:
            self.info.update(done=done, total=total, stage=stage)

    def _run(self, refresh):
        try:
            from etl import build  # noqa: PLC0415 - PySUS só é exigido ao baixar
            build.run(progress=self._progress, refresh=refresh, directory=self.state.directory)
            self.state.reload()
            result = {"state": "done", "stage": "Concluído", "error": None}
        except ModuleNotFoundError as error:
            result = {"state": "error", "error": f"Dependência ausente ({error.name}). Instale pysus e pandas."}
        except Exception as error:  # noqa: BLE001
            result = {"state": "error", "error": str(error)}
        with self.lock:
            self.info.update(result)


def create_handler(state, job):
    class Handler(BaseHTTPRequestHandler):
        def send_body(self, status, body, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, status, payload):
            self.send_body(status, json.dumps(payload, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def status_payload(self):
            _, _, metadata = state.snapshot()
            return {"hasData": metadata is not None, "metadata": metadata, "job": job.snapshot(),
                    "estimatedFiles": EXPECTED_FILES}

        def do_POST(self):
            if urlsplit(self.path).path != "/dataset/update":
                self.send_json(404, {"detail": "Rota inexistente."})
                return
            length = min(int(self.headers.get("Content-Length") or 0), 1024)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                self.send_json(400, {"detail": "Corpo inválido."})
                return
            started = job.start(refresh=bool(body.get("refresh")))
            self.send_json(202 if started else 409,
                           self.status_payload() if started else {"detail": "Já existe um download em andamento."})

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == "/health":
                self.send_json(200, {"status": "ok"})
                return
            if url.path == "/dataset/status":
                self.send_json(200, self.status_payload())
                return
            if url.path not in ("/dashboard", "/export.csv"):
                self.send_json(404, {"detail": "Rota inexistente."})
                return
            rows, weights, metadata = state.snapshot()
            if metadata is None:
                if url.path == "/dashboard":
                    self.send_json(200, {"empty": True, "metadata": None})
                else:
                    self.send_json(409, {"detail": "Nenhuma base carregada."})
                return
            try:
                filters = parse_filters(parse_qs(url.query, keep_blank_values=True, max_num_fields=12), years_of(rows))
            except ValueError as error:
                self.send_json(400, {"detail": str(error) if "intervalo" in str(error) else
                                     "Filtros inválidos. Confira o período, a UF, a faixa etária e o sexo."})
                return
            result = dashboard(rows, filters, metadata, weights)
            if url.path == "/dashboard":
                self.send_json(200, result)
                return
            out = io.StringIO(newline="")
            writer = csv.writer(out)
            for line in (
                f"fonte: {metadata['source']}", f"versão: {metadata['version']}", f"extração: {metadata['createdAt']}",
                f"população: {metadata['populationEdition']}", f"definição de caso: {metadata['caseDefinition']}",
                f"unidade: {metadata['unit']}", f"filtros: {json.dumps(filters, ensure_ascii=False)}",
                f"exclusões: {json.dumps(metadata['exclusions'], ensure_ascii=False)}",
                f"sexo ignorado (internações, incluídas em Ambos): {result['notes']['ignoredSexAdmissions']}",
            ):
                writer.writerow([f"# {line}"])
            writer.writerow(["origem", "versao", "inicio", "fim", "idade", "sexo", "uf", "situacao",
                             "internacoes", "populacao_ano", "taxa_100mil", "taxa_padronizada_100mil",
                             "obitos", "mortalidade_percentual", "permanencia_media_dias",
                             "valor_aprovado_brl_nominal", "baixo_volume"])
            for item in result["territories"]:
                m = item["metrics"] or {}
                writer.writerow([metadata["source"], metadata["version"], filters["start"], filters["end"],
                                 filters["age"] or "60+", filters["sex"] or "F+M", item["key"],
                                 "parcial" if m.get("partial") else "disponível" if m else "indisponível",
                                 *(m.get(key) for key in ("admissions", "population", "rate", "standardRate",
                                                         "deaths", "mortality", "meanStay", "approved", "lowVolume"))])
            self.send_body(200, out.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8")
    return Handler


def main():
    state = State(store.data_dir())
    job = Job(state)
    with ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("PORT", "8091"))),
                             create_handler(state, job)) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
