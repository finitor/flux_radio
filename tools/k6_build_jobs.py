"""Single-worker, local-only firmware build job runner. Never touches a radio."""
import json
from pathlib import Path
import subprocess
import sys
import threading
import uuid

ROOT = Path(__file__).resolve().parents[1]
JOBS_DIR = ROOT / 'firmware/k6-aura/out-fd6818b/web-builds'


class BuildJobs:
    def __init__(self, directory=JOBS_DIR, runner=subprocess.Popen):
        self.directory = Path(directory)
        self.runner = runner
        self._lock = threading.Lock()
        self._active = None
        self._jobs = {}

    def start(self, packs):
        from k6_feature_packs import DEFAULT, resolve
        from k6_pack_policy import POLICY, validate
        spec = json.loads(DEFAULT.read_text())
        validate(spec, json.loads(POLICY.read_text()))
        plan = resolve(spec, packs or ['base'])
        with self._lock:
            if self._active and self._active.poll() is None:
                raise ValueError('another firmware build is already running')
            self._active = None
            job_id = uuid.uuid4().hex
            folder = self.directory / job_id
            folder.mkdir(parents=True, exist_ok=False)
            log = folder / 'build.log'
            output = folder / 'pack'
            command = [sys.executable, str(ROOT / 'tools/k6.py'), 'build', *plan['packs'], '--output', str(output)]
            with log.open('wb') as stream:
                process = self.runner(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
            self._active = process
            self._jobs[job_id] = {'process': process, 'packs': plan['packs'], 'folder': folder,
                                  'command': command}
            return job_id

    def get(self, job_id):
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        code = job['process'].poll()
        output = job['folder'] / 'pack' / 'pack.lock.json'
        lock = json.loads(output.read_text()) if code == 0 and output.is_file() else None
        log = (job['folder'] / 'build.log').read_text(errors='replace')
        return {'id': job_id, 'packs': job['packs'], 'state': 'running' if code is None else ('success' if code == 0 and lock else 'failed'),
                'exit_code': code, 'log': log[-16000:], 'lock': lock, 'output': str(output.parent) if lock else None}
