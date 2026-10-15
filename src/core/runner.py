"""RunSpriteRun behaviour (FR-3.3, FR-3.10): which frame is shown, given the start state, the keys held
and the time passing. No UI code here; the app calls tick() once per frame time (1 / fps)."""
from __future__ import annotations

from .project import Project, Rule
from .rules import DIAGONALS


class Runner:
    def __init__(self, project: Project) -> None:
        self.project = project
        self.running = False
        self.held: list[str] = []                 # keys held that matter (own group, or part of a diagonal group), oldest first
        self._current: str | None = None          # the key whose group is playing (a diagonal such as W+D counts as one key)
        self._seq: list[int] = []                 # frames of the group being played
        self._pos = 0
        self.frame = 0                            # the frame being shown
        self.playing_group: str | None = None
        self._show_start_state()

    @property
    def animating(self) -> bool:
        """True while the frame shown changes with time (a looping group of two or more frames)."""
        return self.running and len(self._seq) > 1

    # ---- helpers --------------------------------------------------------------------------------
    def _group_for_key(self, key: str):
        return next((g for g in self.project.groups if g.key == key), None)

    def _play(self, group, loop: bool) -> None:
        self._seq = list(range(group.first, group.last + 1))
        self._pos = 0
        self.frame = self._seq[0]
        self.playing_group = group.name

    def _hold(self, frame: int) -> None:
        self._seq = []
        self._pos = 0
        self.frame = frame
        self.playing_group = None

    def _apply(self, rule: Rule | None, fallback_frame: int) -> None:
        """Apply a resting or start rule. A missing rule, or one whose target is gone, holds fallback_frame."""
        if rule is not None and rule.kind == "frame":
            for i, f in enumerate(self.project.frames):
                if f.label == rule.target:
                    self._hold(i)
                    return
        elif rule is not None and rule.kind == "group":
            g = next((g for g in self.project.groups if g.name == rule.target), None)
            if g is not None:
                if rule.loop:
                    self._play(g, True)               # a resting loop animates
                else:
                    self._hold(g.first)               # Loop off: nothing animates, the group's first frame is shown
                return
        self._hold(fallback_frame)

    def _show_start_state(self) -> None:
        """The start state; if it was never set (or its target is gone) frame 1 is held."""
        self._apply(self.project.start_state, 0)

    # ---- F5 -------------------------------------------------------------------------------------
    def start(self) -> None:
        self.held.clear()
        self._current = None
        self.running = True
        self._show_start_state()

    def stop(self) -> None:
        """F5 again: stop and return the display to the start state. There is no pause."""
        self.held.clear()
        self._current = None
        self.running = False
        self._show_start_state()
        # the display is static now: a start state that plays a group shows that group's first frame
        self._seq = []

    # ---- keys -----------------------------------------------------------------------------------
    def _matters(self, key: str) -> bool:
        """A key counts if it has its own group, or it is one half of a diagonal that has a group."""
        return self._group_for_key(key) is not None or any(
            key in parts and self._group_for_key(d) is not None for d, parts in DIAGONALS.items())

    def effective_key(self) -> str | None:
        """The key whose group should play: a diagonal that has a group wins (so W then A, or A then W, both give
        W+A); otherwise the most recently pressed held key that has a group."""
        for diag, (a, b) in DIAGONALS.items():
            if a in self.held and b in self.held and self._group_for_key(diag) is not None:
                return diag
        return next((k for k in reversed(self.held) if self._group_for_key(k) is not None), None)

    def lit(self) -> list[str]:
        """Everything to light on the key pad: the keys held, plus a diagonal when both its keys are held."""
        extra = [d for d, (a, b) in DIAGONALS.items() if a in self.held and b in self.held]
        return list(self.held) + extra

    def _switch(self) -> None:
        now = self.effective_key()
        if now is not None and now != self._current:
            self._play(self._group_for_key(now), True)     # whatever was playing stops; the new group starts at its first frame
        self._current = now

    def press(self, key: str) -> bool:
        """A key goes down. Returns False if it was ignored (not running, no group for it, auto-repeat)."""
        if not self.running or not self._matters(key) or key in self.held:
            return False
        self.held.append(key)
        self._switch()
        return True

    def release(self, key: str) -> bool:
        if not self.running or key not in self.held:
            return False
        before = self._current
        self.held.remove(key)
        self._switch()
        if self._current is None and before is not None:   # nothing playable is held: the released group's resting state
            g = self._group_for_key(before)
            self._apply(g.on_release, g.last)              # an ignored rule stops on the group's last frame
        return True

    def release_all(self) -> None:
        """Window lost focus, or keys were let go while something else had the keyboard."""
        while self.held:
            self.release(self.held[-1])

    # ---- time -----------------------------------------------------------------------------------
    def tick(self) -> bool:
        """One frame time has passed. Returns True if the frame shown changed."""
        if not self.running or not self._seq:
            return False
        before = self.frame
        if self._pos + 1 < len(self._seq):
            self._pos += 1
        else:                                     # only looping sequences are ever played
            self._pos = 0
        self.frame = self._seq[self._pos]
        return self.frame != before or len(self._seq) > 1
