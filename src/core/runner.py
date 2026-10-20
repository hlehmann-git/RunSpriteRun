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
        self._current: tuple | None = None        # what is playing: ("key", key) for a group's own key (a diagonal such as W+D counts as
                                                  # one key), or ("rule", index) for a Frame Group Control rule
        self._once = False                        # the sequence playing is a play-once one: it ends instead of looping
        self._done: set[int] = set()              # play-once rules that finished while their keys are still held
        self._seq: list[int] = []                 # frames of the group being played
        self._pos = 0
        self.frame = 0                            # the frame being shown
        self.playing_group: str | None = None
        self._show_start_state()

    @property
    def animating(self) -> bool:
        """True while the frame shown changes with time (a looping group of two or more frames)."""
        return self.running and (len(self._seq) > 1 or (self._once and bool(self._seq)))

    # ---- helpers --------------------------------------------------------------------------------
    def _group_for_key(self, key: str):
        return next((g for g in self.project.groups if g.key == key), None)

    def _play(self, group, loop: bool) -> None:
        self._once = not loop                         # a group that is not looped plays through once (Frame Group Control rules)
        self._seq = list(range(group.first, group.last + 1))
        self._pos = 0
        self.frame = self._seq[0]
        self.playing_group = group.name

    def _hold(self, frame: int) -> None:
        self._once = False
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
        self._done.clear()
        self.running = True
        self._show_start_state()

    def stop(self) -> None:
        """F5 again: stop and return the display to the start state. There is no pause."""
        self.held.clear()
        self._current = None
        self._done.clear()
        self.running = False
        self._show_start_state()
        # the display is static now: a start state that plays a group shows that group's first frame
        self._seq = []

    # ---- keys -----------------------------------------------------------------------------------
    def _matters(self, key: str) -> bool:
        """A key counts if it has its own group, it is one half of a diagonal that has a group, or a Frame Group Control
        rule uses it."""
        return (self._group_for_key(key) is not None
                or any(key in parts and self._group_for_key(d) is not None for d, parts in DIAGONALS.items())
                or any(key in r.keys for r in self.project.control_rules))

    def _group_named(self, name: str):
        return next((g for g in self.project.groups if g.name == name), None)

    def showing_group(self) -> str | None:
        """The group the frame on screen belongs to (frames in no group: None)."""
        return next((g.name for g in self.project.groups if g.first <= self.frame <= g.last), None)

    def _wanted(self) -> tuple | None:
        """What should play now. The Frame Group Control rules come first, top rule first: the first one whose keys are
        all held (and that has not just finished playing once) wins. Then the basic key of a group."""
        held = set(self.held)
        showing = self.showing_group()
        for i, r in enumerate(self.project.control_rules):
            if i not in self._done and r.keys and set(r.keys) <= held and self._group_named(r.group) is not None:
                # "only when showing": the rule that is already playing keeps going even though its own frames are now on screen
                if r.from_group and r.from_group != showing and ("rule", i) != self._current:
                    continue
                return ("rule", i)
        key = self.effective_key()
        return ("key", key) if key is not None else None

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
        rules = self.project.control_rules
        held = set(self.held)
        self._done = {i for i in self._done if i < len(rules) and set(rules[i].keys) <= held}   # let go of the keys: it can fire again
        now = self._wanted()
        if now is not None and now != self._current:
            if now[0] == "rule":
                r = rules[now[1]]
                self._play(self._group_named(r.group), not r.once)    # whatever was playing stops; the new group starts at its first frame
            else:
                self._play(self._group_for_key(now[1]), True)
        self._current = now

    def _rest_after(self, token: tuple) -> None:
        """Nothing playable is held any more: the resting state of what was playing. A rule uses its own 'when released'
        choice, else its group's On Release; an ignored rule stops on the group's last frame."""
        if token[0] == "rule":
            r = self.project.control_rules[token[1]] if token[1] < len(self.project.control_rules) else None
            g = self._group_named(r.group) if r is not None else None
            if g is None:
                self._hold(self.frame)
                return
            self._apply(r.release if r.release is not None else g.on_release, g.last)
        else:
            g = self._group_for_key(token[1])
            if g is not None:
                self._apply(g.on_release, g.last)

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
            self._rest_after(before)
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
        elif self._once:                          # a play-once rule ends: the next rule or key takes over
            return self._finish()
        else:
            self._pos = 0
        self.frame = self._seq[self._pos]
        return self.frame != before or len(self._seq) > 1

    def _finish(self) -> bool:
        """A play-once rule reached its last frame while its keys are still held: it will not fire again until they are
        let go, and the next matching rule (or the newest key's group) takes over; with none, its resting state."""
        before = self._current
        if before is not None and before[0] == "rule":
            self._done.add(before[1])
        self._once = False
        self._switch()
        if self._current is None and before is not None:
            self._rest_after(before)
        return True
