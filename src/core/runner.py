"""RunSpriteRun behaviour (FR-3.3, FR-3.10): which frame is shown, given the start state, the keys held
and the time passing. No UI code here; the app calls tick() once per frame time (1 / fps)."""
from __future__ import annotations

from .project import Project, Rule


class Runner:
    def __init__(self, project: Project) -> None:
        self.project = project
        self.running = False
        self.held: list[str] = []                 # assigned keys held, oldest first
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
        self.running = True
        self._show_start_state()

    def stop(self) -> None:
        """F5 again: stop and return the display to the start state. There is no pause."""
        self.held.clear()
        self.running = False
        self._show_start_state()
        # the display is static now: a start state that plays a group shows that group's first frame
        self._seq = []

    # ---- keys -----------------------------------------------------------------------------------
    def press(self, key: str) -> bool:
        """An assigned key goes down. Returns False if it was ignored (not running, no group, auto-repeat)."""
        g = self._group_for_key(key)
        if not self.running or g is None or key in self.held:
            return False
        self.held.append(key)
        self._play(g, True)                       # whatever was playing stops; the group starts from its first frame
        return True

    def release(self, key: str) -> bool:
        if not self.running or key not in self.held:
            return False
        was_top = self.held[-1] == key
        self.held.remove(key)
        g = self._group_for_key(key)
        if self.held:
            if was_top:                           # the most recently pressed key that is still held takes over
                self._play(self._group_for_key(self.held[-1]), True)
        elif g is not None:                       # no assigned key is held: the released group's resting state
            self._apply(g.on_release, g.last)     # an ignored rule stops on the group's last frame
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
