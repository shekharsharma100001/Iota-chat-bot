#!/usr/bin/env python3
import logging
import sys
from datetime import datetime
from pathlib import Path

class SafeStreamHandler(logging.StreamHandler):
    """Stream handler that won’t crash on unencodable chars (Windows consoles)."""
    def emit(self, record):
        try:
            super().emit(record)
        except UnicodeEncodeError:
            try:
                msg = self.format(record)
                enc = getattr(self.stream, "encoding", None) or "utf-8"
                safe = msg.encode(enc, errors="replace").decode(enc, errors="replace")
                self.stream.write(safe + self.terminator)
                self.flush()
            except Exception:
                # last-resort: swallow logging failure
                pass

def setup_logging():
    Path("logs").mkdir(exist_ok=True)

    # try to reconfigure std streams early (Python 3.7+)
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(
                f'logs/iota_bot_{datetime.now().strftime("%Y%m%d")}.log',
                encoding="utf-8"  # ← important
            ),
            SafeStreamHandler()  # ← tolerant stream logging
        ],
        force=True,  # override any prior basicConfig calls
    )
    return logging.getLogger("IotaBot")

logger = setup_logging()
