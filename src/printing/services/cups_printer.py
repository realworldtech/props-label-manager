import logging
import re
import subprocess
import tempfile

from printing.services.printer import PrintError

logger = logging.getLogger(__name__)


class CupsPrinterService:
    def __init__(self, queue_name: str, server: str | None = None, timeout: int = 30):
        self.queue_name = queue_name
        self.server = server
        self.timeout = timeout

    def send(self, data: bytes) -> str:
        tmp_file = None
        try:
            tmp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            tmp_file.write(data)
            tmp_file.close()

            cmd = ["lp", "-d", self.queue_name]
            if self.server:
                cmd = ["lp", "-h", self.server, "-d", self.queue_name]
            cmd.append(tmp_file.name)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            if result.returncode != 0:
                raise PrintError(
                    f"lp command failed (exit {result.returncode}): {result.stderr.strip()}"
                )

            job_id = self._parse_job_id(result.stdout)
            logger.info(
                "CUPS job submitted to %s: %s", self.queue_name, job_id or "unknown"
            )
            return job_id or ""

        except FileNotFoundError:
            raise PrintError("lp command not found. Is cups-client installed?")
        except subprocess.TimeoutExpired:
            raise PrintError(f"lp command timed out after {self.timeout}s")
        finally:
            if tmp_file is not None:
                import os

                try:
                    os.unlink(tmp_file.name)
                except OSError:
                    pass

    @staticmethod
    def _parse_job_id(stdout: str) -> str | None:
        match = re.search(r"request id is (\S+)", stdout)
        return match.group(1) if match else None
