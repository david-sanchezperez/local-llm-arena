"""Self-check mínimo: ThermalGuard detecta temperatura alta y mata el proceso."""
import time
from unittest.mock import MagicMock, patch

from thermal_guard import ThermalGuard


def _fake_nvidia_smi(temp: int):
    return MagicMock(returncode=0, stdout=f"{temp}\n")


def test_triggers_and_kills_when_over_threshold():
    guard = ThermalGuard(port=8081, max_temp_c=83, interval_s=0.01)
    with patch("subprocess.run", return_value=_fake_nvidia_smi(90)) as mock_run:
        guard.start()
        time.sleep(0.05)
        guard.stop()
        guard.join(timeout=1)
    assert guard.triggered is True
    assert any("pkill" in str(c) for c in mock_run.call_args_list)


def test_does_not_trigger_below_threshold():
    guard = ThermalGuard(port=8081, max_temp_c=83, interval_s=0.01)
    with patch("subprocess.run", return_value=_fake_nvidia_smi(50)):
        guard.start()
        time.sleep(0.05)
        guard.stop()
        guard.join(timeout=1)
    assert guard.triggered is False


if __name__ == "__main__":
    test_triggers_and_kills_when_over_threshold()
    test_does_not_trigger_below_threshold()
    print("OK")
