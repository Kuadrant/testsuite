"""Module containing facade for hyperfoil manipulation"""
import shutil
import typing
from io import StringIO
from pathlib import Path

import backoff
import yaml
from apyproxy import ApyProxy


class StartedRun:
    """Hyperfoil run that was already started"""

    def __init__(self, client, run_id) -> None:
        super().__init__()
        self.client = client
        self.run_id = run_id

    def wait(self, timeout: int) -> dict:
        """Waits until the run completes"""

        @backoff.on_predicate(backoff.constant, lambda x: not x["completed"], interval=5, max_time=timeout)
        def _wait():
            response = self.client.run._(self.run_id).get()
            return response.json()

        return _wait()

    def stats(self):
        """Returns Stats for the run, needs to be finished"""
        return self.client.run._(self.run_id).stats.all.json.get().json()

    def report(self, name, directory):
        """Returns Stats for the run, needs to be finished"""
        with self.client.run._(self.run_id).report.get(stream=True) as response:
            response.raise_for_status()
            with Path(directory).joinpath(name).open("wb") as file:
                shutil.copyfileobj(response.raw, file)


class Benchmark:
    """Hyperfoil Benchmark object"""

    def __init__(self, client, name) -> None:
        super().__init__()
        self.client = client
        self.name = name

    def start(self, desc: str = "", **params) -> StartedRun:
        """Starts the Benchmark and returns a specific Run that was started"""
        run_id = (
            self.client.benchmark._(self.name).start.get(params={"templateParam": params, "desc": desc}).json()["id"]
        )
        return StartedRun(self.client, run_id)


class Hyperfoil:
    """Facade for Hyperfoil client"""

    def __init__(self, url) -> None:
        super().__init__()
        self.client = ApyProxy(url)

    def create_benchmark(
        self,
        name,
        agents: dict,
        http: dict,
        benchmark: dict,
        additional_files: dict[str, typing.IO],
    ) -> Benchmark:
        """
        Creates or overrides benchmark

        :param name: Name of the new benchmark, if already defined in the definition, it will be overriden
        :param agents: Dict representation for agents section, will be used only if missing in the definition
        https://hyperfoil.io/userguide/benchmark/agents.html
        :param http: Dict representation for http section, will be used only if missing in the definition
        https://hyperfoil.io/userguide/benchmark/http.html
        :param benchmark: Definition of the benchmark in the dict form, may contain template parameters
        :param additional_files: All files handles (already opened) that will be included in the request,
         can be closed afterwards
        :return: Benchmark
        """
        additional_files = additional_files or {}
        if "agents" not in benchmark:
            benchmark["agents"] = agents["agents"]
        if "http" not in benchmark:
            benchmark["http"] = http["http"]
        benchmark["name"] = name
        files = {"benchmark": StringIO(yaml.dump(benchmark)), **additional_files}  # type: ignore
        self.client.benchmark.post(files=files)
        return Benchmark(self.client, name)
