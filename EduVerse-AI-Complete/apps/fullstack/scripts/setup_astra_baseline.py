"""Astra independent defect probe runner for baseline reproduction."""
import sys
from pathlib import Path

# Copy of Astra's independent probe test to establish baseline reproduction
astra_probe_source = Path("C:/Users/sufiy/.codex/visualizations/2026/10/22/01a1642f-ad56-77b2-89e2-fce9160e260c/astra-audit/snapshot/backend/tests/test_astra_independent.py").read_text(encoding="utf-8")
Path("S:/SY/SEM 3/MP/EduVerse_Web_Demo/backend/tests/test_astra_probes_baseline.py").write_text(astra_probe_source, encoding="utf-8")
print("Saved baseline probe test to backend/tests/test_astra_probes_baseline.py")
