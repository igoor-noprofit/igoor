"""Offline behavioral test for the speakerid pre-warm switching logic (no SpeechBrain).

Simulates the gap-between-conversations scenario the user reported: speaker A is
pre-warmed, then B talks. Drives _handle_detection directly on a stub instance
(subclass with a stub __init__ so no plugin machinery runs) and checks:
  1. stale A votes decay, so B commits on its COMMIT_VOTES-th detection
  2. the tentative badge flips to B before the commit (no more A outvoted display)
  3. 2 consecutive no-matches with speech present revert the pre-warm to unknown
  4. silence path (no detections) still honors the full prewarm_ttl
"""
import sys
import time
from collections import deque
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))
from plugins.speakerid import speakerid as sid_mod
from plugins.speakerid.speakerid import Speakerid


class FakeContext:
    def __init__(self):
        self.speaker_info = {"name": "unknown", "status": "unknown"}

    def get_context(self):
        return {"speaker_info": self.speaker_info}


class Harness(Speakerid):
    """Stand-in instance: only the state the detection state machine touches."""

    def __init__(self, cooldown=2.0):
        # deliberately NOT calling super().__init__ — no Baseplugin/SpeechBrain setup
        self.confidence_threshold_low = 0.45
        self.confidence_threshold_high = 0.51
        self.identification_cooldown = cooldown
        self.prewarm_ttl = 30.0
        self._evidence_ttl = 3.0 * cooldown
        self._last_prewarm_refresh = 0.0
        self._consecutive_no_match = 0
        self.committed_speaker = None
        self.conversation_active = False
        self.evidence_window = deque(maxlen=Speakerid.EVIDENCE_WINDOW)
        self.last_speaker = SimpleNamespace(id=None, confidence=0.0)
        self.last_phrase_speaker = SimpleNamespace(id=None, confidence=0.0)
        self._last_tentative_push = None
        self.pushes = []          # (kind, name, status) frontend messages
        self.logs = []
        self.logger = SimpleNamespace(
            info=lambda m: self.logs.append(m),
            debug=lambda m: None, warning=lambda m: None, error=lambda m: None,
        )

    def _update_speaker_context(self, speaker_name, confidence, status, method="auto"):
        self._last_tentative_push = None
        fake_ctx.speaker_info = {"name": speaker_name, "status": status, "method": method}
        self.pushes.append(("context", speaker_name, status))

    def send_message_to_frontend(self, msg):
        s = msg["speaker"]
        self.pushes.append(("tentative", s["name"], s["status"]))


fake_ctx = FakeContext()
sid_mod.context_manager = fake_ctx   # module-level singleton → point at the fake


def det(h, t, match, score, runner_up=0.0):
    """One identification at wall-clock t (seconds, frozen clock)."""
    top = [(match, score)] if match else []
    if runner_up:
        top.append(("other", runner_up))
    real_time = time.time
    time.time = lambda: t
    try:
        h._handle_detection(match, score, top)
    finally:
        time.time = real_time


def commit_A(h, base):
    """Fast-path commit of A at t=base -> pre-warm (score/margin clear the bars)."""
    det(h, base, "A", 0.70, runner_up=0.30)
    assert h._last_prewarm_refresh == base, "A's commit must refresh the pre-warm timer"
    assert fake_ctx.speaker_info["name"] == "A" and fake_ctx.speaker_info["status"] == "prewarmed"


def test_switch_to_enrolled_B():
    h = Harness(cooldown=2.0)
    commit_A(h, 1000.0)
    # A talked a bit before leaving: 2 more slow-path A votes
    det(h, 1002.0, "A", 0.48)
    det(h, 1004.0, "A", 0.48)
    # B starts at t=1010.5: A's votes are 6.5s+ old (ttl=6) and must decay out.
    # B scores clear the commit bar but not the fast-path margin -> slow path.
    cut = len(h.pushes)            # pushes from here on are B's era
    for t in (1010.5, 1012.5, 1014.5):
        det(h, t, "B", 0.52, runner_up=0.47)
    assert fake_ctx.speaker_info["name"] == "B", "B must commit on its 3rd detection"
    assert fake_ctx.speaker_info["status"] == "prewarmed"
    # Before the fix, B-era tentatives showed A (most-seen with stale votes)
    tent = [p for p in h.pushes[cut:] if p[0] == "tentative"]
    assert ("tentative", "A", "partial") not in tent, f"stale A displayed: {tent}"
    assert ("tentative", "B", "partial") in tent, f"B never displayed as tentative: {tent}"
    print("test_switch_to_enrolled_B: OK  (commits at 3rd B detection, badge shows B meanwhile)")


def test_contradiction_reverts_prewarm():
    h = Harness(cooldown=2.0)
    commit_A(h, 1000.0)
    # B (not enrolled / not matching) talks: no-match, no-match -> revert, not 30s
    det(h, 1002.0, None, 0.30)
    assert fake_ctx.speaker_info["name"] == "A", "1st no-match must not revert yet"
    det(h, 1004.0, None, 0.28)
    assert fake_ctx.speaker_info["name"] == "unknown", "2nd no-match must revert the pre-warm"
    assert fake_ctx.speaker_info["status"] == "unknown"
    assert h._last_prewarm_refresh == 0.0
    print("test_contradiction_reverts_prewarm: OK  (revert at ~4s instead of 30s TTL)")


def test_weak_A_frames_do_not_flicker_on_one_dip():
    h = Harness(cooldown=2.0)
    commit_A(h, 1000.0)
    det(h, 1002.0, "A", 0.48)      # weak but matching frame resets the streak
    det(h, 1004.0, None, 0.30)     # one isolated no-match...
    assert fake_ctx.speaker_info["name"] == "A", "isolated no-match must not revert"
    det(h, 1006.0, "A", 0.48)
    assert fake_ctx.speaker_info["name"] == "A"
    print("test_weak_A_frames_do_not_flicker_on_one_dip: OK  (streak resets on any match)")


def test_silence_keeps_full_ttl():
    h = Harness(cooldown=2.0)
    commit_A(h, 1000.0)
    # Nobody talks: only the chunk heartbeat runs _expire_stale_prewarm
    real_time = time.time

    def expire_at(t):
        time.time = lambda: t
        try:
            h._expire_stale_prewarm()
        finally:
            time.time = real_time

    expire_at(1020.0)              # 20s of silence — inside the 30s TTL
    assert fake_ctx.speaker_info["name"] == "A"
    expire_at(1031.0)              # TTL lapsed — now it reverts
    assert fake_ctx.speaker_info["name"] == "unknown"
    print("test_silence_keeps_full_ttl: OK  (30s TTL intact on the silence path)")


if __name__ == "__main__":
    test_switch_to_enrolled_B()
    test_contradiction_reverts_prewarm()
    test_weak_A_frames_do_not_flicker_on_one_dip()
    test_silence_keeps_full_ttl()
    print("\nAll speakerid pre-warm switching tests passed.")
