"""Background catalog jobs backed by the unified K6 CLI."""
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
        self._radio_jobs = {}

    def start(self, packs, theme='flux'):
        from k6_feature_packs import DEFAULT, resolve
        from k6_pack_policy import POLICY, validate
        spec = json.loads(DEFAULT.read_text())
        validate(spec, json.loads(POLICY.read_text()))
        plan = resolve(spec, packs or ['base'], theme)
        with self._lock:
            if self._active and self._active.poll() is None:
                raise ValueError('another firmware build is already running')
            self._active = None
            job_id = uuid.uuid4().hex
            folder = self.directory / job_id
            folder.mkdir(parents=True, exist_ok=False)
            log = folder / 'build.log'
            output = folder / 'pack'
            command = [sys.executable, str(ROOT / 'tools/k6.py'), 'build', *plan['packs'], '--output', str(output), '--theme', plan['theme']]
            with log.open('wb') as stream:
                process = self.runner(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
            self._active = process
            self._jobs[job_id] = {'process': process, 'packs': plan['packs'], 'theme': plan['theme'], 'folder': folder,
                                  'command': command}
            return job_id

    def start_radio(self, build_id, action, port, key_file, already_update=False):
        with self._lock:
            build = self.get(build_id)
            if build['state'] != 'success':
                raise ValueError('build must finish successfully before provisioning')
            job_id = uuid.uuid4().hex
            command = [sys.executable, '-u', str(ROOT / 'tools/k6.py'),
                       'flash-pack' if action == 'flash' else 'install-pack',
                       build['output'], '--port', port,
                       '--preview' if action == 'preview' else '--yes']
            if key_file:
                command += ['--key-file', key_file]
            if already_update:
                command.append('--already-update')
            log = self.directory / build_id / f'radio-{job_id}.log'
            with log.open('wb') as stream:
                process = self.runner(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                      stdin=subprocess.DEVNULL)
            self._radio_jobs[job_id] = (build_id, action, process, log)
            return job_id

    def get_radio(self, build_id, job_id):
        owner, action, process, log = self._radio_jobs[job_id]
        if owner != build_id:
            raise KeyError(job_id)
        code = process.poll()
        return {'action': action, 'state': 'running' if code is None else ('success' if code == 0 else 'failed'),
                'log': log.read_text(errors='replace')[-16000:]}

    def get(self, job_id):
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        code = job['process'].poll()
        output = job['folder'] / 'pack' / 'pack.lock.json'
        lock = json.loads(output.read_text()) if code == 0 and output.is_file() else None
        log = (job['folder'] / 'build.log').read_text(errors='replace')
        return {'id': job_id, 'packs': job['packs'], 'theme': job['theme'], 'state': 'running' if code is None else ('success' if code == 0 and lock else 'failed'),
                'exit_code': code, 'log': log[-16000:], 'lock': lock, 'output': str(output.parent) if lock else None}
