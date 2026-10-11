#!/usr/bin/env python3
# engine_lab.py — EngineLab: an interactive tutor for game engine architecture.
#
#   pip install PySide6
#   python engine_lab.py              # run the app
#   python engine_lab.py --selftest   # headless CI harness (exit 0 = all green)
#
# 23 pages · 18 animated diagrams · 40 achievements · 1 shared event bus.

import json
import math
import random
import re as _re
import struct as _struct
import sys
import time
import zlib
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QImage, QLineF,
                           QKeySequence, QLinearGradient, QPainter, QPen,
                           QPolygonF, QShortcut, QRadialGradient)
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QPlainTextEdit, QPushButton,
    QRadioButton, QScrollArea, QSlider, QStackedWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

# ------------------------------------------------------------------ palette -
C_BG, C_PANEL, C_PANEL2, C_BORDER = "#141518", "#1e2024", "#26282e", "#2f3238"
C_TEXT, C_DIM, C_ACCENT = "#e8e8e8", "#9aa0a6", "#4fc3f7"
C_GREEN, C_ORANGE, C_PINK = "#66bb6a", "#ffa726", "#ec407a"
C_PURPLE, C_RED, C_YELLOW = "#ab47bc", "#ef5350", "#ffee58"
PALETTE = [C_ACCENT, C_GREEN, C_ORANGE, C_PINK, C_PURPLE, C_YELLOW]

STYLESHEET = """
* { font-family:'Segoe UI','Ubuntu',sans-serif; font-size:13px; color:#e8e8e8; }
QMainWindow, QWidget { background-color:#141518; }
QLabel#h1 { font-size:21px; font-weight:700; }
QLabel#h2 { font-size:15px; font-weight:600; color:#4fc3f7; }
QLabel#dim { color:#9aa0a6; }
QPushButton { background-color:#26282e; border:1px solid #34373f; border-radius:6px; padding:7px 12px; }
QPushButton:hover { border-color:#4fc3f7; }
QPushButton:pressed { background-color:#1e2024; }
QPushButton:checked { background-color:#4fc3f7; border-color:#4fc3f7; color:#10151a; font-weight:600; }
QPushButton#nav { text-align:left; padding:8px 12px; border:none; background:transparent; color:#c7cdd4; }
QPushButton#nav:hover { color:#ffffff; background-color:#22242a; }
QPushButton#nav:checked { background-color:#26323d; color:#4fc3f7; font-weight:700; border:none; }
QListWidget, QTableWidget, QPlainTextEdit { background:#1b1d21; border:1px solid #2f3238; border-radius:6px; }
QListWidget::item { padding:3px 5px; border-radius:4px; }
QListWidget::item:selected { background:#2b3b46; color:#dfe9f0; }
QTableWidget { gridline-color:#2a2d33; }
QHeaderView::section { background:#22242a; border:none; padding:3px 5px; color:#9aa0a6; }
QSlider::groove:horizontal { height:6px; background:#26282e; border-radius:3px; }
QSlider::sub-page:horizontal { background:#4fc3f7; border-radius:3px; }
QSlider::handle:horizontal { width:14px; height:14px; margin:-5px 0; border-radius:7px; background:#4fc3f7; }
QCheckBox, QRadioButton { spacing:8px; padding:1px 0; }
QGroupBox { border:1px solid #2f3238; border-radius:8px; margin-top:13px; padding:9px 8px 5px 8px; font-weight:600; }
QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 4px; color:#9aa0a6; }
QComboBox { background:#26282e; border:1px solid #34373f; border-radius:6px; padding:5px 9px; }
QComboBox QAbstractItemView { background:#22242a; selection-background-color:#2b3b46; }
QToolTip { background:#22242a; color:#e8e8e8; border:1px solid #34373f; padding:4px; }
QScrollArea { background:transparent; border:none; }
QDialog { background:#141518; }
"""

def mono(pt: int = 9) -> QFont:
    f = QFont()
    f.setFamilies(["Consolas", "Menlo", "DejaVu Sans Mono", "Courier New"])
    f.setPointSize(pt)
    return f

def page_header(title: str, sub: str) -> QWidget:
    w = QWidget()
    v = QVBoxLayout(w); v.setContentsMargins(0, 0, 0, 4); v.setSpacing(2)
    t = QLabel(title); t.setObjectName("h1")
    s = QLabel(sub); s.setObjectName("dim"); s.setWordWrap(True)
    v.addWidget(t); v.addWidget(s)
    return w

def diag_header(title: str, desc: str) -> QWidget:
    w = QWidget()
    v = QVBoxLayout(w); v.setContentsMargins(0, 0, 0, 2); v.setSpacing(3)
    t = QLabel(title); t.setObjectName("h2")
    d = QLabel(desc); d.setObjectName("dim"); d.setWordWrap(True)
    v.addWidget(t); v.addWidget(d)
    return w

def lerp(a, b, k): return a + (b - a) * k

def _qc(hexcolor, alpha):
    c = QColor(hexcolor); c.setAlpha(int(alpha)); return c

def _mk_slider(lo, hi, val, w=110):
    s = QSlider(Qt.Horizontal); s.setRange(lo, hi); s.setValue(val)
    s.setMaximumWidth(w); return s


# --------------------------------------------------------------- event bus --
@dataclass
class EngineEvent:
    name: str
    payload: dict = field(default_factory=dict)

class EventBus(QObject):
    """Publish/subscribe hub — every system in this app talks through here."""
    event_fired = Signal(object)

    def __init__(self):
        super().__init__()
        self._subs = defaultdict(list)
        self.counts = defaultdict(int)

    def subscribe(self, name, fn): self._subs[name].append(fn)

    def emit(self, name, **payload):
        self.counts[name] += 1
        ev = EngineEvent(name, payload)
        for fn in self._subs.get(name, ()):
            fn(ev)
        self.event_fired.emit(ev)


# ------------------------------------------------------------ achievements --
ACH_DEFS = [
    ("first_spawn",     "👶", "Hello, Entity",      "Spawn your first entity in the ECS playground"),
    ("mass_extinction", "☠️", "Mass Extinction",    "Manually destroy 10 entities"),
    ("compositional",   "🧩", "Compositional",      "Toggle a component on an entity"),
    ("spiral_survivor", "🌀", "Spiral Survivor",    "Trigger the spiral-of-death guard"),
    ("cache_money",     "💰", "Cache Money",        "Score 5 cache hits in the Resource Manager"),
    ("frustum_friend",  "✂️", "Frustum Friend",     "Cull 500 objects in the Rendering lab"),
    ("prune_head",      "🌲", "Prune Head",         "Save 5000 narrow-phase tests with the grid"),
    ("remapper",        "🎮", "Remapper",           "Rebind an input action"),
    ("certified",       "🎓", "Certified Architect","Score 9+ on the quiz"),
    ("full_stack",      "🥞", "Full Stack",         "Trace a keypress through the engine layers"),
    ("job_thief",       "🥷", "Sticky Fingers",     "Catch a work-steal in the threading diagram"),
    ("ghost_hunter",    "👻", "Ghost Hunter",       "Occlusion-cull 500 objects"),
    ("net_veteran",     "🕰️", "Time Traveler",      "Watch snapshot interpolation for 30 s"),
    ("checkpoint",      "🧾", "Checkpoint",         "Save and restore a world"),
    ("mod_machine",     "🗡️", "Mod Machine",        "Resolve a conflict between two active mods"),
    ("ship_it",         "🚢", "Ship It",            "Boot the Engine Builder with all 8 modules"),
    ("hot_spot",        "🔥", "Hot Spot Hunter",    "Inspect an expensive span in the Profiler"),
    ("polyglot",        "🌍", "Polyglot",           "Preview a right-to-left language"),
    ("bandwidth_hero",  "📡", "Bandwidth Hero",     "Finish a delta patch that saved ≥50%"),
    ("butterfly",       "🦋", "Butterfly Effect",   "Witness a replay desync"),
    ("deterministic",   "🧮", "Deterministic",      "Complete a hash-verified replay"),
    ("build_master",    "🏭", "Build Master",       "Skip 3+ assets in an incremental build"),
    ("trailblazer",     "🧭", "Trailblazer",        "Complete the guided tour"),
    ("lag_lived",       "🐌", "Feel the Lag",       "Play 8 s with client prediction OFF"),
    ("rubber_band",     "🪀", "Rubber Band",        "Survive a prediction correction > 1.2 units"),
    ("shader_wizard",   "🧙", "Shader Wizard",      "Compile 3 shaders in the Shader Lab"),
    ("hot_fix",         "🔧", "Hot Fix",            "Recover from a broken shader"),
    ("animator",        "🕺", "Keyframe Kung-Fu",   "Catch the blend zone between walk and run"),
    ("eureka",          "💡", "Admissible",         "A* explores ≤75% of greedy's nodes, equal cost"),
    ("bowling",         "🎳", "Tunnel Vision",      "Fire a projectile through the platform"),
    ("sleepy",          "😴", "Let Them Sleep",     "Rest 6 bodies to sleep at once"),
    ("worldsmith",      "⛰️", "Worldsmith",         "Generate 5 seeded worlds"),
    ("frugal",          "🏦", "Defragmenter",       "Fragment the heap ≥30% while the pool stays 0%"),
    ("bt_master",       "🌿", "Branch Manager",     "Trigger a chase in the behavior tree"),
    ("strongarm",       "🦾", "Strong Arm",         "Solve a two-bone IK target by dragging"),
    ("contortion",      "🤸", "Contortionist",      "Flip the elbow to the mirrored solution"),
    ("acne_hunter",     "🩹", "Acne Hunter",        "Meet shadow acne — bias too low"),
    ("peter_pan",       "🧚", "Peter Panning",      "Detach shadows — bias too high"),
    ("wide_angle",      "📷", "Wide Angle",         "Push FOV past 100°"),
    ("bloomlord",       "🌟", "Bloom Lord",         "Stack bloom, +EV exposure and a warm grade"),
]
ACH_LOOKUP = {a: (e, t, d) for a, e, t, d in ACH_DEFS}

class Achievements(QObject):
    """Listens on the bus and unlocks achievements — the app dogfoods the
    pattern it teaches. High-frequency stats arrive batched (1 Hz)."""
    unlocked_sig = Signal(str, str, str)

    def __init__(self, bus):
        super().__init__()
        self.bus, self.armed = bus, False
        self.unlocked, self.unlocked_at = set(), {}
        self.count = defaultdict(int)
        self.path = Path.home() / ".enginelab_achievements.json"
        try:
            self.unlocked = set(json.loads(self.path.read_text()).get("ids", []))
        except Exception:
            pass
        for name, fn in {
            "entity_spawned":    lambda ev: self._bump("spawns", "first_spawn", 1),
            "entity_destroyed":  self._on_destroy,
            "component_toggled": lambda ev: self.unlock("compositional"),
            "spiral_guard":      lambda ev: self.unlock("spiral_survivor"),
            "cache_hit":         lambda ev: self._bump("cache", "cache_money", 5),
            "action_rebound":    lambda ev: self.unlock("remapper"),
            "cull_stats":        self._on_cull,
            "broadphase_stats":  self._on_bp,
            "quiz_finished":     self._on_quiz,
            "layer_traced":      lambda ev: self.unlock("full_stack"),
            "job_stolen":        lambda ev: self.unlock("job_thief"),
            "occluded_stats":    self._on_occl,
            "net_stats":         self._on_net,
            "checkpoint_made":   lambda ev: self.unlock("checkpoint"),
            "mod_conflict":      lambda ev: self.unlock("mod_machine"),
            "capstone_complete": lambda ev: self.unlock("ship_it"),
            "profiler_inspect":  lambda ev: self.unlock("hot_spot"),
            "loc_language":      lambda ev: self.unlock("polyglot") if ev.payload.get("rtl") else None,
            "patch_saved":       self._on_patch,
            "replay_desync":     lambda ev: self.unlock("butterfly"),
            "replay_verified":   lambda ev: self.unlock("deterministic"),
            "build_done":        self._on_build,
            "tour_complete":     lambda ev: self.unlock("trailblazer"),
            "lag_lived":         lambda ev: self.unlock("lag_lived"),
            "net_corrected":     lambda ev: self.unlock("rubber_band"),
            "shader_ok":         lambda ev: self._bump("shader_ok", "shader_wizard", 3),
            "shader_recovered":  lambda ev: self.unlock("hot_fix"),
            "anim_blended":      lambda ev: self.unlock("animator"),
            "astar_win":         lambda ev: self.unlock("eureka"),
            "tunnelled":         lambda ev: self.unlock("bowling"),
            "bodies_asleep":     lambda ev: self.unlock("sleepy"),
            "world_generated":   lambda ev: self._bump("worlds", "worldsmith", 5),
            "heap_fragged":      lambda ev: self.unlock("frugal"),
            "bt_chase":          lambda ev: self.unlock("bt_master"),
            "ik_solved":         lambda ev: self.unlock("strongarm"),
            "ik_flipped":        lambda ev: self.unlock("contortion"),
            "shadow_acne":       lambda ev: self.unlock("acne_hunter"),
            "peter_panning":     lambda ev: self.unlock("peter_pan"),
            "camera_wide":       lambda ev: self.unlock("wide_angle"),
            "post_stacked":      lambda ev: self.unlock("bloomlord"),
        }.items():
            bus.subscribe(name, fn)

    def _bump(self, key, ach, goal):
        self.count[key] += 1
        if self.count[key] >= goal: self.unlock(ach)

    def _on_destroy(self, ev):
        if ev.payload.get("user"): self._bump("kills", "mass_extinction", 10)

    def _on_cull(self, ev):
        if ev.payload.get("total", 0) >= 500: self.unlock("frustum_friend")

    def _on_bp(self, ev):
        if ev.payload.get("saved", 0) >= 5000: self.unlock("prune_head")

    def _on_occl(self, ev):
        if ev.payload.get("saved", 0) >= 500: self.unlock("ghost_hunter")

    def _on_net(self, ev):
        if ev.payload.get("interp_secs", 0) >= 30: self.unlock("net_veteran")

    def _on_quiz(self, ev):
        if ev.payload.get("score", 0) >= 9: self.unlock("certified")

    def _on_patch(self, ev):
        if ev.payload.get("saved_pct", 0) >= 50: self.unlock("bandwidth_hero")

    def _on_build(self, ev):
        if ev.payload.get("skipped", 0) >= 3: self.unlock("build_master")

    def unlock(self, aid):
        if aid in self.unlocked or not self.armed: return
        self.unlocked.add(aid)
        self.unlocked_at[aid] = time.time()
        try:
            self.path.write_text(json.dumps({"ids": sorted(self.unlocked)}))
        except Exception:
            pass
        emoji, title, desc = ACH_LOOKUP[aid]
        self.unlocked_sig.emit(emoji, title, desc)

class ToastOverlay(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.toasts = []
        self.timer = QTimer(self); self.timer.timeout.connect(self._tick)

    def pop(self, emoji, title, desc):
        self.toasts.append([emoji, title, desc, time.monotonic()])
        if not self.timer.isActive(): self.timer.start(33)
        self.raise_(); self.update()

    def _tick(self):
        now = time.monotonic()
        self.toasts = [t for t in self.toasts if now - t[3] < 4.2]
        self.update()
        if not self.toasts: self.timer.stop()

    def paintEvent(self, e):
        if not self.toasts: return
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        y = 14.0
        for emoji, title, desc, t0 in reversed(self.toasts[-4:]):
            age = time.monotonic() - t0
            a = min(1.0, age / 0.25) * min(1.0, max(0.0, (4.2 - age) / 0.5))
            if a <= 0: continue
            tw, th = 340, 66; x = self.width() - tw - 14
            p.setBrush(QColor(30, 32, 38, int(238 * a)))
            p.setPen(QPen(QColor(255, 209, 102, int(210 * a)), 1))
            p.drawRoundedRect(QRectF(x, y, tw, th), 10, 10)
            for (txt, col, fnt, rect) in (
                    (f"{emoji}  ACHIEVEMENT UNLOCKED", C_DIM, mono(8),
                     QRectF(x + 12, y + 7, tw - 24, 14)),
                    (title, C_ACCENT, mono(10),
                     QRectF(x + 12, y + 22, tw - 24, 18)),
                    (desc, C_TEXT, mono(8),
                     QRectF(x + 12, y + 41, tw - 24, 22))):
                cc = QColor(col); cc.setAlpha(int(255 * a))
                p.setPen(cc); p.setFont(fnt)
                p.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap, txt)
            y += th + 10


# ================================================================= OVERVIEW =
SUBSYSTEMS = {
    "Game Loop": dict(color=C_ACCENT,
        desc="The heartbeat of the engine. Every frame it reads input, advances the simulation (update) and draws the world (render). All other systems are orchestrated from here.",
        concepts=["delta time (dt)", "fixed vs. variable timestep", "the accumulator pattern", "render interpolation", "'spiral of death'"],
        engines="Unity: PlayerLoop • Unreal: FEngineLoop • Godot: Main::iteration()"),
    "ECS / Entities": dict(color=C_GREEN,
        desc="Composition over inheritance: entities are just IDs, components are plain data, systems are functions that transform every entity owning a given component set.",
        concepts=["entity = ID", "component = data", "system = behavior", "data-oriented design & cache locality", "vs. deep inheritance trees"],
        engines="Unity DOTS • Unreal Actors+Components (hybrid) • Godot Nodes (tree alternative) • Bevy, EnTT"),
    "Animation": dict(color=C_PINK,
        desc="Turns sparse authored keyframes into motion: interpolation fills the gaps between poses, blending mixes whole clips, IK snaps hands and feet to world targets.",
        concepts=["keyframes & interpolation", "clip blending / blend spaces", "skeletons & skinning", "IK (analytic & iterative)", "state machines with hysteresis"],
        engines="Unity Mecanim • Unreal Sequencer/Control Rig • Godot AnimationTree"),
    "Rendering": dict(color=C_PINK,
        desc="Turns scene state into pixels: culls what's invisible, sorts drawables, batches draw calls, shades fragments, then grades the finished frame.",
        concepts=["cull → sort → draw pipeline", "shaders (vertex/fragment)", "draw-call batching & instancing", "forward vs. deferred", "shadows & post-processing"],
        engines="Unity URP/HDRP • Unreal RDG/Lumen • Godot RenderingServer • Vulkan/D3D12/Metal"),
    "Physics": dict(color=C_ORANGE,
        desc="Integrates forces and resolves collisions so objects move believably. A cheap broad phase prunes candidate pairs before narrow-phase tests and impulse response.",
        concepts=["integration (semi-implicit Euler)", "broad phase vs. narrow phase", "impulse response & restitution", "tunnelling, substeps & CCD", "sleeping & islands"],
        engines="PhysX (Unity/Unreal) • Jolt • Box2D • Godot Physics"),
    "AI": dict(color=C_YELLOW,
        desc="Decides what agents do (behavior trees) and how they get there (pathfinding): BFS, Dijkstra, greedy best-first and A* over navmeshes or grids.",
        concepts=["behavior trees / FSMs / GOAP", "A* and admissible heuristics", "navmesh generation", "steering & crowd sim", "utility AI"],
        engines="Unreal Behavior Trees/Navigation • Unity NavMesh+ML-Agents • Godot NavigationServer"),
    "Audio": dict(color=C_PURPLE,
        desc="Mixes and plays sound: streams music, schedules one-shots, routes sources through buses, applies 3D spatialization and effects like reverb.",
        concepts=["mixing buses & channels", "2D vs. 3D spatial audio", "streaming vs. in-memory samples", "DSP effects"],
        engines="FMOD & Wwise (middleware) • Godot AudioServer • XAudio2"),
    "Resources": dict(color="#26c6da",
        desc="Loads, caches and unloads assets so nothing is read from disk twice and memory stays within budget — fed by a build pipeline that compiles sources into runtime formats.",
        concepts=["handle-based access", "reference counting & pooling", "async loading / world streaming", "content-addressed builds", "allocator choice by lifetime"],
        engines="Unity Addressables • Unreal Asset Manager • Godot Resource system"),
    "Scripting": dict(color="#ff7043",
        desc="The gameplay layer on top of the engine — the code or visual logic designers iterate on, usually hot-reloadable and kept separate from engine internals.",
        concepts=["scripting languages (C#, Lua, GDScript)", "visual scripting (Blueprints)", "hot reload", "gameplay ↔ engine boundary"],
        engines="Unity C# • Unreal Blueprints/C++ • Godot GDScript"),
    "Event Bus": dict(color="#ee6ec8",
        desc="A decoupled communication channel: systems publish events ('enemy died') without knowing who listens. Achievements, audio and UI each react independently.",
        concepts=["publish/subscribe pattern", "immediate vs. queued events", "observer pattern", "event payloads"],
        engines="Unreal Delegates • Godot Signals • nearly every gameplay framework"),
}
POS = {
    "ECS / Entities": (0.13, 0.10), "Animation": (0.32, 0.04), "Rendering": (0.50, 0.09),
    "Physics": (0.68, 0.04), "AI": (0.87, 0.10),
    "Input": (0.05, 0.50), "Audio": (0.95, 0.50),
    "Resources": (0.13, 0.90), "Scripting": (0.32, 0.96), "Event Bus": (0.87, 0.90),
}
LAB_FOR = {"Game Loop": "loop", "ECS / Entities": "ecs", "Animation": "anim",
           "Rendering": "render", "Physics": "physics", "AI": "ai",
           "Resources": "resources", "Input": "input", "Event Bus": "bus",
           "Audio": "diagrams", "Scripting": "shader"}

class ArchMap(QWidget):
    selected_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.selected = "Game Loop"
        self._rects, self._hub = {}, QRectF()
        self.setMouseTracking(True)
        self.setMinimumSize(430, 430)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        cx, cy = w * 0.5, h * 0.5
        hub_r = max(56.0, min(w, h) * 0.11)
        self._rects.clear()
        self._hub = QRectF(cx - hub_r, cy - hub_r, hub_r * 2, hub_r * 2)
        p.setFont(self.font())
        for name, (fx, fy) in POS.items():
            p.setPen(QPen(QColor(SUBSYSTEMS[name]["color"]), 1, Qt.DashLine))
            p.drawLine(QPointF(cx, cy), QPointF(w * fx, h * fy))
        grad = QLinearGradient(cx - hub_r, cy - hub_r, cx + hub_r, cy + hub_r)
        grad.setColorAt(0, QColor("#1b4a63")); grad.setColorAt(1, QColor("#2e86ad"))
        p.setBrush(grad)
        p.setPen(QPen(QColor(C_ACCENT), 3 if self.selected == "Game Loop" else 1))
        p.drawEllipse(QPointF(cx, cy), hub_r, hub_r)
        p.setPen(QColor("white"))
        f = self.font(); f.setBold(True); p.setFont(f)
        p.drawText(self._hub, Qt.AlignCenter, "ENGINE\nCORE")
        for name, (fx, fy) in POS.items():
            bw, bh = 136, 40
            rect = QRectF(w * fx - bw / 2, h * fy - bh / 2, bw, bh)
            sel = name == self.selected
            col = QColor(SUBSYSTEMS[name]["color"])
            p.setBrush(QColor("#243039" if sel else C_PANEL))
            p.setPen(QPen(col, 3 if sel else 1))
            p.drawRoundedRect(rect, 10, 10)
            p.setPen(QColor(C_TEXT)); f.setBold(False); p.setFont(f)
            p.drawText(rect, Qt.AlignCenter, name)
            self._rects[name] = rect
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(10, 16), "click any module for details")

    def _hit(self, pos):
        if self._hub.contains(pos): return "Game Loop"
        for name, r in self._rects.items():
            if r.contains(pos): return name
        return None

    def mousePressEvent(self, e):
        name = self._hit(e.position())
        if name:
            self.selected = name
            self.selected_changed.emit(name)
            self.update()

    def mouseMoveEvent(self, e):
        self.setCursor(Qt.PointingHandCursor if self._hit(e.position()) else Qt.ArrowCursor)

class OverviewPage(QWidget):
    open_requested = Signal(str)

    def __init__(self, bus):
        super().__init__()
        v = QVBoxLayout(self)
        v.addWidget(page_header("Engine Architecture",
            "A real engine is a collection of subsystems coordinated by the game loop. Click a module to inspect it — modules with a matching lab can be opened directly. 23 interactive pages, 18 animated diagrams, and achievements for experimenting."))
        h = QHBoxLayout()
        self.map = ArchMap()
        self.map.selected_changed.connect(self.show_detail)
        h.addWidget(self.map, 1)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame); scroll.setFixedWidth(350)
        inner = QWidget(); iv = QVBoxLayout(inner); iv.setContentsMargins(12, 4, 4, 12); iv.setSpacing(10)
        self.lbl_tag = QLabel("MODULE"); self.lbl_tag.setObjectName("dim")
        self.lbl_title = QLabel(""); self.lbl_title.setObjectName("h2")
        self.lbl_desc = QLabel(""); self.lbl_desc.setWordWrap(True)
        self.lbl_concepts = QLabel(""); self.lbl_concepts.setWordWrap(True)
        self.lbl_engines = QLabel(""); self.lbl_engines.setWordWrap(True); self.lbl_engines.setObjectName("dim")
        self.open_btn = QPushButton("▶  Open the lab for this module")
        self.open_btn.clicked.connect(lambda: self.open_requested.emit(LAB_FOR[self.lbl_title.text()]))
        tip = QLabel("▶ The app itself runs on one event bus: experiments anywhere unlock achievements (watch the toasts), and every event is visible in the Event Bus Monitor. CI-style: python engine_lab.py --selftest")
        tip.setObjectName("dim"); tip.setWordWrap(True)
        for w in (self.lbl_tag, self.lbl_title, self.lbl_desc, self.lbl_concepts,
                  self.lbl_engines, self.open_btn, tip):
            iv.addWidget(w)
        iv.addStretch(1)
        scroll.setWidget(inner)
        h.addWidget(scroll)
        v.addLayout(h)
        self.show_detail("Game Loop")

    def show_detail(self, name):
        info = SUBSYSTEMS[name]
        self.lbl_title.setText(name)
        self.lbl_title.setStyleSheet(f"color:{info['color']}; font-size:18px; font-weight:700;")
        self.lbl_desc.setText(info["desc"])
        self.lbl_concepts.setText("<b>Key concepts</b><br>" + "<br>".join("• " + c for c in info["concepts"]))
        self.lbl_engines.setText("<b>In real engines</b><br>" + info["engines"])
        self.open_btn.setVisible(name in LAB_FOR)


# =============================================================== GAME LOOP ==
@dataclass
class Ball:
    x: float; y: float; px: float; py: float
    vx: float; vy: float; r: int; color: str

class BallSim(QWidget):
    def __init__(self):
        super().__init__()
        self.balls, self.alpha, self.hud = [], 1.0, []
        self.setMinimumHeight(260)
        self.reset()

    def reset(self):
        w, h = max(self.width(), 320), max(self.height(), 240)
        self.balls = []
        for _ in range(14):
            r = random.randint(8, 16)
            ang, spd = random.uniform(0, 2 * math.pi), random.uniform(60, 180)
            b = Ball(random.uniform(r, w - r), random.uniform(r, h - r), 0, 0,
                     math.cos(ang) * spd, math.sin(ang) * spd, r, random.choice(PALETTE))
            b.px, b.py = b.x, b.y
            self.balls.append(b)

    def update_world(self, dt):
        w, h = max(self.width(), 50), max(self.height(), 50)
        for b in self.balls:
            b.px, b.py = b.x, b.y
            b.x += b.vx * dt; b.y += b.vy * dt
            if b.x < b.r:     b.x = b.r;     b.vx = abs(b.vx)
            if b.x > w - b.r: b.x = w - b.r; b.vx = -abs(b.vx)
            if b.y < b.r:     b.y = b.r;     b.vy = abs(b.vy)
            if b.y > h - b.r: b.y = h - b.r; b.vy = -abs(b.vy)

    def set_alpha(self, a): self.alpha = a

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        p.setPen(QPen(QColor("#191b1f"), 1))
        for gx in range(0, w, 40): p.drawLine(gx, 0, gx, h)
        for gy in range(0, h, 40): p.drawLine(0, gy, w, gy)
        p.setPen(Qt.NoPen)
        for b in self.balls:
            cx = lerp(b.px, b.x, self.alpha)
            cy = lerp(b.py, b.y, self.alpha)
            p.setBrush(QColor(b.color))
            p.drawEllipse(QPointF(cx, cy), b.r, b.r)
        p.setPen(QColor(C_DIM)); p.setFont(mono(9))
        for i, line in enumerate(self.hud):
            p.drawText(QPointF(10, 18 + 15 * i), line)

class PhaseStrip(QWidget):
    def __init__(self):
        super().__init__()
        self.frames = deque(maxlen=140)
        self.setFixedHeight(92)

    def add(self, updates): self.frames.append(updates)
    def clear(self): self.frames.clear()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(C_PANEL))
        w, h = self.width(), self.height()
        n_slots = 140
        bw = max(1.5, w / n_slots)
        frames = list(self.frames)[-n_slots:]
        start = n_slots - len(frames)
        seg = (h - 24) / 8
        for i, u in enumerate(frames):
            x = (start + i) * bw
            for k in range(min(u, 8)):
                yy = h - 10 - (k + 1) * seg
                p.fillRect(QRectF(x + 0.5, yy, bw - 1.5, max(1.0, seg - 1.0)), QColor(C_ACCENT))
            if u > 8:
                p.fillRect(QRectF(x + 0.5, h - 10 - 8 * seg - seg, bw - 1.5, max(1.0, seg - 1.0)), QColor(C_RED))
            p.fillRect(QRectF(x + 0.5, h - 10, bw - 1.5, 2.5), QColor(C_GREEN))
        p.setPen(QColor(C_BORDER)); p.drawLine(0, h - 6, w, h - 6)
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(8, 13),
                   "frame timeline · each blue block = one update() this frame · green cap = render() · red = >8 updates (spiral!)")

class GameLoopPage(QWidget):
    FIXED_DT = 1.0 / 60.0

    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.mode, self.target_fps, self.timescale = "variable", 60, 1.0
        self.load_ms = 0
        self.acc, self.alpha = 0.0, 1.0
        self.playing, self.fps_ema = True, 60.0
        self.last_real = time.perf_counter()
        self.last_updates, self.last_real_dt = 0, 0.0
        self.frames_total, self.updates_total = 0, 0

        v = QVBoxLayout(self)
        v.addWidget(page_header("Game Loop Lab",
            "Every frame: input → update → render. Drop the FPS to 15 and watch Variable mode stutter — then switch to Fixed: physics advances in smooth 1/60 s steps (multiple per frame) with render interpolation. Now try the 🔥 lag injector: give each update a fake cost above ~17 ms and the accumulator can never catch up — the spiral-of-death guard fires."))
        h = QHBoxLayout()
        left = QWidget(); left.setFixedWidth(300)
        lv = QVBoxLayout(left); lv.setContentsMargins(0, 0, 0, 0)

        gb1 = QGroupBox("Playback"); b1 = QHBoxLayout(gb1)
        self.play_btn = QPushButton("⏸ Pause"); self.play_btn.setCheckable(True); self.play_btn.setChecked(True)
        self.play_btn.toggled.connect(lambda on: self.play_btn.setText("⏸ Pause" if on else "▶ Play"))
        step = QPushButton("Step ⏭"); step.setToolTip("Run a single frame while paused")
        reset = QPushButton("Reset")
        step.clicked.connect(self._tick); reset.clicked.connect(self._reset)
        b1.addWidget(self.play_btn); b1.addWidget(step); b1.addWidget(reset)
        lv.addWidget(gb1)

        gb2 = QGroupBox("Timestep"); b2 = QVBoxLayout(gb2)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Variable — dt = real frame time", "Fixed — dt = 1/60 s + accumulator"])
        self.mode_combo.currentIndexChanged.connect(
            lambda i: (setattr(self, "mode", "variable" if i == 0 else "fixed"), setattr(self, "acc", 0.0)))
        b2.addWidget(self.mode_combo)
        lv.addWidget(gb2)

        gb3 = QGroupBox("Target frame rate"); b3 = QVBoxLayout(gb3)
        self.fps_lbl = QLabel("60 fps")
        self.fps_slider = QSlider(Qt.Horizontal); self.fps_slider.setRange(10, 120); self.fps_slider.setValue(60)
        self.fps_slider.valueChanged.connect(self._fps_changed)
        b3.addWidget(self.fps_slider); b3.addWidget(self.fps_lbl)
        lv.addWidget(gb3)

        gb4 = QGroupBox("Time scale (slow motion)"); b4 = QVBoxLayout(gb4)
        self.ts_lbl = QLabel("1.00×")
        self.ts_slider = QSlider(Qt.Horizontal); self.ts_slider.setRange(5, 200); self.ts_slider.setValue(100)
        self.ts_slider.valueChanged.connect(
            lambda val: (setattr(self, "timescale", val / 100), self.ts_lbl.setText(f"{val/100:.2f}×")))
        b4.addWidget(self.ts_slider); b4.addWidget(self.ts_lbl)
        lv.addWidget(gb4)

        gb5 = QGroupBox("🔥 Lag injector (artificial update cost)"); b5 = QVBoxLayout(gb5)
        self.load_lbl = QLabel("0 ms per update() call")
        self.load_slider = QSlider(Qt.Horizontal); self.load_slider.setRange(0, 30); self.load_slider.setValue(0)
        self.load_slider.valueChanged.connect(
            lambda val: (setattr(self, "load_ms", val), self.load_lbl.setText(f"{val} ms per update() call")))
        warn = QLabel("A fixed 60 Hz step budgets 16.7 ms per update. Sustained cost above that ⇒ the accumulator grows every frame ⇒ spiral of death (the guard clamps at 8 updates and drops the debt).")
        warn.setObjectName("dim"); warn.setWordWrap(True)
        b5.addWidget(self.load_slider); b5.addWidget(self.load_lbl); b5.addWidget(warn)
        lv.addWidget(gb5)

        gb6 = QGroupBox("Live stats"); g6 = QGridLayout(gb6)
        self.st = {k: QLabel("—") for k in ("fps", "ms", "upd", "alpha", "tot")}
        for w in self.st.values(): w.setFont(mono(10)); w.setStyleSheet(f"color:{C_ACCENT};")
        for row, (k, name) in enumerate((("fps", "actual fps"), ("ms", "frame time"),
                                         ("upd", "updates this frame"), ("alpha", "render alpha"),
                                         ("tot", "total frames / updates"))):
            g6.addWidget(QLabel(name), row, 0); g6.addWidget(self.st[k], row, 1)
        lv.addWidget(gb6)
        lv.addStretch(1)
        h.addWidget(left)

        right = QWidget(); rv = QVBoxLayout(right); rv.setContentsMargins(0, 0, 0, 0)
        self.canvas = BallSim()
        self.strip = PhaseStrip()
        rv.addWidget(self.canvas, 1)
        rv.addWidget(self.strip)
        legend = QLabel(f"<span style='color:{C_ACCENT};'>▮</span> update() &nbsp; <span style='color:{C_GREEN};'>▬</span> render() &nbsp; — newest frames at the right")
        legend.setObjectName("dim")
        rv.addWidget(legend)
        h.addWidget(right, 1)
        v.addLayout(h)

        self.timer = QTimer(self); self.timer.setInterval(16)
        self.timer.timeout.connect(lambda: self.playing and self._tick())

    def _fps_changed(self, val):
        self.target_fps = val
        self.fps_lbl.setText(f"{val} fps")
        self.timer.setInterval(max(4, round(1000 / val)))

    def _reset(self):
        self.canvas.reset(); self.acc = 0.0
        self.frames_total = self.updates_total = 0
        self.strip.clear(); self.canvas.update()

    def _tick(self):
        now = time.perf_counter()
        real_dt = min(now - self.last_real, 0.25)
        self.last_real = now
        scaled = real_dt * self.timescale
        updates = 0
        cost = self.load_ms / 1000.0
        if self.mode == "variable":
            if cost: time.sleep(cost)
            self.canvas.update_world(scaled)
            self.alpha, updates = 1.0, 1
        else:
            self.acc += scaled
            n = 0
            while self.acc >= self.FIXED_DT and n < 8:
                if cost: time.sleep(cost)
                self.canvas.update_world(self.FIXED_DT)
                self.acc -= self.FIXED_DT
                n += 1
            updates = n
            if n >= 8:
                self.acc = 0.0
                self.bus.emit("spiral_guard", load_ms=self.load_ms)
            self.alpha = self.acc / self.FIXED_DT
        self.canvas.set_alpha(self.alpha)
        self.canvas.update()
        self.strip.add(updates)
        if real_dt > 0:
            self.fps_ema = self.fps_ema * 0.9 + (1.0 / real_dt) * 0.1
        self.frames_total += 1; self.updates_total += updates
        self.last_updates, self.last_real_dt = updates, real_dt
        self.st["fps"].setText(f"{self.fps_ema:5.1f} fps")
        self.st["ms"].setText(f"{self.last_real_dt*1000:6.1f} ms")
        self.st["upd"].setText(f"{self.last_updates}  ({'fixed 1/60' if self.mode=='fixed' else 'variable'})")
        self.st["alpha"].setText(f"{self.alpha:.2f}")
        self.st["tot"].setText(f"{self.frames_total} / {self.updates_total}")
        self.canvas.hud = [f"mode: {self.mode}  ·  target {self.target_fps} fps",
                           f"time scale {self.timescale:.2f}×  ·  render alpha {self.alpha:.2f}",
                           f"fake update cost: {self.load_ms} ms"]

    def showEvent(self, e):
        self.last_real = time.perf_counter()
        if not self.timer.isActive(): self.timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop(); super().hideEvent(e)


# ============================================================ ECS PLAYGROUND =
@dataclass
class Transform: x: float; y: float; px: float = 0.0; py: float = 0.0
@dataclass
class Velocity:  vx: float; vy: float
@dataclass
class Sprite:    r: float = 10.0; color: str = C_ACCENT
@dataclass
class Collider:  pass
@dataclass
class Lifetime:  t: float = 5.0; total: float = 5.0

COMPONENT_TYPES = [Transform, Velocity, Sprite, Collider, Lifetime]
COMPONENT_TAGS  = ["T", "V", "S", "C", "L"]
COMPONENT_NAMES = ["Transform", "Velocity", "Sprite", "Collider", "Lifetime"]

class World:
    """Sparse-set ECS: one table (dict) of plain data per component type."""
    def __init__(self, bus):
        self.bus, self.next_id, self.order = bus, 1, []
        self.tables = {T: {} for T in COMPONENT_TYPES}
        self.w, self.h = 640.0, 420.0
        self.last_bounce = {}
        self.stats = {"spawned": 0, "destroyed": 0}

    def create(self, *comps):
        eid = self.next_id; self.next_id += 1
        self.order.append(eid)
        for c in comps: self.tables[type(c)][eid] = c
        self.stats["spawned"] += 1
        self.bus.emit("entity_spawned", entity=eid, components=[type(c).__name__ for c in comps])
        return eid

    def destroy(self, eid, user=False):
        for t in self.tables.values(): t.pop(eid, None)
        if eid in self.order: self.order.remove(eid)
        self.last_bounce.pop(eid, None)
        self.stats["destroyed"] += 1
        self.bus.emit("entity_destroyed", entity=eid, user=user)

    def has(self, eid, T): return eid in self.tables[T]
    def get(self, eid, T): return self.tables[T].get(eid)
    def add(self, eid, comp): self.tables[type(comp)][eid] = comp
    def remove(self, eid, T): self.tables[T].pop(eid, None)

class MovementSystem:
    def update(self, w, dt):
        for eid, v in w.tables[Velocity].items():
            t = w.tables[Transform].get(eid)
            if t is None: continue
            t.px, t.py = t.x, t.y
            t.x += v.vx * dt; t.y += v.vy * dt

class WallBounceSystem:
    def update(self, w, dt):
        now = time.monotonic()
        for eid in list(w.tables[Collider].keys()):
            t, v = w.tables[Transform].get(eid), w.tables[Velocity].get(eid)
            if t is None or v is None: continue
            s = w.tables[Sprite].get(eid); r = s.r if s else 10.0
            hit = False
            if t.x < r and v.vx < 0:         t.x = r;       v.vx = abs(v.vx); hit = True
            elif t.x > w.w - r and v.vx > 0: t.x = w.w - r; v.vx = -abs(v.vx); hit = True
            if t.y < r and v.vy < 0:         t.y = r;       v.vy = abs(v.vy); hit = True
            elif t.y > w.h - r and v.vy > 0: t.y = w.h - r; v.vy = -abs(v.vy); hit = True
            if hit and now - w.last_bounce.get(eid, 0.0) > 0.8:
                w.last_bounce[eid] = now
                w.bus.emit("collision_detected", entity=eid, surface="wall")

class LifetimeSystem:
    def update(self, w, dt):
        expired = []
        for eid, lf in w.tables[Lifetime].items():
            lf.t -= dt
            if lf.t <= 0: expired.append(eid)
        for eid in expired: w.destroy(eid)

class ECSCanvas(QWidget):
    def __init__(self, world):
        super().__init__()
        self.world, self.hud = world, ""
        self.setMinimumHeight(300)

    def resizeEvent(self, e):
        self.world.w = max(50.0, float(self.width()))
        self.world.h = max(50.0, float(self.height()))
        for t in self.world.tables[Transform].values():
            t.x = min(max(t.x, 16.0), self.world.w - 16.0)
            t.y = min(max(t.y, 16.0), self.world.h - 16.0)
        super().resizeEvent(e)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        p.setPen(QPen(QColor("#191b1f"), 1))
        for gx in range(0, w, 40): p.drawLine(gx, 0, gx, h)
        for gy in range(0, h, 40): p.drawLine(0, gy, w, gy)
        wt = self.world.tables
        for eid in self.world.order:
            t, s = wt[Transform].get(eid), wt[Sprite].get(eid)
            if t is None or s is None: continue
            fade = 1.0
            lf = wt[Lifetime].get(eid)
            if lf is not None and lf.total > 0:
                fade = max(0.12, lf.t / lf.total)
            v = wt[Velocity].get(eid)
            if v is not None:
                p.setPen(QPen(QColor(255, 255, 255, 45), 1))
                p.drawLine(QPointF(t.x, t.y), QPointF(t.x + v.vx * 0.25, t.y + v.vy * 0.25))
            col = QColor(s.color); col.setAlpha(int(255 * fade))
            p.setPen(Qt.NoPen); p.setBrush(col)
            p.drawEllipse(QPointF(t.x, t.y), s.r, s.r)
            if eid in wt[Collider]:
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor(C_ORANGE), 1, Qt.DashLine))
                p.drawEllipse(QPointF(t.x, t.y), s.r + 4, s.r + 4)
        p.setPen(QColor(C_DIM)); p.setFont(mono(9))
        st = self.world.stats
        p.drawText(QPointF(10, 18), f"entities: {len(self.world.order)}   (spawned {st['spawned']}, destroyed {st['destroyed']})")
        if self.hud: p.drawText(QPointF(10, 34), self.hud)

class ECSPage(QWidget):
    TICK_DT = 1.0 / 60.0

    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.world = World(bus)
        self.systems = [MovementSystem(), WallBounceSystem(), LifetimeSystem()]
        self.systems_on = {"MovementSystem": True, "WallBounceSystem": True, "LifetimeSystem": True}
        self.selected, self._syncing, self.tick_n = None, False, 0

        v = QVBoxLayout(self)
        v.addWidget(page_header("ECS Playground",
            "Entity = an ID. Component = plain data. System = behavior that queries component tables. Toggle components on the selected entity and watch the systems react — orange rings show Colliders, white lines show Velocity. Spawn a stress batch to see it scale."))
        h = QHBoxLayout()
        left = QWidget(); left.setFixedWidth(330)
        lv = QVBoxLayout(left); lv.setContentsMargins(0, 0, 0, 0)

        gb1 = QGroupBox("Spawn presets"); g1 = QGridLayout(gb1)
        defs = [("＋ Ball", self._add_ball), ("＋ Particle", self._add_particle),
                ("＋ Prop", self._add_prop), ("⚡ ×50", self._add_stress)]
        for i, (txt, fn) in enumerate(defs):
            b = QPushButton(txt); b.clicked.connect(fn); g1.addWidget(b, 0, i)
        kill = QPushButton("☠ Kill selected"); kill.clicked.connect(self._kill_selected)
        rst = QPushButton("Reset scene"); rst.clicked.connect(self._reset_scene)
        g1.addWidget(kill, 1, 0, 1, 2); g1.addWidget(rst, 1, 2)
        lv.addWidget(gb1)

        gb2 = QGroupBox("Systems (behavior)"); b2 = QVBoxLayout(gb2)
        for name in self.systems_on:
            cb = QCheckBox(name); cb.setChecked(True)
            cb.toggled.connect(lambda on, n=name: self.systems_on.__setitem__(n, on))
            b2.addWidget(cb)
        note = QLabel("A system only 'sees' entities owning the components it queries — try removing Velocity from a moving ball.")
        note.setObjectName("dim"); note.setWordWrap(True)
        b2.addWidget(note)
        lv.addWidget(gb2)

        gb3 = QGroupBox("Entities"); b3 = QVBoxLayout(gb3)
        self.entity_list = QListWidget()
        self.entity_list.currentItemChanged.connect(lambda *_: self._selection_changed())
        b3.addWidget(self.entity_list)
        leg = QLabel("T=Transform V=Velocity S=Sprite C=Collider L=Lifetime")
        leg.setObjectName("dim"); leg.setFont(mono(8))
        b3.addWidget(leg)
        lv.addWidget(gb3, 1)

        gb4 = QGroupBox("Inspector"); b4 = QVBoxLayout(gb4)
        self.ins_title = QLabel("Inspector — no entity selected"); self.ins_title.setObjectName("h2")
        b4.addWidget(self.ins_title)
        self.comp_checks = []
        for i, name in enumerate(COMPONENT_NAMES):
            cb = QCheckBox(name)
            cb.toggled.connect(lambda on, ix=i: self._comp_toggled(ix, on))
            b4.addWidget(cb); self.comp_checks.append(cb)
        note2 = QLabel("An entity with zero components still exists — it's just an ID.")
        note2.setObjectName("dim"); note2.setWordWrap(True)
        b4.addWidget(note2)
        lv.addWidget(gb4)
        h.addWidget(left)

        right = QWidget(); rv = QVBoxLayout(right); rv.setContentsMargins(0, 0, 0, 0)
        self.canvas = ECSCanvas(self.world)
        rv.addWidget(self.canvas, 1)
        h.addWidget(right, 1)
        v.addLayout(h)

        cap = QLabel("Component storage — data-oriented layout: each column is one dense component table, systems iterate columns (not objects).")
        cap.setObjectName("dim"); cap.setWordWrap(True)
        v.addWidget(cap)
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            ["Entity", "Transform.x", "Transform.y", "Velocity.vx", "Velocity.vy", "Sprite.r", "Collider", "Lifetime.t"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setMaximumHeight(170)
        v.addWidget(self.table)

        self.timer = QTimer(self); self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)
        self._reset_scene()

    def _rand_pos(self, r):
        return Transform(x=random.uniform(r, max(r + 1, self.world.w - r)),
                         y=random.uniform(r, max(r + 1, self.world.h - r)))

    def _add_ball(self):
        t = self._rand_pos(14); t.px, t.py = t.x, t.y
        ang, spd = random.uniform(0, 2 * math.pi), random.uniform(70, 150)
        self.world.create(t, Velocity(math.cos(ang) * spd, math.sin(ang) * spd),
                          Sprite(r=random.uniform(9, 14), color=random.choice(PALETTE)), Collider())

    def _add_particle(self):
        t = self._rand_pos(8); t.px, t.py = t.x, t.y
        ang, spd = random.uniform(0, 2 * math.pi), random.uniform(30, 90)
        life = random.uniform(3.5, 8)
        self.world.create(t, Velocity(math.cos(ang) * spd, math.sin(ang) * spd),
                          Sprite(r=random.uniform(4, 7), color=random.choice(PALETTE)),
                          Lifetime(t=life, total=life))

    def _add_prop(self):
        self.world.create(self._rand_pos(20), Sprite(r=16, color="#78909c"))

    def _add_stress(self):
        for _ in range(50): self._add_particle()

    def _reset_scene(self):
        for eid in list(self.world.order): self.world.destroy(eid)
        for _ in range(6): self._add_ball()
        for _ in range(5): self._add_particle()
        for _ in range(2): self._add_prop()
        self.refresh_entities(); self.refresh_table()

    def _kill_selected(self):
        if self.selected is not None:
            self.world.destroy(self.selected, user=True)
            self.selected = None
            self.refresh_entities(); self.refresh_table()

    def _selection_changed(self):
        it = self.entity_list.currentItem()
        self.selected = it.data(Qt.UserRole) if it else None
        self._sync_inspector()

    def _sync_inspector(self):
        self._syncing = True
        if self.selected is None:
            self.ins_title.setText("Inspector — no entity selected")
            for cb in self.comp_checks: cb.setEnabled(False); cb.setChecked(False)
        else:
            self.ins_title.setText(f"Inspector — entity #{self.selected}")
            for cb, T in zip(self.comp_checks, COMPONENT_TYPES):
                cb.setEnabled(True); cb.setChecked(self.world.has(self.selected, T))
        self._syncing = False

    def _comp_toggled(self, ix, on):
        if self._syncing or self.selected is None: return
        T = COMPONENT_TYPES[ix]
        if on:
            defaults = [self._rand_pos(12),
                        Velocity(random.uniform(-90, 90), random.uniform(-90, 90)),
                        Sprite(r=random.uniform(8, 13), color=random.choice(PALETTE)),
                        Collider(), Lifetime(t=5, total=5)]
            comp = defaults[ix]
            if isinstance(comp, Transform): comp.px, comp.py = comp.x, comp.y
            self.world.add(self.selected, comp)
        else:
            self.world.remove(self.selected, T)
        self.bus.emit("component_toggled", entity=self.selected, component=COMPONENT_NAMES[ix], state=on)
        self.refresh_entities(); self.refresh_table()

    def refresh_entities(self):
        self.entity_list.blockSignals(True)
        self.entity_list.clear()
        for eid in self.world.order:
            tags = "".join(tag for tag, T in zip(COMPONENT_TAGS, COMPONENT_TYPES)
                           if eid in self.world.tables[T]) or "—"
            item = QListWidgetItem(f"#{eid:<3}  {tags}")
            item.setData(Qt.UserRole, eid)
            self.entity_list.addItem(item)
        if self.selected in self.world.order:
            for i in range(self.entity_list.count()):
                if self.entity_list.item(i).data(Qt.UserRole) == self.selected:
                    self.entity_list.setCurrentRow(i); break
        self.entity_list.blockSignals(False)
        self._sync_inspector()

    def refresh_table(self):
        self.table.setRowCount(0)
        for row, eid in enumerate(self.world.order):
            t = self.world.get(eid, Transform); v = self.world.get(eid, Velocity)
            s = self.world.get(eid, Sprite);   lf = self.world.get(eid, Lifetime)
            vals = [f"#{eid}",
                    f"{t.x:.0f}" if t else "—", f"{t.y:.0f}" if t else "—",
                    f"{v.vx:.0f}" if v else "—", f"{v.vy:.0f}" if v else "—",
                    f"{s.r:.0f}" if s else "—",
                    "✔" if self.world.has(eid, Collider) else "—",
                    f"{lf.t:.1f}s" if lf else "—"]
            self.table.insertRow(row)
            for c, txt in enumerate(vals):
                item = QTableWidgetItem(txt)
                if c == 5 and s: item.setForeground(QColor(s.color))
                self.table.setItem(row, c, item)

    def _tick(self):
        dt = self.TICK_DT
        if self.systems_on["MovementSystem"]:   self.systems[0].update(self.world, dt)
        if self.systems_on["WallBounceSystem"]: self.systems[1].update(self.world, dt)
        if self.systems_on["LifetimeSystem"]:   self.systems[2].update(self.world, dt)
        self.canvas.hud = "systems on: " + ", ".join(n for n, on in self.systems_on.items() if on)
        self.canvas.update()
        self.tick_n += 1
        if self.tick_n % 12 == 0:
            self.refresh_entities(); self.refresh_table()

    def showEvent(self, e):
        if not self.timer.isActive(): self.timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop(); super().hideEvent(e)


# =============================================================== ANIMATION ==
WALK_KEYS = [
    (0.000,  28, -10, -20,  -30, -25,  20, 4,  0), (0.125,  15,  -5, -10,  -45, -12,   8, 3, -2),
    (0.250,   0,  -8,   5,  -70,   0,  -5, 4, -4), (0.375, -12, -25,  18,  -40,  10, -18, 5, -2),
    (0.500, -20, -30,  28,  -10,  25, -20, 4,  0), (0.625, -10, -45,  15,   -5,   8, -12, 3, -2),
    (0.750,   5, -70,   0,   -8,  -5,   0, 4, -4), (0.875,  18, -40, -12,  -25, -18,  10, 5, -2),
]
RUN_KEYS = [
    (0.000,  45, -15, -35,  -95, -45,  40, 14, 0), (0.125,  25, -30, -20, -120, -25,  20, 12, -3),
    (0.250,   5, -60,   0, -135,  -5,   0, 11, -7), (0.375, -15, -100, 25,  -80,  20, -25, 13, -3),
    (0.500, -35, -95,  45,  -15,  45, -40, 14, 0), (0.625, -20, -120, 25,  -30,  20, -25, 12, -3),
    (0.750,   0, -135,  5,  -60,   0,  -5, 11, -7), (0.875,  25, -80, -15, -100, -25,  20, 13, -3),
]
IDLE_KEYS = [(0.0, 2, -4, -2, -4, 3, -3, 1, 0), (0.5, 2, -4, -2, -4, 3, -3, 1, -1)]

def sample_clip(keys, ph, mode):
    ph %= 1.0
    n = len(keys)
    for i in range(n):
        t0 = keys[i][0]
        nxt = keys[(i + 1) % n]
        t1 = nxt[0] if nxt[0] > t0 else nxt[0] + 1.0
        if t0 <= ph < t1:
            u = (ph - t0) / (t1 - t0)
            if mode == "step":     u = 0.0
            elif mode == "smooth": u = u * u * (3.0 - 2.0 * u)
            return [a + (b - a) * u for a, b in zip(keys[i][1:], nxt[1:])]
    return list(keys[0][1:])

def _sstep01(x, a, b):
    t = max(0.0, min(1.0, (x - a) / max(1e-6, b - a)))
    return t * t * (3.0 - 2.0 * t)

class _AnimCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setMinimumHeight(330)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        pg = self.page
        groundY = h - 52
        p.setPen(QPen(QColor(C_BORDER), 2)); p.drawLine(20, groundY + 26, w - 210, groundY + 26)
        scroll = (pg.distance * 2.2) % 44
        p.setPen(QPen(QColor("#3a3d45"), 2))
        for gx in range(int(-scroll) - 44, w - 200, 44):
            p.drawLine(gx, groundY + 26, gx - 14, groundY + 26)
        s = 1.35
        pose = pg.pose
        cx = w * 0.30
        hipY = groundY - 78 * s + pose[7] * s * 0.6
        hip = QPointF(cx, hipY)
        def dirpt(origin, ang_deg, L):
            a = math.radians(ang_deg)
            return QPointF(origin.x() + math.sin(a) * L, origin.y() + math.cos(a) * L)
        thighL, thighS = 30 * s, 28 * s
        kneeL_ = dirpt(hip, pose[0], thighL);  footL_ = dirpt(kneeL_, pose[0] + pose[1], thighS)
        kneeR_ = dirpt(hip, pose[2], thighL);  footR_ = dirpt(kneeR_, pose[2] + pose[3], thighS)
        lean = pose[6]
        shoulder = QPointF(hip.x() + math.sin(math.radians(lean)) * 34 * s,
                           hip.y() - math.cos(math.radians(lean)) * 34 * s)
        handL_ = dirpt(shoulder, pose[4], 24 * s)
        handR_ = dirpt(shoulder, pose[5], 24 * s)
        headC = QPointF(shoulder.x() + math.sin(math.radians(lean)) * 13 * s,
                        shoulder.y() - math.cos(math.radians(lean)) * 13 * s)
        def limb(a, b, col, wd):
            p.setPen(QPen(QColor(col), wd, Qt.SolidLine, Qt.RoundCap)); p.setBrush(Qt.NoBrush)
            p.drawLine(a, b)
        far, near = "#5a7488", C_ACCENT
        limb(hip, kneeR_, far, 6); limb(kneeR_, footR_, far, 5)
        limb(shoulder, handR_, far, 5)
        limb(hip, shoulder, "#2e6e93", 8)
        p.setBrush(QColor("#dfe9f0")); p.setPen(Qt.NoPen)
        p.drawEllipse(headC, 9 * s, 9 * s)
        limb(hip, kneeL_, near, 6); limb(kneeL_, footL_, near, 5)
        limb(shoulder, handL_, near, 5)

        sx, sw = w - 186, 130
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(sx, 24), "animation state machine")
        nodes = [("IDLE", 40, "#4a5568"), ("WALK", 116, C_ACCENT), ("RUN", 192, C_ORANGE)]
        dom = pg.dominant
        for name, ny, col in nodes:
            r = QRectF(sx, ny, sw, 44)
            on = name == dom
            p.setBrush(QColor("#332a15") if on else QColor(C_PANEL))
            p.setPen(QPen(QColor(C_YELLOW) if on else QColor(col), 2 if on else 1))
            p.drawRoundedRect(r, 8, 8)
            p.setPen(QColor(C_TEXT) if on else QColor(C_DIM)); p.setFont(self.font())
            p.drawText(r, Qt.AlignCenter, name)
        p.setFont(mono(8))
        for y1, y2, lab, wt in ((40, 116, f"speed>0.2  [{pg.w_move:.2f}]", pg.w_move),
                                (116, 192, f"speed>4-6.5  [{pg.w_run:.2f}]", pg.w_run)):
            active = 0.05 < wt < 0.95
            p.setPen(QPen(QColor(C_YELLOW) if active else QColor("#4a5568"), 2 if active else 1))
            p.drawLine(QPointF(sx + 24, y1 + 44), QPointF(sx + 24, y2))
            p.drawLine(QPointF(sx + 24, y2 + 44), QPointF(sx + 24, y2 + 6))
            p.setPen(QColor(C_YELLOW) if active else QColor(C_DIM))
            p.drawText(QPointF(sx + 32, (y1 + y2) / 2 + 46), lab)
        p.setPen(QColor(C_DIM))
        p.drawText(QPointF(sx + 32, 288), "(hysteresis: stickier")
        p.drawText(QPointF(sx + 32, 300), "than the labels imply)")

        p.setFont(mono(10)); p.setPen(QColor(C_TEXT))
        p.drawText(QPointF(20, 26),
                   f"pose = IDLE·{pg.w_idle:.2f} + WALK·{pg.w_walk:.2f} + RUN·{pg.w_run:.2f}   @ phase {pg.phase % 1.0:.2f}")
        p.setFont(mono(9)); p.setPen(QColor(C_DIM))
        p.drawText(QPointF(20, 44),
                   f"speed {pg.speed:4.1f} m/s · interpolation: {pg.interp} · distance {pg.distance/40:.0f} m")
        p.drawText(QPointF(20, h - 10),
                   "the animator authored 8 keyframes — everything you see between them is interpolation + blending")

class _AnimTimeline(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setFixedHeight(84)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(C_PANEL))
        w, h = self.width(), self.height()
        pg = self.page
        x0, x1 = 64, w - 110
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(8, 14), "clip phase")
        p.setPen(QPen(QColor(C_BORDER), 1)); p.drawLine(x0, 18, x1, 18)
        for (t, *_r) in WALK_KEYS:
            kx = x0 + t * (x1 - x0)
            p.setPen(QPen(QColor(C_YELLOW), 2)); p.drawLine(QPointF(kx, 12), QPointF(kx, 24))
            p.drawText(QPointF(kx - 3, 10), "◆")
        phx = x0 + (pg.phase % 1.0) * (x1 - x0)
        p.setPen(QPen(QColor("white"), 2)); p.drawLine(QPointF(phx, 8), QPointF(phx, 28))
        for i, (name, wt, col) in enumerate((("IDLE", pg.w_idle, "#4a5568"),
                                             ("WALK", pg.w_walk, C_ACCENT),
                                             ("RUN", pg.w_run, C_ORANGE))):
            y = 40 + i * 14
            p.setPen(QColor(C_DIM)); p.drawText(QPointF(8, y + 8), name)
            p.setPen(QPen(QColor(C_BORDER), 1)); p.setBrush(QColor("#171a1e"))
            p.drawRect(QRectF(x0, y, x1 - x0, 10))
            p.setBrush(QColor(col)); p.setPen(Qt.NoPen)
            p.drawRect(QRectF(x0, y, (x1 - x0) * wt, 10))
            p.setPen(QColor(C_TEXT)); p.setFont(mono(8))
            p.drawText(QPointF(x1 + 8, y + 8), f"{wt*100:3.0f}%")

class AnimationPage(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.speed, self.phase, self.distance = 4.5, 0.0, 0.0
        self.interp, self.root_motion = "linear", True
        self.w_idle, self.w_walk, self.w_run = 1.0, 0.0, 0.0
        self.w_move = 0.0
        self.pose = list(IDLE_KEYS[0][1:])
        self.dominant, self._last_state, self._last_blend = "IDLE", "IDLE", -1e9
        self.playing = True

        v = QVBoxLayout(self)
        v.addWidget(page_header("Animation Lab — keyframes, interpolation & blend spaces",
            "Animators author sparse keyframes; the engine fills in every frame between them (interpolation), and mixes whole CLIPS by a parameter (blending). Drag the speed slider: below 0.2 m/s the idle loop dominates, the middle is a genuine walk↔run blend (a 1-D blend space — real engines use 2-D: speed × turn rate), and past ~6 m/s the run cycle takes over. Switch interpolation to 'step' to see what games looked like with no interpolation at all."))

        row = QHBoxLayout()
        row.addWidget(QLabel("speed"))
        self.speed_lbl = QLabel("4.5 m/s")
        self.speed_s = QSlider(Qt.Horizontal); self.speed_s.setRange(0, 100); self.speed_s.setValue(45)
        self.speed_s.setMaximumWidth(200)
        self.speed_s.valueChanged.connect(lambda val: (setattr(self, "speed", val / 10.0),
                                                       self.speed_lbl.setText(f"{val/10:.1f} m/s")))
        row.addWidget(self.speed_s); row.addWidget(self.speed_lbl); row.addSpacing(14)
        row.addWidget(QLabel("interpolation"))
        self.interp_combo = QComboBox()
        self.interp_combo.addItems(["linear", "smooth", "step"])
        self.interp_combo.currentTextChanged.connect(lambda t: setattr(self, "interp", t))
        row.addWidget(self.interp_combo); row.addSpacing(14)
        self.rm_cb = QCheckBox("root motion"); self.rm_cb.setChecked(True)
        self.rm_cb.toggled.connect(lambda on: setattr(self, "root_motion", on))
        row.addWidget(self.rm_cb)
        self.pause_b = QPushButton("⏸ pause"); self.pause_b.setCheckable(True); self.pause_b.setChecked(True)
        self.pause_b.toggled.connect(lambda on: (self.pause_b.setText("⏸ pause" if on else "▶ play"),
                                                 setattr(self, "playing", on)))
        row.addWidget(self.pause_b); row.addStretch(1)
        v.addLayout(row)

        self.canvas = _AnimCanvas(self)
        self.timeline = _AnimTimeline(self)
        v.addWidget(self.canvas, 1)
        v.addWidget(self.timeline)

        self.timer = QTimer(self); self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)
        self._tick()

    def _tick(self):
        dt = 0.016
        if self.playing:
            if self.speed > 0.2:
                self.phase += dt * (0.9 + self.speed * 0.30)
                self.distance += self.speed * 40 * dt
            w_move = _sstep01(self.speed, 0.2, 1.4)
            w_run = _sstep01(self.speed, 4.0, 6.5)
            self.w_move, w_run_raw = w_move, w_run
            self.w_idle = 1.0 - w_move
            self.w_walk = w_move * (1.0 - w_run)
            self.w_run = w_move * w_run
            idle = sample_clip(IDLE_KEYS, self.phase * 0.15, self.interp)
            walk = sample_clip(WALK_KEYS, self.phase, self.interp)
            run = sample_clip(RUN_KEYS, self.phase, self.interp)
            self.pose = [idle[i] * self.w_idle + walk[i] * self.w_walk + run[i] * self.w_run
                         for i in range(8)]
            dom = ("RUN" if self.w_run > 0.5 else "WALK" if self.w_walk > 0.5 else "IDLE")
            if dom != self._last_state:
                self._last_state = dom
                self.dominant = dom
                self.bus.emit("anim_state", state=dom, speed=round(self.speed, 1))
            now = time.monotonic()
            if (0.15 < w_move < 0.85 or 0.15 < w_run < 0.85) and now - self._last_blend > 2.5:
                self._last_blend = now
                self.bus.emit("anim_blended", walk=round(self.w_walk, 2), run=round(self.w_run, 2))
        self.canvas.update(); self.timeline.update()

    def showEvent(self, e):
        if not self.timer.isActive(): self.timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop(); super().hideEvent(e)


# =================================================================== IK TOY ==
def solve_ik2(sx, sy, tx, ty, L1, L2, elbow_up=True):
    """Analytic two-bone IK. Returns ((a1, a2, cx, cy), clamped)."""
    dx, dy = tx - sx, ty - sy
    d = math.hypot(dx, dy)
    lo, hi = abs(L1 - L2) + 1e-6, L1 + L2 - 1e-6
    clamped = d < lo - 0.5 or d > hi + 0.5
    dc = max(lo, min(hi, d)) if d > 1e-6 else lo
    ux, uy = (dx / d, dy / d) if d > 1e-6 else (1.0, 0.0)
    tx, ty = sx + ux * dc, sy + uy * dc
    d = dc
    ca = (d * d + L1 * L1 - L2 * L2) / (2 * d * L1)
    a = math.acos(max(-1.0, min(1.0, ca)))
    b = math.atan2(dy, dx)
    a1 = b + a if elbow_up else b - a
    ex, ey = sx + math.cos(a1) * L1, sy + math.sin(a1) * L1
    a2 = math.atan2(ty - ey, tx - ex) - a1
    return (a1, a2, tx, ty), clamped

def ccd_step(angles, lengths, tx, ty):
    """One CCD sweep (tip → root), absolute angles, base at origin."""
    n = len(angles)
    for i in range(n - 1, -1, -1):
        px = py = 0.0
        for k in range(i):
            px += math.cos(angles[k]) * lengths[k]
            py += math.sin(angles[k]) * lengths[k]
        ex, ey = px, py
        for k in range(i, n):
            ex += math.cos(angles[k]) * lengths[k]
            ey += math.sin(angles[k]) * lengths[k]
        if math.hypot(ex - px, ey - py) < 1e-9: continue
        angles[i] += math.atan2(ty - py, tx - px) - math.atan2(ey - py, ex - px)
    ex = ey = 0.0
    for k in range(n):
        ex += math.cos(angles[k]) * lengths[k]
        ey += math.sin(angles[k]) * lengths[k]
    return ex, ey

def _wrap_deg(a):
    return math.degrees(math.atan2(math.sin(a), math.cos(a)))

class _IKCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.target = QPointF(280, 170)
        self.dragging = False
        self._solved_t = -1e9
        self.setMinimumHeight(340)
        self.setMouseTracking(True)

    def _geom(self):
        return QPointF(70, self.height() * 0.52), 95.0, 95.0

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        S, L1, L2 = self._geom()
        p.setPen(QPen(_qc(C_BORDER, 110), 1, Qt.DashLine)); p.setBrush(Qt.NoBrush)
        p.drawEllipse(S, L1 + L2, L1 + L2)
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(S.x() + (L1 + L2) * 0.5, S.y() - (L1 + L2) * 0.72),
                   f"reach = {L1 + L2:.0f}")
        sol, clamped = solve_ik2(S.x(), S.y(), self.target.x(), self.target.y(), L1, L2,
                                 self.page.elbow_up)
        ghost, _ = solve_ik2(S.x(), S.y(), self.target.x(), self.target.y(), L1, L2,
                             not self.page.elbow_up)
        def arm(a1, a2, tx, ty, solid):
            ex, ey = S.x() + math.cos(a1) * L1, S.y() + math.sin(a1) * L1
            pen_style = Qt.SolidLine if solid else Qt.DashLine
            p.setPen(QPen(QColor(C_ACCENT) if solid else QColor("#4a5568"), 10, pen_style, Qt.RoundCap))
            p.drawLine(S, QPointF(ex, ey))
            p.setPen(QPen(QColor(C_GREEN) if solid else QColor("#3a3d45"), 8, pen_style, Qt.RoundCap))
            p.drawLine(QPointF(ex, ey), QPointF(tx, ty))
            if solid:
                for c in (S, QPointF(ex, ey)):
                    p.setBrush(QColor("#0c0d10")); p.setPen(QPen(QColor("white"), 2))
                    p.drawEllipse(c, 7, 7)
        if self.page.show_both:
            arm(ghost[0], ghost[1], ghost[2], ghost[3], False)
        arm(sol[0], sol[1], sol[2], sol[3], True)
        t = self.target
        p.setPen(QPen(QColor(C_RED if clamped else C_YELLOW), 2))
        p.drawLine(QPointF(t.x() - 14, t.y()), QPointF(t.x() + 14, t.y()))
        p.drawLine(QPointF(t.x(), t.y() - 14), QPointF(t.x(), t.y() + 14))
        p.drawEllipse(t, 10, 10)
        if clamped:
            p.setPen(QColor(C_RED)); p.setFont(mono(9))
            p.drawText(QPointF(t.x() + 16, t.y() - 12), "CLAMPED — full extension")
        p.setFont(mono(9)); p.setPen(QColor(C_TEXT))
        d = math.hypot(t.x() - S.x(), t.y() - S.y())
        p.drawText(QPointF(16, 22), f"two-bone analytic IK — d = {d:5.1f} of reach {L1+L2:.0f}")
        p.setPen(QColor(C_ACCENT))
        p.drawText(QPointF(16, 40),
                   f"shoulder θ₁ {_wrap_deg(sol[0]):6.1f}°   elbow θ₂ {_wrap_deg(sol[1]):6.1f}°   "
                   f"elbow: {'up' if self.page.elbow_up else 'down'}")
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(16, h - 22),
                   "drag the crosshair · law of cosines gives BOTH elbow solutions (ghost = the one you didn't pick)")
        p.drawText(QPointF(16, h - 8),
                   "beyond the dashed circle the solver clamps — engines add foot-step or root-motion fallbacks")

    def mousePressEvent(self, e):
        self.dragging = True; self._drag(e.position())

    def mouseMoveEvent(self, e):
        if self.dragging: self._drag(e.position())

    def mouseReleaseEvent(self, e): self.dragging = False

    def _drag(self, pos):
        self.target = QPointF(max(20, min(self.width() - 20, pos.x())),
                              max(20, min(self.height() - 20, pos.y())))
        S, L1, L2 = self._geom()
        d = math.hypot(self.target.x() - S.x(), self.target.y() - S.y())
        if d < L1 + L2 - 1 and time.monotonic() - self._solved_t > 2.5:
            self._solved_t = time.monotonic()
            self.page.bus.emit("ik_solved", d=int(d))
        self.update()

class _CCDCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.n, self.seg = 6, 30.0
        self.angles = [0.0] * self.n
        self.iters_total, self.err, self._conv_t = 0, 999.0, -1e9
        self.wander_t = time.monotonic()
        self.drag_target = None
        self.setMinimumHeight(300)
        self.setMouseTracking(True)
        self.timer = QTimer(self); self.timer.setInterval(30)
        self.timer.timeout.connect(self._tick)

    def _target(self):
        if self.drag_target is not None: return self.drag_target
        t = time.monotonic() - self.wander_t
        return QPointF(200 + math.cos(t * 0.7) * 140,
                       self.height() * 0.34 + math.sin(t * 1.1) * 85)

    def _tick(self):
        if not self.page.ccd_running: return
        tgt = self._target()
        bx, by = 30, self.height() * 0.58
        a = list(self.angles)
        for _ in range(self.page.ccd_iters):
            ex, ey = ccd_step(a, [self.seg] * self.n, tgt.x() - bx, tgt.y() - by)
            self.iters_total += 1
        self.angles = a
        self.err = math.hypot(ex - (tgt.x() - bx), ey - (tgt.y() - by))
        if self.err < 2.5 and time.monotonic() - self._conv_t > 3.0:
            self._conv_t = time.monotonic()
            self.page.bus.emit("ccd_converged", err=round(self.err, 2), iters=self.iters_total)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        base = QPointF(30, h * 0.58)
        p.setPen(QPen(_qc(C_BORDER, 90), 1, Qt.DashLine)); p.setBrush(Qt.NoBrush)
        p.drawEllipse(base, self.n * self.seg, self.n * self.seg)
        tgt = self._target()
        pts = [base]
        x = y = 0.0
        for k in range(self.n):
            x += math.cos(self.angles[k]) * self.seg
            y += math.sin(self.angles[k]) * self.seg
            pts.append(QPointF(base.x() + x, base.y() + y))
        for k in range(self.n):
            p.setPen(QPen(QColor(PALETTE[k % len(PALETTE)]), 9 - k, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(pts[k], pts[k + 1])
            p.setBrush(QColor("#0c0d10")); p.setPen(QPen(QColor("white"), 1))
            p.drawEllipse(pts[k + 1], 3.5, 3.5)
        p.setBrush(QColor(C_ORANGE)); p.setPen(Qt.NoPen)
        p.drawEllipse(base, 6, 6)
        p.setPen(QPen(QColor(C_YELLOW), 2))
        p.drawLine(QPointF(tgt.x() - 12, tgt.y()), QPointF(tgt.x() + 12, tgt.y()))
        p.drawLine(QPointF(tgt.x(), tgt.y() - 12), QPointF(tgt.x(), tgt.y() + 12))
        if self.err > 3:
            p.setPen(QPen(_qc(C_RED, 150), 1, Qt.DashLine))
            p.drawLine(pts[-1], tgt)
        p.setFont(mono(9)); p.setPen(QColor(C_TEXT))
        p.drawText(QPointF(14, 22), f"CCD — {self.n} joints, iterative")
        p.setPen(QColor(C_ACCENT))
        p.drawText(QPointF(14, 40),
                   f"sweeps/frame {self.page.ccd_iters} · total sweeps {self.iters_total} · error {self.err:5.1f} px")
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(14, h - 22),
                   "each sweep rotates every joint, tip → root, toward the target — no closed form exists for N bones")
        p.drawText(QPointF(14, h - 8),
                   "CCD ignores reach (watch it strain at the dashed circle) — production rigs clamp targets first")

    def mousePressEvent(self, e): self.drag_target = e.position()

    def mouseMoveEvent(self, e):
        if self.drag_target is not None: self.drag_target = e.position()

    def mouseReleaseEvent(self, e):
        self.drag_target = None; self.wander_t = time.monotonic()

    def start(self):
        if not self.timer.isActive(): self.timer.start()

    def stop(self): self.timer.stop()

class IKPage(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.elbow_up, self.show_both = True, True
        self.ccd_iters, self.ccd_running = 1, True
        self._flip_t = -1e9
        v = QVBoxLayout(self)
        v.addWidget(page_header("IK Toy — inverse kinematics: position → angles",
            "FK asks 'where does the hand end up given these joint angles?' — easy. IK asks the reverse: 'what angles put the hand HERE?' — the problem every grabbing, climbing, foot-placing character solves per frame. Two bones have a closed-form answer via the law of cosines — with TWO solutions (elbow up or down): IK is ambiguous until you hint it. N bones have no closed form at all, so engines iterate (CCD here; FABRIK/Jacobian in production)."))
        row = QHBoxLayout()
        flip = QPushButton("🤸 flip elbow solution"); flip.clicked.connect(self._flip)
        both = QCheckBox("show both solutions"); both.setChecked(True)
        both.toggled.connect(lambda on: (setattr(self, "show_both", on), self.ikc.update()))
        row.addWidget(flip); row.addWidget(both); row.addSpacing(16)
        row.addWidget(QLabel("CCD sweeps/frame"))
        self.ccd_lbl = QLabel("1")
        cs = QSlider(Qt.Horizontal); cs.setRange(1, 8); cs.setValue(1); cs.setMaximumWidth(100)
        cs.valueChanged.connect(lambda val: (setattr(self, "ccd_iters", val), self.ccd_lbl.setText(str(val))))
        row.addWidget(cs); row.addWidget(self.ccd_lbl)
        straight = QPushButton("↺ straighten chain")
        straight.clicked.connect(self._straighten)
        wnd = QCheckBox("wander target"); wnd.setChecked(True)
        wnd.toggled.connect(lambda on: setattr(self, "ccd_running", on))
        row.addWidget(straight); row.addWidget(wnd); row.addStretch(1)
        v.addLayout(row)
        h = QHBoxLayout()
        self.ikc = _IKCanvas(self)
        self.ccdc = _CCDCanvas(self); self.ccdc.setFixedWidth(390)
        h.addWidget(self.ikc, 1); h.addWidget(self.ccdc)
        v.addLayout(h)

    def _flip(self):
        self.elbow_up = not self.elbow_up
        if time.monotonic() - self._flip_t > 1.5:
            self._flip_t = time.monotonic()
            self.bus.emit("ik_flipped", elbow="up" if self.elbow_up else "down")
        self.ikc.update()

    def _straighten(self):
        self.ccdc.angles = [0.0] * self.ccdc.n
        self.ccdc.iters_total = 0
        self.ccdc.update()

    def showEvent(self, e): self.ccdc.start(); super().showEvent(e)
    def hideEvent(self, e): self.ccdc.stop(); super().hideEvent(e)


# ============================================================ RENDERING LAB =
WORLD_W, WORLD_H = 1000.0, 640.0

@dataclass
class RObj:
    x: float; y: float; r: float; z: float; color: str

class RenderCanvas(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.objs = []
        self.cam = QRectF(340, 200, 320, 240)
        self.dragging, self.drag_off = False, QPointF()
        self.show_depth, self.batching = False, True
        self.culled_cum = 0
        self.stats = (0, 0, 0, 0)
        self.setMinimumHeight(320)
        self.set_objects(160)

    def set_objects(self, n):
        self.objs = [RObj(random.uniform(20, WORLD_W - 20), random.uniform(20, WORLD_H - 20),
                          random.uniform(8, 26), random.random(), random.choice(PALETTE))
                     for _ in range(n)]
        self.update()

    def _visible(self, o):
        nx = max(self.cam.left(), min(o.x, self.cam.right()))
        ny = max(self.cam.top(),  min(o.y, self.cam.bottom()))
        return (o.x - nx) ** 2 + (o.y - ny) ** 2 <= o.r * o.r

    def advance(self, dx):
        self.cam.moveLeft(max(0.0, min(WORLD_W - self.cam.width(), self.cam.left() + dx)))

    def _to_world(self, pos):
        return QPointF(pos.x() * WORLD_W / max(1, self.width()),
                       pos.y() * WORLD_H / max(1, self.height()))

    def mousePressEvent(self, e):
        wpt = self._to_world(e.position())
        if self.cam.contains(wpt):
            self.dragging = True
            self.drag_off = wpt - self.cam.topLeft()

    def mouseMoveEvent(self, e):
        if self.dragging:
            tl = self._to_world(e.position()) - self.drag_off
            self.cam.moveTopLeft(QPointF(max(0.0, min(WORLD_W - self.cam.width(), tl.x())),
                                         max(0.0, min(WORLD_H - self.cam.height(), tl.y()))))
            self.update()

    def mouseReleaseEvent(self, e): self.dragging = False

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#0c0d10"))
        p.scale(self.width() / WORLD_W, self.height() / WORLD_H)
        vis = [o for o in self.objs if self._visible(o)]
        culd = len(self.objs) - len(vis)
        self.culled_cum += culd
        vis.sort(key=lambda o: o.z)
        p.setPen(QPen(QColor(200, 200, 210, 28), 1))
        p.setBrush(Qt.NoBrush)
        for o in self.objs:
            if not self._visible(o):
                p.drawEllipse(QPointF(o.x, o.y), o.r, o.r)
        if self.show_depth and len(vis) > 1:
            p.setPen(QPen(QColor(255, 255, 255, 60), 1))
            for a, b in zip(vis, vis[1:]):
                p.drawLine(QPointF(a.x, a.y), QPointF(b.x, b.y))
        p.setPen(Qt.NoPen)
        f = mono(7)
        for i, o in enumerate(vis):
            p.setBrush(QColor(o.color))
            p.drawEllipse(QPointF(o.x, o.y), o.r, o.r)
            if self.show_depth:
                p.setPen(QPen(QColor(255, 255, 255, 170), 1)); p.setFont(f)
                p.drawText(QPointF(o.x + o.r + 2, o.y - o.r), str(i))
                p.setPen(Qt.NoPen)
        p.setBrush(QColor(79, 195, 247, 16))
        p.setPen(QPen(QColor(C_ACCENT), 2))
        p.drawRect(self.cam)
        calls = len(vis)
        batched = len({o.color for o in vis})
        self.stats = (len(vis), culd, calls, batched)
        p.resetTransform()
        p.setPen(QColor(C_DIM)); p.setFont(mono(9))
        p.drawText(QPointF(10, 18), f"objects {len(self.objs)} · visible {len(vis)} · culled {culd} (cumulative {self.culled_cum})")
        p.drawText(QPointF(10, 34),
                   f"draw calls: {calls}" + (f"  →  {batched} after batching by material" if self.batching else "  (batching off)")
                   + f" · sorted back→front: {len(vis)}")
        p.drawText(QPointF(10, 50), "drag the blue camera rect · dim outlines are frustum-culled")

class RenderPage(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self._acc, self._last_emit = 0, 0
        v = QVBoxLayout(self)
        v.addWidget(page_header("Rendering Lab",
            "The GPU only draws what the camera can see. Drag the camera: objects outside the view are frustum-culled (dim outlines) and never become draw calls. Visible objects are depth-sorted back-to-front (painter's algorithm), and batching merges draws that share a material."))
        bar = QHBoxLayout()
        gb1 = QGroupBox("Scene"); b1 = QVBoxLayout(gb1)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("objects"))
        self.count_lbl = QLabel("160")
        s1 = QSlider(Qt.Horizontal); s1.setRange(30, 300); s1.setValue(160)
        s1.valueChanged.connect(lambda val: (self.canvas.set_objects(val), self.count_lbl.setText(str(val))))
        row1.addWidget(s1); row1.addWidget(self.count_lbl)
        b1.addLayout(row1)
        regen = QPushButton("↻ Regenerate")
        regen.clicked.connect(lambda: self.canvas.set_objects(len(self.canvas.objs)))
        b1.addWidget(regen)
        bar.addWidget(gb1)
        gb2 = QGroupBox("Camera"); b2 = QVBoxLayout(gb2)
        self.pan_cb = QCheckBox("auto-pan (ping-pong)"); self.pan_cb.setChecked(True)
        row2 = QHBoxLayout(); row2.addWidget(QLabel("speed"))
        self.speed_lbl = QLabel("120 px/s")
        s2 = QSlider(Qt.Horizontal); s2.setRange(0, 400); s2.setValue(120)
        s2.valueChanged.connect(lambda val: self.speed_lbl.setText(f"{val} px/s"))
        row2.addWidget(s2); row2.addWidget(self.speed_lbl)
        b2.addWidget(self.pan_cb); b2.addLayout(row2)
        self.speed = s2
        bar.addWidget(gb2)
        gb3 = QGroupBox("Pipeline view"); b3 = QVBoxLayout(gb3)
        self.batch_cb = QCheckBox("draw-call batching by material"); self.batch_cb.setChecked(True)
        self.batch_cb.toggled.connect(lambda on: setattr(self.canvas, "batching", on))
        self.depth_cb = QCheckBox("show depth sort order")
        self.depth_cb.toggled.connect(lambda on: setattr(self.canvas, "show_depth", on))
        b3.addWidget(self.batch_cb); b3.addWidget(self.depth_cb)
        bar.addWidget(gb3)
        bar.addStretch(1)
        v.addLayout(bar)
        self.canvas = RenderCanvas(bus)
        v.addWidget(self.canvas, 1)
        self.timer = QTimer(self); self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)

    def _tick(self):
        if self.pan_cb.isChecked():
            t = time.monotonic() * 0.5
            span = WORLD_W - self.canvas.cam.width()
            k = abs((t % 2.0) - 1.0)
            self.canvas.advance(k * span - self.canvas.cam.left())
        self.canvas.update()
        self._acc += 1
        if self._acc >= 60:
            self._acc = 0
            if self.canvas.culled_cum != self._last_emit:
                self._last_emit = self.canvas.culled_cum
                self.bus.emit("cull_stats", total=self.canvas.culled_cum)

    def showEvent(self, e):
        if not self.timer.isActive(): self.timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop(); super().hideEvent(e)


# =============================================================== SHADER LAB =
SH_HELPERS = """
def SH_fract(x): return x - math.floor(x)
def SH_clamp(x, lo, hi): return lo if x < lo else (hi if x > hi else x)
def SH_mix(a, b, k): return a + (b - a) * k
def SH_step(e, x): return 1.0 if x >= e else 0.0
def SH_sstep(e0, e1, x):
    k = SH_clamp((x - e0) / ((e1 - e0) or 1e-6), 0.0, 1.0)
    return k * k * (3.0 - 2.0 * k)
def SH_mod(a, b): return a - b * math.floor(a / b) if b else 0.0
def SH_len(a, b): return math.hypot(a, b)
def SH_pow(a, b):
    try: return math.pow(a, b)
    except (ValueError, OverflowError): return 0.0
"""
_SH_NS = {'math': math}
exec(SH_HELPERS, _SH_NS)

SH_FUNCS = {'sin': 'math.sin', 'cos': 'math.cos', 'tan': 'math.tan', 'abs': 'abs',
            'sqrt': 'math.sqrt', 'floor': 'math.floor', 'fract': 'SH_fract',
            'pow': 'SH_pow', 'min': 'min', 'max': 'max', 'clamp': 'SH_clamp',
            'mix': 'SH_mix', 'step': 'SH_step', 'smoothstep': 'SH_sstep',
            'mod': 'SH_mod', 'length': 'SH_len', 'exp': 'math.exp'}

SH_PRESETS = {
    "Plasma": """// classic plasma — layered sine fields
float a = sin((uv.x + sin(time * 0.7) * 0.3) * 9.0);
float b = sin((uv.y + sin(time * 0.9) * 0.3) * 8.0);
float d = length(uv.x - 0.5, uv.y - 0.5);
float c = sin(d * 18.0 - time * 2.0);
float v = a + b + c;
return vec3(v * 0.5 + 0.5, c * 0.5 + 0.5, sin(v * 2.0 + time));""",
    "Rings": """// sonar rings — distance + time
float d = length(uv.x - 0.5, uv.y - 0.5);
float rings = sin(d * 40.0 - time * 3.0) * 0.5 + 0.5;
float glow = clamp(1.0 - d * 1.6, 0.0, 1.0);
return vec3(rings * glow, d, glow * (0.4 + 0.6 * rings));""",
    "Checker floor": """// tiled floor with a pulsing light — very game-y
float cx = floor(uv.x * 8.0);
float cy = floor(uv.y * 6.0);
float checker = mod(cx + cy, 2.0);
float d = length(uv.x - 0.5, uv.y - 0.5);
float light = clamp(1.0 - d * 1.4, 0.0, 1.0) * (0.7 + 0.3 * sin(time * 2.0));
return vec3(checker * light, checker * light * 0.85, checker * light * 0.6 + 0.03);""",
    "Vignette": """// soft vignette tint — pure gradients
float d = length(uv.x - 0.5, uv.y - 0.5);
float v = smoothstep(0.85, 0.15, d);
float tint = mix(0.25, 0.9, uv.x);
return vec3(v * tint, v * 0.45, v * (1.0 - uv.x * 0.5));""",
    "💥 broken (syntax error)": """// 💥 this one fails to compile — watch the safe fallback
float d = length(uv.x - 0.5, uv.y - 0.5;
float rings = sin(d * 40.0) * 0.5 + 0.5;
return vec3(rings, d, 0.2);""",
}

def _sh_split(s):
    parts, depth, cur = [], 0, ""
    for ch in s:
        if ch == "," and depth == 0:
            parts.append(cur.strip()); cur = ""
        else:
            depth += (ch == "(") - (ch == ")")
            cur += ch
    parts.append(cur.strip())
    return parts

def compile_shader(src):
    """Mini-GLSL → Python. Returns (fn|None, error|None, generated_src, n_stmts)."""
    text = _re.sub(r'//[^\n]*', '', src)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    stmts, ret = [], None
    for i, ln in enumerate(lines):
        m = _re.match(r'^float\s+([A-Za-z_]\w*)\s*=\s*(.+?)\s*;\s*$', ln)
        if m: stmts.append((m.group(1), m.group(2))); continue
        m = _re.match(r'^return\s+vec3\s*\((.+)\)\s*;\s*$', ln)
        if m: ret = _sh_split(m.group(1)); continue
        return None, f"line {i+1}: expected 'float name = expr;' or 'return vec3(r,g,b);' — got \"{ln[:52]}\"", "", 0
    if ret is None or len(ret) != 3:
        return None, "missing/bad return — end with: return vec3(r, g, b);", "", 0
    if len(stmts) > 32:
        return None, "too many statements (max 32) — real shaders have instruction budgets too", "", 0

    declared = set()
    def translate(expr):
        e = _re.sub(r'uv\.x\b', 'x_', expr)
        e = _re.sub(r'uv\.y\b', 'y_', e)
        e = _re.sub(r'\btime\b', 't_', e)
        e = _re.sub(r'\bu_a\b', 'a_', e)
        e = _re.sub(r'\bu_b\b', 'b_', e)
        e = _re.sub(r'\b(' + '|'.join(SH_FUNCS) + r')\s*\(',
                    lambda m: SH_FUNCS[m.group(1)] + '(', e)
        for name in _re.findall(r'[A-Za-z_]\w*', e):
            if name in declared or name in ('x_', 'y_', 't_', 'a_', 'b_'): continue
            if name in ('abs', 'min', 'max'): continue
            return None, f"undeclared identifier '{name}' — declare it first: float {name} = …;"
        return e, None

    py = ["def _frag(x_, y_, t_, a_, b_):"]
    try:
        for name, expr in stmts:
            if name in ('x_', 'y_', 't_', 'a_', 'b_') or name in SH_FUNCS:
                return None, f"'{name}' is a reserved name", "", 0
            e, err = translate(expr)
            if err: return None, err, "", 0
            py.append(f"    {name} = {e}")
            declared.add(name)
        outs = []
        for e in ret:
            e2, err = translate(e)
            if err: return None, err, "", 0
            outs.append(e2)
        py.append("    return (" + ", ".join(outs) + ")")
        gen = "\n".join(py)
        ns = dict(_SH_NS); exec(compile(gen, '<shader>', 'exec'), ns)
        fn = ns['_frag']
        fn(0.5, 0.5, 0.0, 0.5, 0.5)          # pre-flight: catches div-by-zero etc.
        return fn, None, gen, len(stmts)
    except ZeroDivisionError:
        return None, "division by zero at uv=(0.5, 0.5) — guard your divisors", "", 0
    except Exception as ex:
        return None, f"compile error: {ex}", "", 0

class _ShaderView(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.t, self.render_ms, self.flash, self._img = 0.0, 0.0, 0.0, None
        self.setMinimumHeight(260)
        self.timer = QTimer(self); self.timer.setInterval(50)
        self.timer.timeout.connect(self._frame)

    def _frame(self):
        pg = self.page
        self.t += 0.05
        if pg.prog is None: self.update(); return
        w = pg.res; h = max(24, int(w * 0.66))
        fn, buf, i = pg.prog, bytearray(w * h * 4), 0
        t0 = time.perf_counter()
        try:
            for j in range(h):
                y_ = j / (h - 1)
                for ii in range(w):
                    r, g, b = fn(ii / (w - 1), y_, self.t, pg.u_a, pg.u_b)
                    buf[i]     = 255 if r > 1 else (0 if r < 0 else int(r * 255))
                    buf[i + 1] = 255 if g > 1 else (0 if g < 0 else int(g * 255))
                    buf[i + 2] = 255 if b > 1 else (0 if b < 0 else int(b * 255))
                    buf[i + 3] = 255; i += 4
        except Exception as ex:
            pg.on_runtime_error(ex); self.update(); return
        self.render_ms = (time.perf_counter() - t0) * 1000.0
        self._img = QImage(bytes(buf), w, h, w * 4, QImage.Format_RGBA8888)
        if self.flash > 0: self.flash -= 0.08
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor("#0c0d10"))
        w, h = self.width(), self.height()
        if self._img is None:
            p.setPen(QColor(C_DIM)); p.setFont(mono(10))
            p.drawText(self.rect(), Qt.AlignCenter, "no compiled program")
            return
        iw, ih = self._img.width(), self._img.height()
        s = min((w - 24) / iw, (h - 40) / ih)
        R = QRectF((w - iw * s) / 2, (h - ih * s) / 2, iw * s, ih * s)
        p.drawImage(R, self._img)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(_qc(C_GREEN, 200) if self.flash > 0 else QColor(C_BORDER),
                      2 if self.flash > 0 else 1))
        p.drawRoundedRect(R, 4, 4)
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(R.left(), R.bottom() + 16),
                   f"{iw}×{ih} = {iw*ih:,} fragments · {self.render_ms:.1f} ms/frame in software — "
                   f"a GPU does this 1000× bigger at 144 fps")
        p.drawText(QPointF(w - 250, R.top() - 6), "this quad IS your fragment shader running")

    def start(self):
        if not self.timer.isActive(): self.timer.start()

    def stop(self): self.timer.stop()

class ShaderLabPage(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.prog, self._last_good, self._gen = None, None, ""
        self._had_error, self._ok_count = False, 0
        self.u_a, self.u_b, self.res = 0.6, 0.3, 96
        v = QVBoxLayout(self)
        v.addWidget(page_header("Shader Lab — write GLSL-ish, hot-reload it live",
            "Shaders are tiny programs executed once per pixel. Edit the source on the left; it compiles and swaps WITHOUT restarting (hot reload — the workflow real engines guard carefully). Only: float statements, math built-ins, and a final return vec3(r,g,b) from uv.x, uv.y, time and two uniform sliders. Break it deliberately: syntax errors and undeclared identifiers keep the LAST GOOD program running, exactly like a driver keeping the old pipeline while your new one fails."))
        h = QHBoxLayout()
        left = QWidget(); left.setFixedWidth(430)
        lv = QVBoxLayout(left); lv.setContentsMargins(0, 0, 0, 0)
        row0 = QHBoxLayout()
        row0.addWidget(QLabel("preset"))
        self.preset = QComboBox(); self.preset.addItems(["— pick —"] + list(SH_PRESETS))
        self.preset.currentTextChanged.connect(self._preset)
        row0.addWidget(self.preset); row0.addStretch(1)
        lv.addLayout(row0)
        self.editor = QPlainTextEdit(); self.editor.setFont(mono(10))
        self.editor.setPlainText(SH_PRESETS["Plasma"])
        self.editor.textChanged.connect(self._edited)
        lv.addWidget(self.editor, 1)
        self.status = QLabel(); self.status.setWordWrap(True); self.status.setFont(mono(9))
        lv.addWidget(self.status)
        row1 = QHBoxLayout()
        self.compile_btn = QPushButton("⚙ compile"); self.compile_btn.clicked.connect(self.recompile)
        self.auto_cb = QCheckBox("auto-recompile"); self.auto_cb.setChecked(True)
        row1.addWidget(self.compile_btn); row1.addWidget(self.auto_cb); row1.addStretch(1)
        lv.addLayout(row1)
        h.addWidget(left)

        right = QWidget(); rv = QVBoxLayout(right); rv.setContentsMargins(0, 0, 0, 0)
        self.view = _ShaderView(self)
        rv.addWidget(self.view, 1)
        srow = QHBoxLayout()
        srow.addWidget(QLabel("resolution"))
        self.res_lbl = QLabel("96")
        rs = QSlider(Qt.Horizontal); rs.setRange(48, 160); rs.setValue(96); rs.setMaximumWidth(120)
        rs.valueChanged.connect(lambda val: (setattr(self, "res", val), self.res_lbl.setText(str(val))))
        srow.addWidget(rs); srow.addWidget(self.res_lbl)
        srow.addSpacing(14)
        self.ua_lbl, self.ub_lbl = QLabel("u_a 0.60"), QLabel("u_b 0.30")
        for lab, attr, init in (("u_a", "u_a", 60), ("u_b", "u_b", 30)):
            srow.addWidget(QLabel(lab))
            s = QSlider(Qt.Horizontal); s.setRange(0, 100); s.setValue(init); s.setMaximumWidth(100)
            s.valueChanged.connect(lambda val, a=attr: (setattr(self, a, val / 100.0),
                                                        getattr(self, a + "_lbl").setText(f"{a} {val/100:.2f}")))
            srow.addWidget(s)
            srow.addWidget(self.ua_lbl if attr == "u_a" else self.ub_lbl)
        srow.addStretch(1)
        rv.addLayout(srow)
        lv2 = QLabel("compiled program — Python as a stand-in for what the driver really generates (SIMD machine code on thousands of threads):")
        lv2.setObjectName("dim"); lv2.setWordWrap(True)
        rv.addWidget(lv2)
        self.gen_view = QPlainTextEdit(); self.gen_view.setReadOnly(True)
        self.gen_view.setFont(mono(8)); self.gen_view.setMaximumHeight(140)
        rv.addWidget(self.gen_view)
        h.addWidget(right, 1)
        v.addLayout(h)

        self.debounce = QTimer(self); self.debounce.setSingleShot(True); self.debounce.setInterval(500)
        self.debounce.timeout.connect(self.recompile)
        self.recompile()

    def _preset(self, name):
        if name in SH_PRESETS: self.editor.setPlainText(SH_PRESETS[name])

    def _edited(self):
        if self.auto_cb.isChecked():
            self.status.setText("✎ editing… (hot reload armed)")
            self.debounce.start()

    def recompile(self):
        t0 = time.perf_counter()
        fn, err, gen, n = compile_shader(self.editor.toPlainText())
        ms = (time.perf_counter() - t0) * 1000
        if fn:
            self._last_good = self.prog or fn
            self.prog, self._gen = fn, gen
            self.view.flash = 1.0
            self.status.setStyleSheet(f"color:{C_GREEN};")
            self.status.setText(f"✔ compiled {n} statements in {ms:.1f} ms — program swapped live, no restart")
            self.gen_view.setPlainText(gen + "\n\n# …runs once per pixel, per frame.")
            self._ok_count += 1
            self.bus.emit("shader_ok", stmts=n)
            if self._had_error:
                self._had_error = False
                self.bus.emit("shader_recovered")
        else:
            self._had_error = True
            self.status.setStyleSheet(f"color:{C_RED};")
            self.status.setText(f"✗ {err}   — keeping the LAST GOOD program (hot-reload safety)")
            self.bus.emit("shader_error", msg=err[:64])

    def on_runtime_error(self, ex):
        self.prog = self._last_good
        self._had_error = True
        self.status.setStyleSheet(f"color:{C_RED};")
        self.status.setText(f"✗ runtime error: {ex} — reverted to last good program")
        self.bus.emit("shader_error", msg=f"runtime: {ex}")

    def showEvent(self, e): self.view.start(); super().showEvent(e)
    def hideEvent(self, e): self.view.stop(); super().hideEvent(e)


# ============================================================ CAMERA & POST ==
POST_GRADES = {
    "warm sunset":  (1.18, 1.00, 0.82, 1.03),
    "cold night":   (0.72, 0.88, 1.22, 0.92),
    "horror green": (0.78, 1.12, 0.74, 0.95),
}

def _post_exposure(buf, ev):
    k = 2.0 ** ev
    lut = [min(255, int(i * k)) for i in range(256)]
    for i in range(0, len(buf), 4):
        buf[i] = lut[buf[i]]; buf[i + 1] = lut[buf[i + 1]]; buf[i + 2] = lut[buf[i + 2]]
    return buf

def _post_grade(buf, preset):
    if preset == "noir":
        for i in range(0, len(buf), 4):
            l = (buf[i] * 299 + buf[i + 1] * 587 + buf[i + 2] * 114) // 1000
            buf[i] = buf[i + 1] = buf[i + 2] = min(255, l)
        return buf
    g = POST_GRADES.get(preset)
    if not g: return buf
    rm, gm, bm, lift = g
    for i in range(0, len(buf), 4):
        buf[i] = min(255, int(buf[i] * rm + lift * 8))
        buf[i + 1] = min(255, int(buf[i + 1] * gm + lift * 4))
        buf[i + 2] = min(255, int(buf[i + 2] * bm))
    return buf

def _post_vignette(buf, w, h, amount):
    cx, cy = w / 2, h / 2
    md = math.hypot(cx, cy)
    for y in range(h):
        for x in range(w):
            k = 1.0 - amount * (math.hypot(x - cx, y - cy) / md) ** 2.2
            i = (y * w + x) * 4
            buf[i] = int(buf[i] * k); buf[i + 1] = int(buf[i + 1] * k); buf[i + 2] = int(buf[i + 2] * k)
    return buf

def _post_ca(buf, w, h, amount):
    s = amount * 7
    cx = max(1.0, w / 2)
    out = bytearray(buf)
    for y in range(h):
        row = y * w
        for x in range(w):
            dxn = (x - cx) / cx
            i = (row + x) * 4
            out[i] = buf[(row + min(w - 1, max(0, x + int(dxn * s)))) * 4]
            out[i + 2] = buf[(row + min(w - 1, max(0, x - int(dxn * s)))) * 4 + 2]
    return out

def _box3(buf, w, h):
    out = bytearray(len(buf))
    for y in range(h):
        for x in range(w):
            for c in range(3):
                s = n = 0
                for dy in (-1, 0, 1):
                    yy = y + dy
                    if not 0 <= yy < h: continue
                    for dx in (-1, 0, 1):
                        xx = x + dx
                        if not 0 <= xx < w: continue
                        s += buf[(yy * w + xx) * 3 + c]; n += 1
                out[(y * w + x) * 3 + c] = s // n
    return out

def _post_bloom(buf, w, h, strength):
    bw, bh = w // 2, h // 2
    acc = bytearray(bw * bh * 3)
    for y in range(bh):
        for x in range(bw):
            i = ((y * 2) * w + x * 2) * 4
            r, g, b = buf[i], buf[i + 1], buf[i + 2]
            l = 0.299 * r + 0.587 * g + 0.114 * b
            if l > 190:
                k = (l - 190) / 65
                j = (y * bw + x) * 3
                acc[j] = min(255, int(r * k)); acc[j + 1] = min(255, int(g * k)); acc[j + 2] = min(255, int(b * k))
    acc = _box3(_box3(acc, bw, bh), bw, bh)
    for y in range(h):
        for x in range(w):
            j = (min(bh - 1, y // 2) * bw + min(bw - 1, x // 2)) * 3
            i = (y * w + x) * 4
            buf[i] = min(255, buf[i] + int(acc[j] * strength))
            buf[i + 1] = min(255, buf[i + 1] + int(acc[j + 1] * strength))
            buf[i + 2] = min(255, buf[i + 2] + int(acc[j + 2] * strength))
    return buf

CAM_PILLARS = [(2.3 if k % 2 else -2.3, k * 7 + 6, PALETTE[k % len(PALETTE)]) for k in range(9)]
CAM_LIGHTS = [k * 7 + 9.5 for k in range(8)]

def _cam_projector(camx, camy, camz, yaw, W, H, fov, near):
    f = (H / 2) / math.tan(math.radians(fov) / 2)
    cyw, syw = math.cos(yaw), math.sin(yaw)
    def proj(x, y, z):
        dx, dz = x - camx, z - camz
        rx = dx * cyw - dz * syw
        rz = dx * syw + dz * cyw
        if rz <= near: return None
        return (W / 2 + f * rx / rz, H / 2 - f * (y - camy) / rz, rz)
    return proj

def _render_corridor(camx, camy, camz, yaw, W, H, fov, near):
    img = QImage(W, H, QImage.Format_RGBA8888)
    img.fill(QColor("#0a0c10"))
    p = QPainter(img); p.setRenderHint(QPainter.Antialiasing)
    proj = _cam_projector(camx, camy, camz, yaw, W, H, fov, near)
    cyw, syw = math.cos(yaw), math.sin(yaw)
    fgh = QColor("#0a0c10")
    def fogc(col, rz):
        k = min(0.85, rz / 46.0)
        return QColor(int(col.red() * (1 - k) + fgh.red() * k),
                      int(col.green() * (1 - k) + fgh.green() * k),
                      int(col.blue() * (1 - k) + fgh.blue() * k))
    p.setPen(QPen(QColor("#1b2733"), 1))
    z0, z1 = camz - 2, camz + 46
    for gx in (-5.0, -2.5, 0.0, 2.5, 5.0):
        a, b = proj(gx, 0, z0), proj(gx, 0, z1)
        if a and b: p.drawLine(QPointF(*a), QPointF(*b))
    zz = math.floor(z0 / 4) * 4
    while zz < z1:
        a, b = proj(-5, 0, zz), proj(5, 0, zz)
        if a and b: p.drawLine(QPointF(*a), QPointF(*b))
        zz += 4
    culled = 0
    order = sorted(CAM_PILLARS, key=lambda pl: -((pl[0] - camx) ** 2 + (pl[1] - camz) ** 2))
    for (px, pz, col) in order:
        s2 = 0.45
        dx, dz = px - camx, pz - camz
        rz = dx * syw + dz * cyw
        if rz + s2 <= near:
            culled += 1; continue
        dist = max(0.1, rz)
        zf = pz + (s2 if camz <= pz else -s2)
        xs = px + (s2 if camx <= px else -s2)
        for quad in (
                [(px - s2, 0, zf), (px + s2, 0, zf), (px + s2, 3, zf), (px - s2, 3, zf)],
                [(xs, 0, pz - s2), (xs, 0, pz + s2), (xs, 3, pz + s2), (xs, 3, pz - s2)]):
            pj = [proj(*c) for c in quad]
            if any(q is None for q in pj): continue
            p.setOpacity(max(0.05, min(1.0, (rz - near) / 2.0)))
            p.setBrush(fogc(QColor(col), dist)); p.setPen(Qt.NoPen)
            p.drawPolygon(QPolygonF([QPointF(*q) for q in pj]))
        p.setOpacity(1.0)
    for lz in CAM_LIGHTS:
        pj = [proj(-0.28, 2.92, lz - 0.28), proj(0.28, 2.92, lz - 0.28),
              proj(0.28, 2.92, lz + 0.28), proj(-0.28, 2.92, lz + 0.28)]
        if all(pj):
            p.setBrush(QColor(255, 250, 235)); p.setPen(Qt.NoPen)
            p.drawPolygon(QPolygonF([QPointF(*q) for q in pj]))
    p.end()
    return img, culled

class _CamCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.t = 0.0
        self.final = None
        self.stages = []
        self.culled = 0
        self.setMinimumHeight(360)
        self.timer = QTimer(self); self.timer.setInterval(60)
        self.timer.timeout.connect(self._frame)

    def _frame(self):
        pg = self.page
        self.t += 0.06
        camz = 6 + (self.t * pg.fly_speed) % 52
        camx = 0.35 * math.sin(self.t * 0.4)
        yaw = 0.07 * math.sin(self.t * 0.55)
        W, H = max(200, self.width() - 20), max(140, self.height() - 118)
        base, self.culled = _render_corridor(camx, 1.5, camz, yaw, W, H, pg.fov_s.value(), 0.25)
        rw, rh = pg.res_combo.currentText().split("×")
        small = base.scaled(int(rw), int(rh), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        self.final, self.stages = self._post(small)
        self.update()

    def _post(self, img):
        pg = self.page
        w, h = img.width(), img.height()
        buf = bytearray(img.constBits().tobytes())
        stages = [("render", self._img(buf, w, h))]
        if abs(pg.ev) > 0.01:
            buf = _post_exposure(buf, pg.ev)
            stages.append((f"exposure {pg.ev:+.2f}", self._img(buf, w, h)))
        if pg.bloom_on:
            buf = _post_bloom(buf, w, h, pg.bloom_k)
            stages.append((f"bloom {pg.bloom_k:.0%}", self._img(buf, w, h)))
        if pg.grade != "neutral":
            buf = _post_grade(buf, pg.grade)
            stages.append((pg.grade, self._img(buf, w, h)))
        if pg.vig > 0.01:
            buf = _post_vignette(buf, w, h, pg.vig)
            stages.append((f"vignette {pg.vig:.0%}", self._img(buf, w, h)))
        if pg.ca > 0.01:
            buf = _post_ca(buf, w, h, pg.ca)
            stages.append((f"chrom.ab {pg.ca:.0%}", self._img(buf, w, h)))
        return self._img(buf, w, h), stages

    @staticmethod
    def _img(buf, w, h):
        return QImage(bytes(buf), w, h, w * 4, QImage.Format_RGBA8888)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        pg = self.page
        if self.final is None: return
        W, H = w - 20, h - 118
        k = min(W / self.final.width(), H / self.final.height())
        R = QRectF(10 + (W - self.final.width() * k) / 2, 10,
                   self.final.width() * k, self.final.height() * k)
        p.drawImage(R, self.final)
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(12, h - 96),
                   f"screen — post target {self.final.width()}×{self.final.height()} scaled up · stage outputs below")
        x = 12
        for (name, img) in self.stages[-8:]:
            r = QRectF(x, h - 86, 104, 58)
            p.setBrush(QColor("#0c0d10")); p.setPen(QPen(QColor(C_BORDER), 1))
            p.drawRoundedRect(r, 4, 4)
            p.drawImage(r.adjusted(1, 1, -1, -1), img)
            p.setPen(QColor(C_ACCENT)); p.setFont(mono(7))
            p.drawText(QRectF(x, h - 26, 104, 12), Qt.AlignCenter, name[:18])
            x += 112
        if pg.frustum_cb.isChecked():
            MR = QRectF(w - 216, 12, 204, 128)
            p.setBrush(QColor(10, 12, 16, 225)); p.setPen(QPen(QColor(C_BORDER), 1))
            p.drawRoundedRect(MR, 6, 6)
            camz = 6 + (self.t * pg.fly_speed) % 52
            camx = 0.35 * math.sin(self.t * 0.4)
            yaw = 0.07 * math.sin(self.t * 0.55)
            def M(x2, z2):
                return QPointF(MR.left() + (x2 + 7) / 14 * MR.width(),
                               MR.top() + (1 - (z2 - (camz - 4)) / 48) * MR.height())
            fovr = math.radians(pg.fov_s.value())
            for sgn in (-1, 1):
                a = yaw + sgn * fovr / 2
                p.setPen(QPen(_qc(C_ACCENT, 140), 1))
                p.drawLine(M(camx, camz), M(camx + math.sin(a) * 46, camz + math.cos(a) * 46))
            p.setPen(QPen(QColor(C_GREEN), 1, Qt.DashLine))
            p.drawLine(M(-7, camz + 44), M(7, camz + 44))
            p.setPen(QPen(QColor(C_RED), 1.5))
            p.drawLine(M(-1.4, camz + 0.25), M(1.4, camz + 0.25))
            p.setPen(QColor(C_RED)); p.setFont(mono(7))
            p.drawText(QPointF(M(1.6, camz + 0.3).x(), M(1.6, camz + 0.3).y() + 8), "near")
            p.setPen(QColor(C_DIM))
            p.drawText(QPointF(M(4.4, camz + 44).x() - 14, M(4.4, camz + 44).y() - 3), "far")
            for (px, pz, col) in CAM_PILLARS:
                inside = abs(px - camx) < math.tan(fovr / 2) * max(0.5, pz - camz)
                p.setBrush(QColor(C_GREEN if inside else "#5c3a3a")); p.setPen(Qt.NoPen)
                mp = M(px, pz)
                p.drawRect(QRectF(mp.x() - 3, mp.y() - 3, 6, 6))
            mp = M(camx, camz)
            p.setBrush(QColor("white")); p.setPen(Qt.NoPen)
            p.drawEllipse(mp, 3.5, 3.5)
            p.setPen(QColor(C_DIM)); p.setFont(mono(7))
            p.drawText(QPointF(MR.left() + 6, MR.bottom() - 5),
                       f"top-down · fov {pg.fov_s.value()}° · culled {self.culled}")

    def start(self):
        if not self.timer.isActive(): self.timer.start()

    def stop(self): self.timer.stop()

class CameraLabPage(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.ev, self.bloom_on, self.bloom_k = 0.0, True, 0.6
        self.grade, self.vig, self.ca = "neutral", 0.25, 0.0
        self.fly_speed = 1.2
        self._wide_t = self._stack_t = -1e9
        v = QVBoxLayout(self)
        v.addWidget(page_header("Camera & Post — the last mile of every frame",
            "The camera is just math: a position, a yaw, a field of view. FOV trades world-visible for distortion (watch the top-down frustum and the corridor bend), the near plane clips geometry that gets too close, and everything outside the frustum was culled before shading. Then the RAW render is never shipped: a stack of full-screen passes — exposure (EV stops), bloom, color grade, vignette, chromatic aberration — runs over the finished frame, each reading the previous output. Order matters; compare the strip."))
        row = QHBoxLayout()
        row.addWidget(QLabel("FOV"))
        self.fov_lbl = QLabel("75°")
        self.fov_s = QSlider(Qt.Horizontal); self.fov_s.setRange(30, 130); self.fov_s.setValue(75)
        self.fov_s.setMaximumWidth(130)
        self.fov_s.valueChanged.connect(self._fov)
        row.addWidget(self.fov_s); row.addWidget(self.fov_lbl); row.addSpacing(10)
        row.addWidget(QLabel("fly speed"))
        sp = QSlider(Qt.Horizontal); sp.setRange(2, 40); sp.setValue(12); sp.setMaximumWidth(90)
        sp.valueChanged.connect(lambda val: setattr(self, "fly_speed", val / 10))
        row.addWidget(sp); row.addSpacing(10)
        row.addWidget(QLabel("target res"))
        self.res_combo = QComboBox()
        self.res_combo.addItems(["140×91", "170×110", "200×130", "240×156"])
        self.res_combo.setCurrentIndex(1)
        row.addWidget(self.res_combo)
        self.frustum_cb = QCheckBox("frustum map"); self.frustum_cb.setChecked(True)
        row.addSpacing(6); row.addWidget(self.frustum_cb); row.addStretch(1)
        v.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("exposure"))
        self.ev_lbl = QLabel("+0.00 EV")
        es = QSlider(Qt.Horizontal); es.setRange(-8, 8); es.setValue(0); es.setMaximumWidth(110)
        es.valueChanged.connect(lambda val: (setattr(self, "ev", val / 4),
                                             self.ev_lbl.setText(f"{val/4:+.2f} EV"), self._stack_check()))
        row2.addWidget(es); row2.addWidget(self.ev_lbl); row2.addSpacing(8)
        self.bloom_cb = QCheckBox("bloom"); self.bloom_cb.setChecked(True)
        self.bloom_cb.toggled.connect(lambda on: (setattr(self, "bloom_on", on), self._stack_check()))
        row2.addWidget(self.bloom_cb)
        bs = QSlider(Qt.Horizontal); bs.setRange(0, 100); bs.setValue(60); bs.setMaximumWidth(90)
        bs.valueChanged.connect(lambda val: (setattr(self, "bloom_k", val / 100), self._stack_check()))
        row2.addWidget(bs); row2.addSpacing(8)
        row2.addWidget(QLabel("grade"))
        gc = QComboBox()
        gc.addItems(["neutral", "warm sunset", "cold night", "horror green", "noir"])
        gc.currentTextChanged.connect(lambda t: (setattr(self, "grade", t), self._stack_check()))
        row2.addWidget(gc); row2.addSpacing(8)
        row2.addWidget(QLabel("vignette"))
        vs = QSlider(Qt.Horizontal); vs.setRange(0, 100); vs.setValue(25); vs.setMaximumWidth(90)
        vs.valueChanged.connect(lambda val: setattr(self, "vig", val / 100))
        row2.addWidget(vs); row2.addSpacing(8)
        row2.addWidget(QLabel("chrom. aberr."))
        cas = QSlider(Qt.Horizontal); cas.setRange(0, 100); cas.setValue(0); cas.setMaximumWidth(90)
        cas.valueChanged.connect(lambda val: setattr(self, "ca", val / 100))
        row2.addWidget(cas); row2.addStretch(1)
        v.addLayout(row2)

        self.canvas = _CamCanvas(self)
        v.addWidget(self.canvas, 1)

    def _fov(self, val):
        self.fov_lbl.setText(f"{val}°")
        if val > 100 and time.monotonic() - self._wide_t > 3:
            self._wide_t = time.monotonic()
            self.bus.emit("camera_wide", fov=val)

    def _stack_check(self):
        if (self.bloom_on and self.bloom_k >= 0.6 and self.ev >= 0.75
                and self.grade == "warm sunset" and time.monotonic() - self._stack_t > 3):
            self._stack_t = time.monotonic()
            self.bus.emit("post_stacked", ev=self.ev, bloom=round(self.bloom_k, 2))

    def showEvent(self, e): self.canvas.start(); super().showEvent(e)
    def hideEvent(self, e): self.canvas.stop(); super().hideEvent(e)


# ========================================================= BROAD-PHASE LAB ==
@dataclass
class BEnt:
    x: float; y: float; vx: float; vy: float; r: float; color: str

class BPCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.hud_lines = []
        self.actual_pairs = []
        self.setMinimumHeight(320)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        pg = self.page
        if pg.grid_on:
            cs = pg.cell
            p.setPen(QPen(QColor("#1c1f24"), 1))
            for gx in range(0, w, cs): p.drawLine(gx, 0, gx, h)
            for gy in range(0, h, cs): p.drawLine(0, gy, w, gy)
            p.setPen(Qt.NoPen); p.setBrush(QColor(79, 195, 247, 14))
            for (cxi, cyi) in pg.occupied_cells:
                p.drawRect(cxi * cs, cyi * cs, cs, cs)
        if pg.cand_cb.isChecked():
            p.setPen(QPen(_qc(C_YELLOW, 60), 1))
            for (i, j) in getattr(pg, "cand_draw", [])[:300]:
                a, b = pg.ents[i], pg.ents[j]
                p.drawLine(QPointF(a.x, a.y), QPointF(b.x, b.y))
        for (i, j) in self.actual_pairs:
            a, b = pg.ents[i], pg.ents[j]
            p.setPen(QPen(QColor(C_RED, 200), 2))
            p.drawLine(QPointF(a.x, a.y), QPointF(b.x, b.y))
        p.setPen(Qt.NoPen)
        for en in pg.ents:
            p.setBrush(QColor(en.color))
            p.drawEllipse(QPointF(en.x, en.y), en.r, en.r)
        p.setPen(QColor(C_DIM)); p.setFont(mono(9))
        for i, line in enumerate(self.hud_lines):
            p.drawText(QPointF(10, 18 + 15 * i), line)

class BroadPhasePage(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.ents = []
        self.grid_on, self.cell = True, 70
        self.occupied_cells = set()
        self.saved_cum = 0
        self._acc, self._last_emit = 0, 0
        self._pending_n = None
        self.last_brute = self.last_cand = self.last_actual = 0
        self.cand_draw = []

        v = QVBoxLayout(self)
        v.addWidget(page_header("Broad-Phase Lab",
            "Checking every object against every other is O(n²) — with 80 objects that's 3160 pair tests per tick. A spatial hash grid only pairs objects that share a cell, pruning almost all of it before the precise narrow-phase test. Watch the counters; red lines are real collisions (objects bounce)."))
        bar = QHBoxLayout()
        gb1 = QGroupBox("World"); b1 = QVBoxLayout(gb1)
        r1 = QHBoxLayout(); r1.addWidget(QLabel("entities"))
        self.n_lbl = QLabel("60")
        s1 = QSlider(Qt.Horizontal); s1.setRange(10, 120); s1.setValue(60)
        s1.valueChanged.connect(lambda val: (setattr(self, "_pending_n", val), self.n_lbl.setText(str(val))))
        r1.addWidget(s1); r1.addWidget(self.n_lbl); b1.addLayout(r1)
        self.grid_cb = QCheckBox("use spatial hash grid (broad phase)"); self.grid_cb.setChecked(True)
        self.grid_cb.toggled.connect(lambda on: setattr(self, "grid_on", on))
        self.cand_cb = QCheckBox("draw candidate pairs (yellow)")
        b1.addWidget(self.grid_cb); b1.addWidget(self.cand_cb)
        bar.addWidget(gb1)

        gb2 = QGroupBox("Grid"); b2 = QVBoxLayout(gb2)
        r2 = QHBoxLayout(); r2.addWidget(QLabel("cell size"))
        self.cs_lbl = QLabel("70 px")
        s2 = QSlider(Qt.Horizontal); s2.setRange(30, 150); s2.setValue(70)
        s2.valueChanged.connect(lambda val: (setattr(self, "cell", val), self.cs_lbl.setText(f"{val} px")))
        r2.addWidget(s2); r2.addWidget(self.cs_lbl); b2.addLayout(r2)
        note = QLabel("Caveat: entities are hashed by center point, so the cell must exceed the largest radius — too small and edge-straddling pairs get missed (classic tuning bug).")
        note.setObjectName("dim"); note.setWordWrap(True)
        b2.addWidget(note)
        bar.addWidget(gb2)
        bar.addStretch(1)
        v.addLayout(bar)

        self.canvas = BPCanvas(self)
        v.addWidget(self.canvas, 1)
        self.timer = QTimer(self); self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)
        self._regen(60)

    def _regen(self, n):
        W, H = max(self.canvas.width(), 320), max(self.canvas.height(), 240)
        self.ents = []
        for _ in range(n):
            r = random.uniform(6, 14)
            ang, spd = random.uniform(0, 2 * math.pi), random.uniform(40, 130)
            self.ents.append(BEnt(random.uniform(r, W - r), random.uniform(r, H - r),
                                  math.cos(ang) * spd, math.sin(ang) * spd, r, random.choice(PALETTE)))

    def _tick(self):
        n = self._pending_n
        if n is not None and n != len(self.ents):
            self._regen(n); self._pending_n = None
        W, H = max(self.canvas.width(), 50), max(self.canvas.height(), 50)
        dt = 1 / 60.0
        for en in self.ents:
            en.x += en.vx * dt; en.y += en.vy * dt
            if en.x < en.r:     en.x = en.r;     en.vx = abs(en.vx)
            if en.x > W - en.r: en.x = W - en.r; en.vx = -abs(en.vx)
            if en.y < en.r:     en.y = en.r;     en.vy = abs(en.vy)
            if en.y > H - en.r: en.y = H - en.r; en.vy = -abs(en.vy)

        n = len(self.ents)
        brute = n * (n - 1) // 2
        self.occupied_cells = set()
        if self.grid_on:
            cells = defaultdict(list)
            for i, en in enumerate(self.ents):
                c = (int(en.x // self.cell), int(en.y // self.cell))
                cells[c].append(i); self.occupied_cells.add(c)
            cand = set()
            for ids in cells.values():
                for a in range(len(ids)):
                    for b in range(a + 1, len(ids)):
                        x, y = ids[a], ids[b]
                        cand.add((x, y) if x < y else (y, x))
        else:
            cand = {(i, j) for i in range(n) for j in range(i + 1, n)}

        actual = []
        for (i, j) in cand:
            a, b = self.ents[i], self.ents[j]
            if (a.x - b.x) ** 2 + (a.y - b.y) ** 2 < (a.r + b.r) ** 2:
                actual.append((i, j))
                a.vx, b.vx = b.vx, a.vx
                a.vy, b.vy = b.vy, a.vy

        saved = brute - len(cand) if self.grid_on else 0
        self.saved_cum += saved
        pct = 100.0 * saved / brute if brute else 0.0
        self.canvas.actual_pairs = actual
        self.canvas.hud_lines = [
            f"entities: {n}",
            f"brute-force pairs: {brute}",
            f"broad-phase candidates: {len(cand)}" + ("" if self.grid_on else "  (grid OFF — testing everything)"),
            f"narrow-phase tests saved: {pct:.1f}%   ·   cumulative saved: {self.saved_cum}",
            f"colliding now: {len(actual)} (red)"]
        self.cand_draw = list(cand)
        self.last_brute, self.last_cand, self.last_actual = brute, len(cand), len(actual)
        self.canvas.update()

        self._acc += 1
        if self._acc >= 60:
            self._acc = 0
            if self.saved_cum != self._last_emit:
                self._last_emit = self.saved_cum
                self.bus.emit("broadphase_stats", saved=self.saved_cum)

    def showEvent(self, e):
        if not self.timer.isActive(): self.timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop(); super().hideEvent(e)


# ======================================================== PHYSICS RESPONSE ==
@dataclass
class PBody:
    x: float; y: float; px: float; py: float
    vx: float = 0.0; vy: float = 0.0
    r: float = 12.0; color: str = C_ACCENT
    sleep_t: float = 0.0; sleeping: bool = False; dead: bool = False

class _PhysCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.puffs = []
        self.setMinimumHeight(360)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#0c0d10"))
        w, h = self.width(), self.height()
        pg = self.page
        ptop = pg.platform_top()
        p.setBrush(QColor("#3d4450")); p.setPen(QPen(QColor("#5a6572"), 1))
        p.drawRect(QRectF(70, ptop, w - 140, 14))
        p.setPen(QColor(C_DIM)); p.setFont(mono(7))
        p.drawText(QPointF(74, ptop - 4), "platform — 14 px thick (tunnel target)")
        p.setPen(QPen(QColor(C_BORDER), 2)); p.drawLine(0, h - 36, w, h - 36)
        p.setPen(QColor("#33373d"))
        p.drawText(QPointF(6, h - 42), "ground")
        for (x, y, ttl) in self.puffs:
            p.setPen(QPen(_qc(C_ORANGE, int(220 * ttl)), 2))
            p.drawEllipse(QPointF(x, y), 6 + (1 - ttl) * 16, 6 + (1 - ttl) * 16)
        for c in pg.contacts:
            x, y, nx, ny, j, ttl = c
            a = min(1.0, ttl / 0.12)
            p.setPen(QPen(_qc(C_GREEN, int(200 * a)), 2))
            L = min(30.0, 4 + j * 0.02)
            p.drawLine(QPointF(x, y), QPointF(x + nx * L, y + ny * L))
        for b in pg.bodies:
            col = QColor(b.color)
            if b.sleeping: col.setAlpha(110)
            p.setBrush(col); p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(b.x, b.y), b.r, b.r)
            p.setPen(QColor("#10151a")); p.setFont(mono(7))
            p.drawText(QPointF(b.x - 3, b.y + 3), "z" if b.sleeping else "")
        p.setPen(QColor(C_DIM)); p.setFont(mono(9))
        st = pg.stats
        p.drawText(QPointF(10, 18),
                   f"bodies {st[0]} · sleeping {st[1]} · contacts {st[2]} · tunnelled {st[3]}")
        p.drawText(QPointF(10, h - 12),
                   "response = positional correction + impulse (j = -(1+e)·v·n) + friction · e is ENERGY RETENTION per bounce (energy ×e²)")

class PhysicsResponsePage(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.bodies, self.contacts = [], []
        self.restitution, self.friction, self.substeps = 0.55, 0.35, 2
        self.correct, self.sleeping_on = True, True
        self.tunnel_count, self._asleep_emitted, self._imp_t = 0, -1e9, -1e9
        self.stats = (0, 0, 0, 0)

        v = QVBoxLayout(self)
        v.addWidget(page_header("Physics Response — resolution, restitution & tunnelling",
            "Broad phase finds candidates; THIS is what happens next: depenetrate (positional correction), then apply an impulse along the contact normal proportional to closing velocity, scaled by restitution e. With e=0.6 each bounce keeps 60% of velocity — 36% of energy — watch bodies bleed energy until they fall asleep. The star: 🎯 fire a fast ball at the thin platform with substeps=1 and it TUNNELS straight through — discrete timesteps miss thin geometry, which is why engines add substeps or continuous collision detection."))
        row = QHBoxLayout()
        for label, attr, val in (("restitution", "restitution", 55), ("friction μ", "friction", 35)):
            row.addWidget(QLabel(label))
            s = QSlider(Qt.Horizontal); s.setRange(0, 100); s.setValue(val); s.setMaximumWidth(110)
            lab = QLabel(f"{val/100:.2f}")
            s.valueChanged.connect(lambda v2, a=attr, l2=lab: (setattr(self, a, v2 / 100.0),
                                                               l2.setText(f"{v2/100:.2f}")))
            setattr(self, attr + "_slider", s)
            row.addWidget(s); row.addWidget(lab); row.addSpacing(8)
        row.addWidget(QLabel("substeps"))
        self.sub_lbl = QLabel("2")
        ss = QSlider(Qt.Horizontal); ss.setRange(1, 8); ss.setValue(2); ss.setMaximumWidth(90)
        ss.valueChanged.connect(lambda v2: (setattr(self, "substeps", v2), self.sub_lbl.setText(str(v2))))
        row.addWidget(ss); row.addWidget(self.sub_lbl); row.addSpacing(8)
        self.corr_cb = QCheckBox("positional correction"); self.corr_cb.setChecked(True)
        self.corr_cb.toggled.connect(lambda on: setattr(self, "correct", on))
        self.sleep_cb = QCheckBox("sleeping"); self.sleep_cb.setChecked(True)
        self.sleep_cb.toggled.connect(lambda on: setattr(self, "sleeping_on", on))
        row.addWidget(self.corr_cb); row.addWidget(self.sleep_cb); row.addStretch(1)
        v.addLayout(row)

        row2 = QHBoxLayout()
        for txt, fn in (("☔ drop 10", self._drop), ("🎯 fire fast ball", self._fire), ("🧹 clear", self._clear)):
            b = QPushButton(txt); b.clicked.connect(fn); row2.addWidget(b)
        row2.addStretch(1)
        v.addLayout(row2)

        self.canvas = _PhysCanvas(self)
        v.addWidget(self.canvas, 1)
        self.timer = QTimer(self); self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)
        self._drop()

    def platform_top(self): return max(120.0, self.canvas.height() * 0.48)

    def _drop(self):
        for i in range(10):
            self.bodies.append(PBody(x=random.uniform(90, max(120, self.canvas.width() - 90)),
                                     y=40 + i * 26, px=0, py=0,
                                     vx=random.uniform(-40, 40), vy=0,
                                     r=random.uniform(10, 16), color=random.choice(PALETTE)))

    def _fire(self):
        self.bodies.append(PBody(x=12, y=self.platform_top() - 8, px=12, py=self.platform_top() - 8,
                                 vx=3300 + random.uniform(0, 600), vy=-40, r=9, color=C_RED))

    def _clear(self):
        self.bodies = []; self.contacts = []; self.tunnel_count = 0

    def _resolve_static(self, b, nx, ny, pen):
        if self.correct:
            b.x += nx * pen * 0.8; b.y += ny * pen * 0.8
        vn = b.vx * nx + b.vy * ny
        if vn < 0:
            j = -(1.0 + self.restitution) * vn
            b.vx += nx * j; b.vy += ny * j
            self.contacts.append([b.x - nx * b.r, b.y - ny * b.r, nx, ny, j, 0.12])
            if b.sleeping and j > 60:
                b.sleeping = False; b.sleep_t = 0.0
            tx, ty = b.vx - vn * nx, b.vy - vn * ny
            tm = math.hypot(tx, ty)
            if tm > 1e-3:
                jt = min(self.friction * j, tm)
                b.vx -= tx / tm * jt; b.vy -= ty / tm * jt
            now = time.monotonic()
            if j > 120 and now - self._imp_t > 1.2:
                self._imp_t = now
                self.bus.emit("physics_impact", j=int(j), e=round(self.restitution, 2))

    def _tick(self):
        dt = 1 / 60.0
        sdt = dt / self.substeps
        W = max(80, self.canvas.width()); H = max(120, self.canvas.height())
        ptop = self.platform_top(); pbot = ptop + 14
        self.contacts = []
        for _s in range(self.substeps):
            for b in self.bodies:
                if b.sleeping: continue
                b.px, b.py = b.x, b.y
                b.vy += 950 * sdt
                b.x += b.vx * sdt; b.y += b.vy * sdt
                if b.py + b.r <= ptop and b.y - b.r >= pbot and 70 < b.x < W - 70:
                    self.tunnel_count += 1
                    self.canvas.puffs.append([b.x, (ptop + pbot) / 2, 1.0])
                    self.bus.emit("tunnelled", vx=int(b.vx), substeps=self.substeps)
                    b.dead = True; continue
                if b.x < b.r: b.x = b.r; b.vx = abs(b.vx)
                if b.x > W - b.r: b.x = W - b.r; b.vx = -abs(b.vx)
                if b.y - b.r < 0: b.y = b.r; b.vy = abs(b.vy)
                if b.y + b.r > H - 36:
                    self._resolve_static(b, 0, -1, (b.y + b.r) - (H - 36))
                nx2 = min(W - 70, max(70.0, b.x)); ny2 = min(pbot, max(ptop, b.y))
                dx, dy = b.x - nx2, b.y - ny2
                d2 = dx * dx + dy * dy
                if d2 < b.r * b.r:
                    if d2 > 1e-9:
                        d = math.sqrt(d2)
                        self._resolve_static(b, dx / d, dy / d, b.r - d)
                    else:
                        side = -1 if b.py <= (ptop + pbot) / 2 else 1
                        self._resolve_static(b, 0, side, b.r + (ptop - b.y if side < 0 else b.y - pbot))
            for i in range(len(self.bodies)):
                for j2 in range(i + 1, len(self.bodies)):
                    a, b = self.bodies[i], self.bodies[j2]
                    dx, dy = b.x - a.x, b.y - a.y
                    d = math.hypot(dx, dy)
                    pen = a.r + b.r - d
                    if pen > 0 and d > 1e-6:
                        nx, ny = dx / d, dy / d
                        if self.correct:
                            a.x -= nx * pen * 0.4; a.y -= ny * pen * 0.4
                            b.x += nx * pen * 0.4; b.y += ny * pen * 0.4
                        rvx, rvy = b.vx - a.vx, b.vy - a.vy
                        vn = rvx * nx + rvy * ny
                        if vn < 0:
                            jimp = -(1.0 + self.restitution) * vn / 2.0
                            a.vx -= nx * jimp; a.vy -= ny * jimp
                            b.vx += nx * jimp; b.vy += ny * jimp
                            self.contacts.append([(a.x + b.x) / 2, (a.y + b.y) / 2, nx, ny, jimp * 2, 0.12])
                            for bd in (a, b):
                                if bd.sleeping and jimp > 30:
                                    bd.sleeping = False; bd.sleep_t = 0.0
            if self.sleeping_on:
                for b in self.bodies:
                    if b.sleeping: continue
                    if b.vx * b.vx + b.vy * b.vy < 700:
                        b.sleep_t += sdt
                        if b.sleep_t > 0.7: b.sleeping = True
                    else:
                        b.sleep_t = 0.0
        self.bodies = [b for b in self.bodies if not b.dead]
        for c in self.contacts: c[5] -= dt
        self.contacts = [c for c in self.contacts if c[5] > 0]
        for pf in self.canvas.puffs: pf[2] -= 0.05
        self.canvas.puffs = [pf for pf in self.canvas.puffs if pf[2] > 0]
        sleeping = sum(1 for b in self.bodies if b.sleeping)
        self.stats = (len(self.bodies), sleeping, len(self.contacts), self.tunnel_count)
        now = time.monotonic()
        if sleeping >= 6 and now - self._asleep_emitted > 5:
            self._asleep_emitted = now
            self.bus.emit("bodies_asleep", count=sleeping)
        self.canvas.update()

    def showEvent(self, e):
        if not self.timer.isActive(): self.timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop(); super().hideEvent(e)


# ========================================================= AI & PATHFINDING =
PF_COLS, PF_ROWS = 26, 16

def _pf_h(c, r, goal):
    return abs(c - goal[0]) + abs(r - goal[1])

class PfSearch:
    """Step-able grid search. alg: bfs | dijkstra | greedy | astar."""
    def __init__(self, walls, mud, start, goal, alg, cols=PF_COLS, rows=PF_ROWS):
        self.walls, self.mud, self.start, self.goal = walls, mud, start, goal
        self.alg, self.cols, self.rows = alg, cols, rows
        self.g = {start: 0.0}
        self.came, self.closed = {}, set()
        self.seq = 0
        self.open = [(-1, start)] if alg == "bfs" else [(0.0, 0, start)]
        self.done, self.path, self.cost, self.expanded = False, None, 0.0, 0

    def step(self, n=1):
        for _ in range(n):
            if self.done or not self.open:
                self.done = True; return
            if self.alg == "bfs":
                _s, cur = self.open.pop(0)
            else:
                best_i = min(range(len(self.open)), key=lambda i: self.open[i][0])
                _pri, _s, cur = self.open.pop(best_i)
            if cur in self.closed: continue
            self.closed.add(cur); self.expanded += 1
            if cur == self.goal:
                self.path, p = [], cur
                while p is not None:
                    self.path.append(p); p = self.came.get(p)
                self.path.reverse()
                self.cost = self.g[cur]; self.done = True; return
            gc = self.g[cur]
            for (nc, nr) in self._nbrs(cur):
                step_cost = 5.0 if (nc, nr) in self.mud else 1.0
                ng = gc + (1.0 if self.alg in ("bfs", "greedy") else step_cost)
                if ng < self.g.get((nc, nr), 1e18):
                    self.g[(nc, nr)] = ng
                    self.came[(nc, nr)] = cur
                    self.seq += 1
                    if self.alg == "bfs":
                        self.open.append((self.seq, (nc, nr)))
                    elif self.alg == "dijkstra":
                        self.open.append((ng, self.seq, (nc, nr)))
                    elif self.alg == "greedy":
                        self.open.append((_pf_h(nc, nr, self.goal), self.seq, (nc, nr)))
                    else:
                        self.open.append((ng + _pf_h(nc, nr, self.goal), self.seq, (nc, nr)))

    def _nbrs(self, cell):
        c, r = cell
        for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nc, nr = c + dc, r + dr
            if 0 <= nc < self.cols and 0 <= nr < self.rows and (nc, nr) not in self.walls:
                yield nc, nr

def solve_path(walls, mud, start, goal, alg):
    s = PfSearch(walls, mud, start, goal, alg)
    while not s.done: s.step(10_000)
    return s.path, s.expanded, s.cost

PF_ALGS = [("bfs", "BFS — uninformed"), ("dijkstra", "Dijkstra — uniform cost"),
           ("greedy", "Greedy best-first"), ("astar", "A* — g + h")]

class _PFCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.hover = None
        self.setMouseTracking(True)
        self.setMinimumHeight(320)

    def cell_at(self, pos):
        cs = self.page.cell_size
        c, r = int(pos.x() / cs), int((pos.y() - 26) / cs)
        return (c, r) if 0 <= c < PF_COLS and 0 <= r < PF_ROWS else None

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        pg = self.page
        cs = pg.cell_size
        ox, oy = 0, 26
        pulse = (math.sin(time.monotonic() * 6) + 1) / 2
        for r in range(PF_ROWS):
            for c in range(PF_COLS):
                cell = (c, r)
                x, y = ox + c * cs, oy + r * cs
                fill = "#1a1d22"
                if cell in pg.walls: fill = "#2a2f38"
                elif cell in pg.mud: fill = "#4a3a20"
                elif pg.search and cell in pg.search.closed: fill = "#1d3245"
                elif pg.search and any(o[-1] == cell for o in pg.search.open):
                    fill = QColor("#2e5e6e").lighter(100 + int(40 * pulse)).name()
                p.setBrush(QColor(fill)); p.setPen(QPen(QColor("#22252b"), 1))
                p.drawRect(QRectF(x, y, cs - 1, cs - 1))
                if cell in pg.mud and cell not in pg.walls:
                    p.setPen(QColor("#8a6d3b")); p.setFont(mono(7))
                    p.drawText(QRectF(x, y, cs, cs), Qt.AlignCenter, "5")
        if pg.search and pg.search.path:
            pts = [QPointF(ox + c * cs + cs / 2, oy + r * cs + cs / 2) for (c, r) in pg.search.path]
            p.setPen(QPen(QColor(C_YELLOW), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPolyline(QPolygonF(pts))
        sc, sr = pg.start; gc_, gr = pg.goal
        p.setBrush(QColor(C_ACCENT)); p.setPen(Qt.NoPen)
        p.drawRect(QRectF(ox + sc * cs + 5, oy + sr * cs + 5, cs - 11, cs - 11))
        p.setBrush(QColor(C_GREEN))
        p.drawEllipse(QPointF(ox + gc_ * cs + cs / 2, oy + gr * cs + cs / 2), cs / 2 - 4, cs / 2 - 4)
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(4, 18),
                   "paint: walls ▩ · mud ×5 cost · drag S and ◎ · frontier pulses, visited fades blue, path in gold")
        if self.hover and pg.search and self.hover in pg.search.g:
            g = pg.search.g[self.hover]
            h = _pf_h(self.hover[0], self.hover[1], pg.goal)
            p.setPen(QColor(C_YELLOW))
            p.drawText(QPointF(self.width() - 170, 18), f"g={g:.0f} h={h} f={g + h:.0f}")

    def mousePressEvent(self, e): self.page._paint_at(self.cell_at(e.position()))

    def mouseMoveEvent(self, e):
        self.hover = self.cell_at(e.position())
        if e.buttons() & Qt.LeftButton: self.page._paint_at(self.hover)
        self.update()

class AIPathPage(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.cell_size = 28
        self.walls, self.mud = set(), set()
        self.start, self.goal = (2, 8), (PF_COLS - 3, 8)
        self.search = None
        self.results, self._results_maze = {}, None
        self.maze_id = 1
        self.paint_mode = "wall"
        self._random_maze()

        v = QVBoxLayout(self)
        v.addWidget(page_header("AI & Pathfinding — informed search on a grid",
            "Every AI that navigates runs something from this family. BFS ignores terrain cost; Dijkstra guarantees the cheapest path but floods the map; Greedy beelines and is cheap but can return a SUBOPTIMAL path; A* = Dijkstra's guarantee + Greedy's focus (f = g + h), as long as h never overestimates. Paint mud (×5 cost) and race all four — the results table is the whole lesson."))
        row = QHBoxLayout()
        row.addWidget(QLabel("algorithm"))
        self.alg_combo = QComboBox()
        for _k, label in PF_ALGS: self.alg_combo.addItem(label)
        self.alg_combo.setCurrentIndex(3)
        row.addWidget(self.alg_combo)
        for txt, fn in (("▶ run", self._run), ("🏁 race all 4", self._race),
                        ("↺ reset", self._reset_search), ("🎲 new maze", self._random_maze),
                        ("🧹 clear", self._clear)):
            b = QPushButton(txt); b.clicked.connect(fn); row.addWidget(b)
        row.addSpacing(10)
        for mode, tip in (("wall", "paint walls"), ("mud", "paint mud (cost 5)"),
                          ("erase", "erase"), ("start", "place start"), ("goal", "place goal")):
            rb = QRadioButton(mode); rb.setToolTip(tip)
            rb.toggled.connect(lambda on, m=mode: on and setattr(self, "paint_mode", m))
            if mode == "wall": rb.setChecked(True)
            row.addWidget(rb)
        row.addStretch(1)
        v.addLayout(row)

        h = QHBoxLayout()
        self.canvas = _PFCanvas(self)
        h.addWidget(self.canvas, 1)
        side = QWidget(); side.setFixedWidth(300)
        sv = QVBoxLayout(side); sv.setContentsMargins(0, 0, 0, 0)
        sv.addWidget(QLabel("<b>Race results — this maze</b>"))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["algorithm", "expanded", "path cost"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        sv.addWidget(self.table)
        self.status = QLabel(""); self.status.setWordWrap(True); self.status.setObjectName("dim")
        sv.addWidget(self.status); sv.addStretch(1)
        h.addWidget(side)
        v.addLayout(h)

        self.timer = QTimer(self); self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)
        self._reset_search()

    def _random_maze(self):
        for _try in range(40):
            walls = {(c, r) for c in range(PF_COLS) for r in range(PF_ROWS)
                     if random.random() < 0.30 and (c, r) not in (self.start, self.goal)}
            mud = {(c, r) for c in range(PF_COLS) for r in range(PF_ROWS)
                   if random.random() < 0.10 and (c, r) not in walls}
            path, _e, _c = solve_path(walls, mud, self.start, self.goal, "astar")
            if path:
                self.walls, self.mud = walls, mud
                self.maze_id += 1
                self._reset_search(); return

    def _clear(self):
        self.walls, self.mud = set(), set()
        self.maze_id += 1; self._reset_search()

    def _paint_at(self, cell):
        if cell is None or cell in (self.start, self.goal): return
        if self.paint_mode == "wall":
            self.mud.discard(cell); self.walls.add(cell)
        elif self.paint_mode == "mud":
            self.walls.discard(cell); self.mud.add(cell)
        elif self.paint_mode == "erase":
            self.walls.discard(cell); self.mud.discard(cell)
        elif self.paint_mode == "start":
            self.start = cell
        elif self.paint_mode == "goal":
            self.goal = cell
        self.maze_id += 1
        self._reset_search()

    def _alg_key(self):
        return PF_ALGS[self.alg_combo.currentIndex()][0]

    def _reset_search(self):
        self.search = PfSearch(self.walls, self.mud, self.start, self.goal, self._alg_key())
        self.canvas.update()

    def _run(self): self._reset_search()

    def _race(self):
        self.results = {}
        self._results_maze = self.maze_id
        for key, label in PF_ALGS:
            path, expanded, cost = solve_path(self.walls, self.mud, self.start, self.goal, key)
            self.results[key] = (len(path) if path else 0, expanded, cost, path is not None)
            self.bus.emit("search_done", alg=key, expanded=expanded,
                          cost=round(cost, 1), found=path is not None)
        if "astar" in self.results and "greedy" in self.results:
            a, g = self.results["astar"], self.results["greedy"]
            if a[3] and g[3] and a[2] <= g[2] + 1e-6 and a[1] <= 0.75 * g[1]:
                self.bus.emit("astar_win", astar=a[1], greedy=g[1])
                self.status.setText(f"💡 A* expanded {a[1]} vs greedy {g[1]} at equal cost — an admissible heuristic paying rent.")
        self._refresh_table(); self._reset_search()

    def _refresh_table(self):
        self.table.setRowCount(0)
        best = min((v[2] for v in self.results.values() if v[3]), default=None)
        for key in [k for k, _l in PF_ALGS]:
            if key not in self.results: continue
            ln, ex, cost, ok = self.results[key]
            r = self.table.rowCount(); self.table.insertRow(r)
            cost_s = f"{cost:.0f}" if ok else "— no path"
            for c, txt in enumerate((dict(PF_ALGS)[key].split(" — ")[0], str(ex), cost_s)):
                it = QTableWidgetItem(txt)
                if ok and best is not None and abs(cost - best) < 1e-6 and c == 2:
                    it.setForeground(QColor(C_GREEN))
                self.table.setItem(r, c, it)

    def _tick(self):
        if self.search and not self.search.done:
            self.search.step(6)
            if self.search.done and self.search.path:
                key = self.search.alg
                if self._results_maze != self.maze_id:
                    self.results = {}; self._results_maze = self.maze_id
                self.results[key] = (len(self.search.path), self.search.expanded,
                                     self.search.cost, True)
                self._refresh_table()
                self.bus.emit("search_done", alg=key, expanded=self.search.expanded,
                              cost=round(self.search.cost, 1))
                if key == "astar" and "greedy" in self.results:
                    g = self.results["greedy"]
                    if g[3] and self.search.cost <= g[2] + 1e-6 and self.search.expanded <= 0.75 * g[1]:
                        self.bus.emit("astar_win", astar=self.search.expanded, greedy=g[1])
        self.canvas.update()

    def showEvent(self, e):
        if not self.timer.isActive(): self.timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop(); super().hideEvent(e)


# ========================================================= NOISE & WORLDGEN ==
def _hash2(ix, iy, seed):
    h = (ix * 374761393 + iy * 668265263 + seed * 2246822519) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0

def vnoise(x, y, seed):
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy)
    a = _hash2(ix, iy, seed);     b = _hash2(ix + 1, iy, seed)
    c = _hash2(ix, iy + 1, seed); d = _hash2(ix + 1, iy + 1, seed)
    return lerp(lerp(a, b, fx), lerp(c, d, fx), fy)

def fbm(x, y, seed, octaves=4, persistence=0.5, freq=3.0):
    total, amp, f, norm = 0.0, 1.0, freq, 0.0
    for _ in range(octaves):
        total += vnoise(x * f, y * f, seed) * amp
        norm += amp; amp *= persistence; f *= 2.0
    return total / norm

BIOME_BANDS = [(0.34, "#123a5e"), (0.44, "#1d5e8a"), (0.50, "#d8c27a"),
               (0.68, "#4a8f3c"), (0.78, "#2f6e33"), (0.88, "#8a8a8a"),
               (1.01, "#eef2f5")]

class _NoiseCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setMinimumHeight(320)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        pg = self.page
        if pg.img is None: return
        iw, ih = pg.img.width(), pg.img.height()
        s = min((w - 40) / iw, (h - 110) / ih)
        R = QRectF(20, 16, iw * s, ih * s)
        p.drawImage(R, pg.img)
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(20, 12), f"world map — seed {pg.seed}")
        sy = R.bottom() + 26
        p.setPen(QPen(QColor(C_BORDER), 1)); p.drawLine(R.left(), sy + 44, R.right(), sy + 44)
        pts = [QPointF(R.left() + (i / (iw - 1)) * R.width(), sy + 44 - pg.slice[i] * 88)
               for i in range(iw)]
        p.setPen(QPen(QColor(C_ACCENT), 2)); p.drawPolyline(QPolygonF(pts))
        p.setPen(QColor(C_DIM))
        p.drawText(QPointF(R.left(), sy + 62),
                   "1-D slice — what a side-scrolling terrain generator consumes")
        p.setFont(mono(9)); p.setPen(QColor(C_TEXT))
        p.drawText(QPointF(R.right() + 12, R.top() + 16),
                   f"min {pg.hmin:.3f}  max {pg.hmax:.3f}  mean {pg.hmean:.3f}")
        p.drawText(QPointF(R.right() + 12, R.top() + 46), "same seed ⇒ same world.")
        p.drawText(QPointF(R.right() + 12, R.top() + 60), "Ship the seed, not the map.")

class NoisePage(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.seed, self.oct, self.pers, self.freq = 1337, 4, 0.5, 3.0
        self.mode, self.img = "biomes", None
        self.slice = []
        self.hmin = self.hmax = self.hmean = 0.0
        v = QVBoxLayout(self)
        v.addWidget(page_header("Noise & Worldgen — procedural worlds from a seed",
            "Random per pixel is TV static; coherent noise is terrain. Value noise interpolates a hashed lattice (deterministic: seed + integer coords → same value forever), and fBm stacks octaves at doubling frequency — octave 1 draws continents, later octaves add detail. Thresholding the height field into bands gives biomes. Change the seed: same math, different world — shipping the 9-digit seed ships the whole world."))
        row = QHBoxLayout()
        row.addWidget(QLabel("seed"))
        self.seed_edit = QLineEdit(str(self.seed)); self.seed_edit.setMaximumWidth(120)
        self.seed_edit.setFont(mono(10))
        self.seed_edit.editingFinished.connect(self._seed_changed)
        row.addWidget(self.seed_edit)
        dice = QPushButton("🎲 random world"); dice.clicked.connect(self._dice)
        row.addWidget(dice); row.addSpacing(12)
        for label, attr, lo, hi, val, fmt in (("octaves", "oct", 1, 6, 4, "{:d}"),
                                              ("persistence", "pers", 10, 90, 50, "{:.2f}"),
                                              ("frequency", "freq", 10, 90, 30, "{:.1f}")):
            row.addWidget(QLabel(label))
            lab = QLabel(fmt.format(val if attr == "oct" else val / (100 if attr == "pers" else 10)))
            s = QSlider(Qt.Horizontal); s.setRange(lo, hi); s.setValue(val)
            s.setMaximumWidth(90); s.setTracking(False)
            if attr == "oct":
                s.valueChanged.connect(lambda v2: (setattr(self, "oct", v2), lab.setText(str(v2)), self._regen()))
            elif attr == "pers":
                s.valueChanged.connect(lambda v2: (setattr(self, "pers", v2 / 100), lab.setText(f"{v2/100:.2f}"), self._regen()))
            else:
                s.valueChanged.connect(lambda v2: (setattr(self, "freq", v2 / 10), lab.setText(f"{v2/10:.1f}"), self._regen()))
            row.addWidget(s); row.addWidget(lab); row.addSpacing(8)
        self.mode_combo = QComboBox(); self.mode_combo.addItems(["biomes", "raw height"])
        self.mode_combo.currentTextChanged.connect(lambda t: (setattr(self, "mode", t), self._regen()))
        row.addWidget(self.mode_combo); row.addStretch(1)
        v.addLayout(row)
        self.canvas = _NoiseCanvas(self)
        v.addWidget(self.canvas, 1)
        self._regen()

    def _seed_changed(self):
        txt = self.seed_edit.text().strip()
        try: self.seed = int(txt)
        except ValueError: self.seed = zlib.crc32(txt.encode()) & 0xFFFFFFF
        self._regen()
        self.bus.emit("world_generated", seed=self.seed)

    def _dice(self):
        self.seed = random.randint(1, 99999999)
        self.seed_edit.setText(str(self.seed))
        self._regen()
        self.bus.emit("world_generated", seed=self.seed)

    def _regen(self):
        W, H = 208, 128
        img = QImage(W, H, QImage.Format_RGB32)
        vals = []
        for j in range(H):
            for i in range(W):
                hv = fbm(i / 48, j / 48, self.seed, self.oct, self.pers, self.freq)
                vals.append(hv)
                if self.mode == "raw height":
                    g = int(hv * 255); img.setPixel(i, j, QColor(g, g, g).rgb())
                else:
                    col = next(c for t, c in BIOME_BANDS if hv < t)
                    img.setPixel(i, j, QColor(col).rgb())
        self.img = img
        self.slice = [fbm(i / 48, 0.5, self.seed, self.oct, self.pers, self.freq) for i in range(W)]
        self.hmin, self.hmax = min(vals), max(vals)
        self.hmean = sum(vals) / len(vals)
        self.canvas.update()


# ========================================================= RESOURCE MANAGER =
@dataclass
class Asset:
    name: str; size: int; kind: str
    state: str = "unloaded"
    progress: float = 0.0
    refs: set = field(default_factory=set)
    pending: set = field(default_factory=set)
    last_used: int = 0

ASSET_DB = [
    ("tex/bark_albedo", 8, "texture"), ("tex/leaves_albedo", 6, "texture"),
    ("tex/stone_albedo", 10, "texture"), ("tex/torch_glow", 3, "texture"),
    ("tex/asphalt", 7, "texture"), ("tex/brick", 5, "texture"),
    ("tex/sky_clouds", 12, "texture"),
    ("mesh/tree_low", 2, "mesh"), ("mesh/rock", 3, "mesh"),
    ("mesh/pillar", 4, "mesh"), ("mesh/car", 6, "mesh"),
    ("audio/birds", 5, "audio"), ("audio/wind", 4, "audio"),
    ("audio/drip", 2, "audio"), ("audio/dragon", 9, "audio"),
    ("audio/crowd", 6, "audio"), ("audio/rain", 3, "audio"),
    ("fx/explosion", 1, "effect"), ("fx/spark", 1, "effect"),
]
LEVELS = {
    "Forest":  ["tex/bark_albedo", "tex/leaves_albedo", "tex/sky_clouds",
                "mesh/tree_low", "mesh/rock", "audio/birds", "audio/wind"],
    "Dungeon": ["tex/stone_albedo", "tex/torch_glow", "mesh/pillar", "mesh/rock",
                "audio/drip", "audio/dragon", "fx/explosion"],
    "City":    ["tex/asphalt", "tex/brick", "tex/sky_clouds", "mesh/car",
                "mesh/pillar", "audio/crowd", "audio/rain", "fx/spark"],
}
LEVEL_EMOJI = {"Forest": "🌳", "Dungeon": "🏰", "City": "🏙"}

class MemoryBar(QWidget):
    def __init__(self):
        super().__init__()
        self.used, self.budget = 0, 48
        self.setFixedHeight(26)

    def set(self, used, budget):
        self.used, self.budget = used, budget; self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(C_PANEL))
        frac = self.used / max(1, self.budget)
        col = C_GREEN if frac < 0.7 else C_ORANGE if frac < 1.0 else C_RED
        p.setPen(QPen(QColor(C_BORDER), 1))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 6, 6)
        if self.used > 0:
            fw = max(8, int((self.width() - 2) * min(1.0, frac)))
            p.setBrush(QColor(col)); p.setPen(Qt.NoPen)
            p.drawRoundedRect(1, 1, fw, self.height() - 2, 5, 5)
        p.setPen(QColor("#10151a" if frac > 0.35 else C_TEXT))
        p.setFont(mono(9))
        p.drawText(self.rect(), Qt.AlignCenter, f"{self.used} / {self.budget} MB VRAM budget")

class ResourcePage(QWidget):
    BUDGET = 48

    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.assets = {n: Asset(n, s, k) for n, s, k in ASSET_DB}
        self.queue = deque()
        self.loaded_levels = set()
        self.hits = self.misses = self.evictions = 0
        self.tick_n = 0

        v = QVBoxLayout(self)
        v.addWidget(page_header("Resource Manager",
            "Assets load asynchronously through a queue, deduplicate in a cache (re-requesting a resident asset = cache hit), pin by per-level reference counts, and evict LRU-first when the memory budget would overflow. Load two overlapping levels to see hits; load all three to force eviction."))
        top = QHBoxLayout()
        self.membar = MemoryBar(); self.membar.set(0, self.BUDGET)
        top.addWidget(self.membar, 1)
        for name in LEVELS:
            b = QPushButton(f"{LEVEL_EMOJI[name]} {name}")
            b.clicked.connect(lambda _=False, n=name: self._toggle_level(n))
            top.addWidget(b)
            setattr(self, f"btn_{name}", b)
        flush = QPushButton("🔥 Flush unused"); flush.clicked.connect(self._flush)
        reset = QPushButton("Reset"); reset.clicked.connect(self._reset)
        top.addWidget(flush); top.addWidget(reset)
        v.addLayout(top)

        stats = QHBoxLayout()
        self.st = {k: QLabel("—") for k in ("hits", "misses", "rate", "ev", "used")}
        for w in self.st.values(): w.setFont(mono(10)); w.setStyleSheet(f"color:{C_ACCENT};")
        for k, name in (("hits", "cache hits"), ("misses", "cache misses"),
                        ("rate", "hit rate"), ("ev", "evictions"), ("used", "resident")):
            box = QVBoxLayout(); box.addWidget(QLabel(name)); box.addWidget(self.st[k])
            stats.addLayout(box)
        stats.addStretch(1)
        v.addLayout(stats)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Asset", "Kind", "Size", "State", "Refs (levels)", "Idle"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        v.addWidget(self.table, 1)

        self.timer = QTimer(self); self.timer.setInterval(60)
        self.timer.timeout.connect(self._tick)

    def used_mb(self):
        return sum(a.size for a in self.assets.values() if a.state == "loaded")

    def _toggle_level(self, name):
        if name in self.loaded_levels:
            self.loaded_levels.discard(name)
            for n in LEVELS[name]:
                self.assets[n].refs.discard(name)
        else:
            self.loaded_levels.add(name)
            for n in LEVELS[name]:
                a = self.assets[n]
                if a.state == "loaded":
                    self.hits += 1
                    a.refs.add(name); a.last_used = self.tick_n
                    self.bus.emit("cache_hit", asset=n, level=name)
                elif a.state == "loading":
                    a.pending.add(name)
                else:
                    self.misses += 1
                    a.state = "loading"; a.progress = 0.0
                    a.pending = {name}
                    self.queue.append(n)
        self._sync_buttons()

    def _evictIfNeeded(self):
        while self.used_mb() > self.BUDGET:
            victims = [a for a in self.assets.values()
                       if a.state == "loaded" and not a.refs]
            if not victims: return
            victim = min(victims, key=lambda a: a.last_used)
            victim.state = "unloaded"; victim.progress = 0.0
            self.evictions += 1
            self.bus.emit("asset_evicted", asset=victim.name, lru=True)

    def _flush(self):
        for a in self.assets.values():
            if a.state == "loaded" and not a.refs:
                a.state = "unloaded"; a.progress = 0.0
                self.evictions += 1

    def _reset(self):
        self.queue.clear(); self.loaded_levels.clear()
        self.hits = self.misses = self.evictions = 0
        for a in self.assets.values():
            a.state, a.progress, a.refs, a.pending, a.last_used = "unloaded", 0.0, set(), set(), 0
        self._sync_buttons()

    def _sync_buttons(self):
        for name in LEVELS:
            b = getattr(self, f"btn_{name}")
            mark = "✓ unload" if name in self.loaded_levels else "load"
            b.setText(f"{LEVEL_EMOJI[name]} {name}  ({mark})")

    def _tick(self):
        self.tick_n += 1
        if self.queue:
            a = self.assets[self.queue[0]]
            a.progress += 0.10
            if a.progress >= 1.0:
                a.state = "loaded"; a.progress = 1.0
                a.refs |= a.pending; a.pending = set()
                a.last_used = self.tick_n
                self.bus.emit("asset_loaded", asset=a.name, size_mb=a.size)
                self.queue.popleft()
                self._evictIfNeeded()
        self._refresh_ui()

    def _refresh_ui(self):
        used = self.used_mb()
        self.membar.set(used, self.BUDGET)
        rate = 100.0 * self.hits / max(1, self.hits + self.misses)
        self.st["hits"].setText(str(self.hits))
        self.st["misses"].setText(str(self.misses))
        self.st["rate"].setText(f"{rate:.0f}%")
        self.st["ev"].setText(str(self.evictions))
        over = "  ⚠ OVER BUDGET" if used > self.BUDGET else ""
        self.st["used"].setText(f"{used} MB{over}")
        self.table.setRowCount(0)
        for row, a in enumerate(self.assets.values()):
            if a.state == "loaded":   state = "● loaded"
            elif a.state == "loading": state = f"loading {int(a.progress*100):3d}%"
            else:                      state = "○ unloaded"
            vals = [a.name, a.kind, f"{a.size} MB", state,
                    ", ".join(sorted(a.refs)) or "—",
                    f"{self.tick_n - a.last_used}s" if a.state == "loaded" else "—"]
            self.table.insertRow(row)
            for c, txt in enumerate(vals):
                it = QTableWidgetItem(txt)
                if a.state == "loaded":   it.setForeground(QColor(C_GREEN))
                elif a.state == "loading": it.setForeground(QColor(C_ACCENT))
                else:                      it.setForeground(QColor(C_DIM))
                self.table.setItem(row, c, it)

    def showEvent(self, e):
        if not self.timer.isActive(): self.timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop(); super().hideEvent(e)


# ================================================================= PROFILER =
PROF_UPDATE = [("Script/GC", C_PURPLE, 2.4), ("AI", C_ORANGE, 2.8),
               ("Physics", C_GREEN, 3.4), ("Animation", C_YELLOW, 1.8)]
PROF_RENDER = [("Cull + Sort", C_PINK, 1.3), ("Render Submit", C_ACCENT, 2.1)]
PROF_ALL    = PROF_UPDATE + PROF_RENDER
PROF_BUDGET = 16.6
PROF_AXIS_MS = 36.0

class _ProfCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.frames = deque(maxlen=64)
        self.totals = deque(maxlen=280)
        self.gc_armed, self.burst, self.burst_cd = False, 0, 4.0
        self.hitches = 0
        self.hover = None
        self.setMinimumHeight(300)
        self.setMouseTracking(True)
        self.timer = QTimer(self); self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)

    def _build(self):
        pg = self.page
        if pg.burst_cb.isChecked():
            self.burst_cd -= 0.016
            if self.burst_cd <= 0:
                self.burst, self.burst_cd = 2, random.uniform(3.5, 6.5)
        spans, t = [], 0.0
        def add(name, dur, depth, color):
            nonlocal t
            spans.append(dict(name=name, t0=t, dur=dur, d=depth, color=color))
            t += dur
        add("input", 0.3 + random.random() * 0.25, 0, "#4a5568")
        u0 = t
        for name, color, base in PROF_UPDATE:
            cost = base * random.uniform(0.72, 1.35) + pg.inject.get(name, 0.0)
            if name == "Script/GC" and self.gc_armed:
                cost += 11.5; self.gc_armed = False
            if name == "AI" and self.burst > 0:
                cost *= 3.2
            add(name, cost, 1, color)
        add("update", t - u0, 0, "#33383f")
        r0 = t
        for name, color, base in PROF_RENDER:
            add(name, base * random.uniform(0.75, 1.3) + pg.inject.get(name, 0.0), 1, color)
        add("render", t - r0, 0, "#33383f")
        add("present", 0.5 + random.random() * 0.3, 0, "#4a5568")
        if self.burst > 0: self.burst -= 1
        self.frames.append(spans)
        self.totals.append(t)
        if t > PROF_BUDGET * 1.5: self.hitches += 1

    def _tick(self):
        if self.page.live_cb.isChecked():
            self._build()
        self.update()

    def _geom(self):
        return 64.0, 26.0, (self.width() - 76) / PROF_AXIS_MS, 13

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        L, T, pxms, rh = self._geom()
        p.setFont(mono(8))
        for ms in range(0, int(PROF_AXIS_MS) + 1, 5):
            x = L + ms * pxms
            p.setPen(QPen(QColor("#1c1f24"), 1))
            p.drawLine(QPointF(x, T), QPointF(x, h - 20))
            p.setPen(QColor(C_DIM)); p.drawText(QPointF(x - 6, T - 8), f"{ms}ms")
        bx = L + PROF_BUDGET * pxms
        p.setPen(QPen(QColor(C_GREEN, 150), 1, Qt.DashLine))
        p.drawLine(QPointF(bx, T - 4), QPointF(bx, h - 20))
        p.setPen(QColor(C_GREEN)); p.drawText(QPointF(bx + 4, T - 4), "budget 16.6")
        rows = int((h - T - 30) / rh)
        view = list(self.frames)[-rows:]
        for i, spans in enumerate(view):
            y = T + i * rh
            for s in spans:
                x0 = L + s["t0"] * pxms; x1 = L + (s["t0"] + s["dur"]) * pxms
                r = QRectF(x0, y + 1.5, max(1.5, x1 - x0 - 1), rh - 3)
                hot = self.hover is not None and self.hover[0] == i and self.hover[1] is s
                c = QColor(s["color"])
                if s["d"] == 0: c.setAlpha(90)
                p.setBrush(QColor(c).lighter(140) if hot else c); p.setPen(Qt.NoPen)
                p.drawRoundedRect(r, 2, 2)
                end = s["t0"] + s["dur"]
                if end > PROF_BUDGET:
                    ov0 = max(s["t0"], PROF_BUDGET)
                    p.setBrush(QColor(239, 83, 80, 110))
                    p.drawRect(QRectF(L + ov0 * pxms, y + 1.5, (end - ov0) * pxms, rh - 3))
                if s["d"] == 1 and (x1 - x0) > 52:
                    p.setPen(QColor("#10151a")); p.setFont(mono(7))
                    p.drawText(r.adjusted(3, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft,
                               s["name"][:int((x1 - x0) / 4.4)])
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(8, T - 8), "flame chart — each row is one frame, newest at the bottom")
        p.drawText(QPointF(8, h - 8),
                   "red overlay = past frame budget · depth-0 bands wrap their systems · click a block to inspect")
        if self.hover:
            i, s = self.hover
            if s is not None:
                tot = sum(sp["dur"] for sp in self.frames[i]) if i < len(self.frames) else 0
                p.setPen(QColor(C_YELLOW)); p.setFont(mono(9))
                p.drawText(QPointF(w - 330, h - 8),
                           f"{s['name']}: {s['dur']:.2f} ms  ({100*s['dur']/max(tot,1e-6):.0f}% of a {tot:.1f} ms frame)")

    def _pick(self, pos):
        L, T, pxms, rh = self._geom()
        row = int((pos.y() - T) / rh)
        if not (0 <= row < len(self.frames)) or pos.x() < L: return row, None
        tt = (pos.x() - L) / pxms
        best = None
        for s in self.frames[row]:
            if s["t0"] <= tt < s["t0"] + s["dur"]:
                if best is None or s["d"] > best["d"]: best = s
        return row, best

    def mouseMoveEvent(self, e):
        self.hover = self._pick(e.position()); self.update()

    def leaveEvent(self, e):
        self.hover = None; self.update()

    def mousePressEvent(self, e):
        row, s = self._pick(e.position())
        if s is not None and s["d"] == 1:
            self.page.bus.emit("profiler_inspect", system=s["name"], ms=round(s["dur"], 2))

    def start(self):
        if not self.timer.isActive(): self.timer.start()

    def stop(self): self.timer.stop()

class _ProfHist(QWidget):
    def __init__(self, canvas):
        super().__init__()
        self.canvas = canvas
        self.setFixedHeight(112)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(C_PANEL))
        w, h = self.width(), self.height()
        totals = list(self.canvas.totals)
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(8, 14), "frame-time histogram — the spike on the right is what players feel")
        if len(totals) < 10: return
        BINS, MAXMS = 26, 39.0
        bins = [0] * BINS
        for t in totals:
            bins[min(BINS - 1, int(t / MAXMS * BINS))] += 1
        bw = (w - 20) / BINS
        peak = max(bins)
        for i, c in enumerate(bins):
            bh = (c / peak) * (h - 46)
            mid = (i + 0.5) / BINS * MAXMS
            p.setBrush(QColor(C_RED if mid > PROF_BUDGET * 1.5 else
                              C_ORANGE if mid > PROF_BUDGET else C_GREEN))
            p.setPen(Qt.NoPen)
            p.drawRect(QRectF(10 + i * bw, h - 24 - bh, bw - 1.5, bh))
        for ms, col, lab in ((PROF_BUDGET, C_GREEN, "budget"),
                             (sorted(totals)[int(0.99 * (len(totals) - 1))], C_ACCENT, "p99")):
            x = 10 + ms / MAXMS * (w - 20)
            p.setPen(QPen(QColor(col), 1, Qt.DashLine))
            p.drawLine(QPointF(x, 20), QPointF(x, h - 24))
            p.setPen(QColor(col)); p.drawText(QPointF(min(x + 3, w - 40), 30), lab)
        srt = sorted(totals)
        p.setPen(QColor(C_TEXT)); p.setFont(mono(9))
        p.drawText(QPointF(8, h - 6),
                   f"avg {sum(totals)/len(totals):5.2f} ms   p99 {srt[int(0.99*(len(totals)-1))]:5.2f} ms   "
                   f"worst {max(totals):5.2f} ms   hitches(>25ms) {self.canvas.hitches}")

class ProfilerPage(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.inject = defaultdict(float)
        v = QVBoxLayout(self)
        v.addWidget(page_header("Profiler",
            "Shipped games are tuned with exactly this view. The flame chart shows where each frame's milliseconds go; the histogram shows why the AVERAGE frame time can look fine while players still feel hitches — the p99 tail is the truth. Inject cost into a system, arm a GC spike, or enable periodic AI bursts and hunt the culprit."))
        h = QHBoxLayout()
        left = QWidget(); left.setFixedWidth(290)
        lv = QVBoxLayout(left); lv.setContentsMargins(0, 0, 0, 0)
        gb0 = QGroupBox("Capture"); b0 = QVBoxLayout(gb0)
        self.live_cb = QCheckBox("capture live"); self.live_cb.setChecked(True)
        b0.addWidget(self.live_cb)
        b0.addWidget(QLabel("GC spikes and AI bursts appear as one-off\nvertical walls — never in the average."))
        lv.addWidget(gb0)
        gb1 = QGroupBox("Inject cost"); b1 = QVBoxLayout(gb1)
        self.sys_combo = QComboBox()
        self.sys_combo.addItems([n for n, _, _ in PROF_ALL])
        b1.addWidget(self.sys_combo)
        self.inj_lbl = QLabel("0 ms added")
        s = QSlider(Qt.Horizontal); s.setRange(0, 120); s.setValue(0)
        s.valueChanged.connect(self._inj_changed)
        self.inj_slider = s
        b1.addWidget(s); b1.addWidget(self.inj_lbl)
        clear = QPushButton("✕ clear all injections"); clear.clicked.connect(self._inj_clear)
        b1.addWidget(clear)
        lv.addWidget(gb1)
        gb2 = QGroupBox("Events"); b2 = QVBoxLayout(gb2)
        gc = QPushButton("🗑 script GC spike (next frame)")
        gc.clicked.connect(lambda: setattr(self.canvas, "gc_armed", True))
        self.burst_cb = QCheckBox("periodic AI pathfinding bursts")
        b2.addWidget(gc); b2.addWidget(self.burst_cb)
        lv.addWidget(gb2)
        gb3 = QGroupBox("How to read it"); b3 = QVBoxLayout(gb3)
        for t in ("• block width = time, nesting = call depth",
                  "• a healthy frame is a flat plateau under budget",
                  "• one tall red wall per few seconds = hitch",
                  "• avg fine + p99 awful = stutter players report",
                  "• optimize the WIDEST block first"):
            l = QLabel(t); l.setObjectName("dim"); b3.addWidget(l)
        lv.addWidget(gb3)
        lv.addStretch(1)
        h.addWidget(left)
        right = QVBoxLayout()
        self.canvas = _ProfCanvas(self)
        self.hist = _ProfHist(self.canvas)
        right.addWidget(self.canvas, 1)
        right.addWidget(self.hist)
        h.addLayout(right, 1)
        v.addLayout(h)

    def _inj_changed(self, val):
        name = self.sys_combo.currentText()
        self.inject[name] = val / 10.0
        self.inj_lbl.setText(f"+{val/10.0:.1f} ms on {name}")

    def _inj_clear(self):
        self.inject.clear()
        self.inj_slider.setValue(0)
        self.inj_lbl.setText("0 ms added")

    def showEvent(self, e):
        self.canvas.start(); super().showEvent(e)

    def hideEvent(self, e):
        self.canvas.stop(); super().hideEvent(e)


# ============================================================ LOCALIZATION ==
def _pl(n):
    return 0 if n == 1 else (1 if 2 <= n <= 4 else 2)

def _ar(n):
    return {0: 0, 1: 1, 2: 2}.get(n, 3)

def _pseudo(s):
    s = s.translate(str.maketrans("aeiouAEIOU", "áéîóúÀÉÎÓÚ"))
    return f"[{s}{'!' * max(1, int(len(s) * 0.4))}]"

LOC_DATA = {
    "English": dict(rtl=False, exp=1.00,
        ui=dict(health="Health", play="Play", inv="Inventory", set="Settings", quest="QUEST LOG"),
        sent=lambda n: f"{n} coin collected" if n == 1 else f"{n} coins collected",
        form=lambda n: "one" if n == 1 else "other",
        note="<b>2 plural forms</b> (one, other). The boring baseline — every other language breaks your assumptions."),
    "German": dict(rtl=False, exp=1.35,
        ui=dict(health="Lebenspunkte", play="Spielen", inv="Inventar", set="Einstellungen", quest="AUFGABEN"),
        sent=lambda n: f"{n} Münze eingesammelt" if n == 1 else f"{n} Münzen eingesammelt",
        form=lambda n: "eins" if n == 1 else "andere",
        note="<b>2 forms</b> like English — but compound words run ~35% longer and overflow fixed-width buttons."),
    "Polish": dict(rtl=False, exp=1.18,
        ui=dict(health="Zdrowie", play="Graj", inv="Ekwipunek", set="Opcje", quest="ZADANIA"),
        sent=lambda n: f"Zebrano {n} " + ["monetę", "monety", "monet"][_pl(n)],
        form=lambda n: ["jeden (1)", "kilka (2-4)", "wiele (5+)"][_pl(n)],
        note="<b>3 plural forms</b>: 1 / 2-4 / 5+ — and a nasty 12-14 exception at higher counts."),
    "Japanese": dict(rtl=False, exp=0.72,
        ui=dict(health="体力", play="プレイ", inv="持ち物", set="設定", quest="クエスト"),
        sent=lambda n: f"コインを{n}枚拾った",
        form=lambda n: "唯一 (no plurals)",
        note="<b>1 form</b> — no plural inflection at all. Text is shorter; CJK fonts must ship with the game."),
    "Arabic": dict(rtl=True, exp=1.12,
        ui=dict(health="الصحة", play="العب", inv="المخزون", set="الإعدادات", quest="المهام"),
        sent=lambda n: ["لا عملات", "عملة واحدة", "عملتان", f"{n} عملات"][min(3, _ar(n))],
        form=lambda n: ["zero", "one", "two", "few", "many", "other"][_ar(n)],
        note="<b>6 plural forms</b> (zero/one/two/few/many/other) — and the whole UI mirrors <b>right-to-left</b>."),
}

class _LocCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setMinimumHeight(260)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        pg = self.page
        lang = LOC_DATA[pg.lang]
        tr = (lambda s: _pseudo(s)) if pg.pseudo else (lambda s: s)
        ui = {k: tr(v) for k, v in lang["ui"].items()}
        sent = tr(lang["sent"](pg.n))
        fm = QFontMetricsF(self.font())
        rtl = lang["rtl"]
        warns = []
        def mirror(x, bw):
            return w - 18 - bw - x if rtl else 18 + x
        hx = mirror(0, 150)
        p.setPen(QColor(C_TEXT)); p.setFont(self.font())
        p.drawText(QPointF(hx if not rtl else hx + 150 - fm.horizontalAdvance(ui["health"]), 30), ui["health"])
        p.setPen(QPen(QColor(C_BORDER), 1)); p.setBrush(QColor("#0c0d10"))
        p.drawRect(QRectF(hx, 38, 150, 12))
        p.setBrush(QColor(C_GREEN)); p.setPen(Qt.NoPen)
        bx = hx if not rtl else hx + 150 - 96
        p.drawRect(QRectF(bx, 39, 96, 10))
        qw = 250
        qx = (w - 18 - qw) if not rtl else 18
        p.setBrush(QColor("#14181d")); p.setPen(QPen(QColor(C_BORDER), 1))
        p.drawRect(QRectF(qx, 24, qw, 64))
        p.setPen(QColor(C_ACCENT)); p.setFont(mono(8))
        p.drawText(QPointF(qx + 10, 40), ui["quest"])
        p.setPen(QColor(C_TEXT)); p.setFont(self.font())
        if fm.horizontalAdvance(sent) > qw - 20:
            warns.append(f"'{sent[:24]}…' overflows the quest panel")
            p.setPen(QColor(C_RED))
        p.drawText(QRectF(qx + 10, 44, qw - 20, 40), Qt.TextWordWrap, sent)
        bw, bh_, gap = 96, 32, 10
        for i, key in enumerate(("play", "inv", "set")):
            x = mirror(i * (bw + gap), bw)
            y = h - 56
            tw = fm.horizontalAdvance(ui[key])
            p.setBrush(QColor("#243039")); p.setPen(QPen(QColor("#4a5568"), 1))
            p.drawRoundedRect(QRectF(x, y, bw, bh_), 6, 6)
            p.setPen(QColor(C_TEXT))
            p.drawText(QRectF(x, y, bw, bh_), (Qt.AlignRight if rtl else Qt.AlignCenter) | Qt.AlignVCenter, ui[key])
            if tw > bw - 12:
                p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(C_RED), 2))
                p.drawRoundedRect(QRectF(x - 3, y - 3, bw + 6, bh_ + 6), 7, 7)
                warns.append(f"'{ui[key]}' is {tw - (bw - 12):.0f}px too wide for its button")
        p.setFont(mono(9)); p.setPen(QColor(C_DIM))
        p.drawText(QPointF(18, h - 12),
                   f"{pg.lang}" + (" · RTL mirrored" if rtl else "") +
                   (" · pseudo-localized" if pg.pseudo else ""))
        if warns:
            p.setPen(QColor(C_RED)); p.setFont(mono(8))
            for i, wn in enumerate(warns[:3]):
                p.drawText(QPointF(18, h - 46 - i * 13), "⚠ " + wn)
        else:
            p.setPen(QColor(C_GREEN)); p.setFont(mono(8))
            p.drawText(QPointF(18, h - 30), "✓ no overflow at this size — try German or pseudo-loc")

class LocalizationPage(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.lang, self.pseudo, self.n = "English", False, 3
        v = QVBoxLayout(self)
        v.addWidget(page_header("Localization",
            "Text is data with opinions. Swap languages and watch a layout sized for English break: German overflows buttons, Arabic mirrors the whole UI and needs six plural forms, Japanese needs none. Pseudo-localization fakes all of this BEFORE translators are involved — the cheap way to find hardcoded strings and cramped layouts."))
        row = QHBoxLayout()
        row.addWidget(QLabel("language"))
        self.combo = QComboBox(); self.combo.addItems(list(LOC_DATA))
        self.combo.currentTextChanged.connect(self._change)
        row.addWidget(self.combo)
        self.pseudo_cb = QCheckBox("pseudo-localize  [!!áéíóú!!]")
        self.pseudo_cb.toggled.connect(lambda on: (setattr(self, "pseudo", on), self.canvas.update()))
        row.addSpacing(12); row.addWidget(self.pseudo_cb)
        row.addWidget(QLabel("coin count"))
        self.n_lbl = QLabel("3")
        ns = QSlider(Qt.Horizontal); ns.setRange(0, 12); ns.setValue(3); ns.setMaximumWidth(120)
        ns.valueChanged.connect(lambda val: (setattr(self, "n", val), self.n_lbl.setText(str(val)),
                                             self.canvas.update(), self._sync_side()))
        row.addWidget(ns); row.addWidget(self.n_lbl); row.addStretch(1)
        v.addLayout(row)
        h = QHBoxLayout()
        self.canvas = _LocCanvas(self)
        h.addWidget(self.canvas, 1)
        side = QWidget(); side.setFixedWidth(300)
        sv = QVBoxLayout(side); sv.setContentsMargins(0, 0, 0, 0)
        sv.addWidget(QLabel("<b>Language facts</b>"))
        self.side_lbl = QLabel(); self.side_lbl.setWordWrap(True)
        self.side_lbl.setTextFormat(Qt.RichText)
        sv.addWidget(self.side_lbl); sv.addStretch(1)
        h.addWidget(side)
        v.addLayout(h)
        self._sync_side()

    def _change(self, name):
        self.lang = name
        d = LOC_DATA[name]
        self.bus.emit("loc_language", lang=name, rtl=d["rtl"])
        self.canvas.update(); self._sync_side()

    def _sync_side(self):
        d = LOC_DATA[self.lang]
        rows = "".join(f"<tr><td><b>{c}</b></td><td>{d['form'](c)}</td>"
                       f"<td>{d['sent'](c)}</td></tr>" for c in range(6))
        self.side_lbl.setText(
            f"<span style='color:{C_ACCENT}; font-weight:700;'>{self.lang}</span>"
            f"<br>text length vs English: <b>{(d['exp']-1)*100:+.0f}%</b>"
            f"<br>direction: <b>{'right-to-left' if d['rtl'] else 'left-to-right'}</b>"
            f"<br><br>{d['note']}"
            f"<br><br><table cellpadding='2'>{rows}</table>"
            f"<br><span style='color:{C_DIM};'>selected count <b>{self.n}</b> → form "
            f"<b>{d['form'](self.n)}</b></span>")

    def showEvent(self, e): self.canvas.update(); super().showEvent(e)


# =========================================================== SAVE/LOAD LAB ==
MAGIC = b"ELSV"
ENT_KINDS = ["knight", "slime", "chest"]
KIND_COLORS = [C_ACCENT, C_GREEN, C_YELLOW]

@dataclass
class SEnt:
    id: int; kind: int; x: float; y: float; vx: float; vy: float; hp: float; gold: int

def serialize_world(ents, version):
    """ELSV binary format: magic | u8 version | u16 count | records | u16 checksum."""
    buf, annot = bytearray(), []
    buf += MAGIC;                                   annot.append((0, 4, "magic bytes 'ELSV'", "magic"))
    buf.append(version);                            annot.append((4, 5, f"schema version = {version}", "ver"))
    buf += _struct.pack("<H", len(ents));           annot.append((5, 7, f"entity count = {len(ents)}", "cnt"))
    for e in ents:
        s = len(buf)
        buf += _struct.pack("<H", e.id)
        buf.append(e.kind)
        buf += _struct.pack("<ff", e.x, e.y)
        buf += _struct.pack("<f", e.hp)
        if version >= 2:
            buf += _struct.pack("<H", e.gold)
        annot.append((s, len(buf), f"entity #{e.id} · {ENT_KINDS[e.kind]}", "ent"))
    cs = sum(buf) & 0xFFFF
    s = len(buf)
    buf += _struct.pack("<H", cs);                  annot.append((s, len(buf), f"checksum = 0x{cs:04X}", "chk"))
    return bytes(buf), annot

def deserialize_world(buf):
    """Returns (ents, error, migrated)."""
    if len(buf) < 7 or bytes(buf[:4]) != MAGIC:
        return None, "bad magic — not an ELSV save", False
    version, count = buf[4], _struct.unpack("<H", buf[5:7])[0]
    payload, stored = buf[:-2], _struct.unpack("<H", buf[-2:])[0]
    if sum(payload) & 0xFFFF != stored:
        return None, (f"checksum mismatch — stored 0x{stored:04X} ≠ computed "
                      f"0x{sum(payload) & 0xFFFF:04X} · file is corrupt"), False
    rec = 17 if version >= 2 else 15
    if len(payload) - 7 < count * rec:
        return None, "truncated entity table", False
    ents, migrated, off = [], False, 7
    for _ in range(count):
        eid, kind = _struct.unpack("<H", payload[off:off + 2])[0], payload[off + 2]
        x, y = _struct.unpack("<ff", payload[off + 3:off + 11])
        hp = _struct.unpack("<f", payload[off + 11:off + 15])[0]
        gold = _struct.unpack("<H", payload[off + 15:off + 17])[0] if version >= 2 else 0
        if version < 2: migrated = True
        ents.append(SEnt(eid, min(kind, 2), x, y, 0.0, 0.0, hp, gold))
        off += rec
    return ents, None, migrated

def world_hash(ents):
    return hash(tuple((e.id, round(e.x, 1), round(e.y, 1), round(e.hp, 1), e.gold) for e in ents)) & 0xFFFF

REGION_COLORS = {"magic": C_ACCENT, "ver": C_PURPLE, "cnt": C_ORANGE, "ent": C_GREEN, "chk": C_RED}

class ByteCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.buf, self.annot = b"", []
        self.cells = {}
        self.hover = None
        self.info = "save a world to inspect its bytes"
        self.setMinimumHeight(150)
        self.setMouseTracking(True)

    def set_buffer(self, buf, annot):
        self.buf, self.annot = buf, annot
        self.info = f"{len(buf)} bytes — hover a byte for its meaning"
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w = self.width()
        cs, cols = 26, max(1, (w - 16) // 26)
        self.cells.clear()
        f = mono(8)
        for i, b in enumerate(self.buf):
            r, c = divmod(i, cols)
            x, y = 8 + c * cs, 26 + r * cs
            reg = next((a for a in self.annot if a[0] <= i < a[1]), None)
            col = QColor(REGION_COLORS[reg[3]]) if reg else QColor("#3a3d45")
            hot = self.hover == i
            p.setBrush(QColor(col).lighter(150) if hot else QColor(20, 24, 30))
            p.setPen(QPen(col, 2 if hot else 1))
            p.drawRect(QRectF(x, y, cs - 3, cs - 3))
            p.setPen(QColor(C_TEXT)); p.setFont(f)
            p.drawText(QRectF(x, y, cs - 3, cs - 3), Qt.AlignCenter, f"{b:02X}")
            self.cells[(x, y)] = i
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(8, 16), "hex view — one cell = one byte")
        p.setPen(QColor(C_YELLOW)); p.setFont(mono(9))
        p.drawText(QPointF(8, self.height() - 8), self.info)
        lx = w - 260
        for key, label in (("magic", "magic"), ("ver", "version"), ("cnt", "count"),
                           ("ent", "entities"), ("chk", "checksum")):
            p.setBrush(QColor(REGION_COLORS[key])); p.setPen(Qt.NoPen)
            p.drawRect(QRectF(lx, 8, 8, 8))
            p.setPen(QColor(C_DIM)); p.setFont(mono(7))
            p.drawText(QPointF(lx + 12, 16), label)
            lx += 12 + p.fontMetrics().horizontalAdvance(label) + 14

    def mouseMoveEvent(self, e):
        hit = next((i for (x, y), i in self.cells.items()
                    if x <= e.position().x() < x + 23 and y <= e.position().y() < y + 23), None)
        if hit is not None:
            reg = next((a for a in self.annot if a[0] <= hit < a[1]), None)
            self.info = f"offset 0x{hit:02X} = 0x{self.buf[hit]:02X}  ·  {reg[2] if reg else 'unknown'}"
        self.hover = hit
        self.update()

    def leaveEvent(self, e):
        self.hover = None; self.update()

class WorldMap(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setFixedHeight(120)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width() - 16, self.height() - 16
        p.setPen(QPen(QColor(C_BORDER), 1)); p.setBrush(QColor("#0c0d10"))
        p.drawRect(8, 8, w, h)
        for ent in self.page.ents:
            x, y = 8 + ent.x / 100 * w, 8 + ent.y / 100 * h
            p.setBrush(QColor(KIND_COLORS[ent.kind])); p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(x, y), 5, 5)
            p.setPen(QColor(C_DIM)); p.setFont(mono(7))
            p.drawText(QPointF(x + 6, y + 3), f"#{ent.id}")
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(10, self.height() - 1), "live world — blue knight · green slime · yellow chest")

class SerializationPage(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.ents, self.t, self.tick_n = [], 0.0, 0
        self.buf, self.annot = b"", []
        self.saved_hash, self.saved_t = None, 0.0
        self.next_id = 1
        self.sim_on = True
        v = QVBoxLayout(self)
        v.addWidget(page_header("Save / Load Lab",
            "Saving is translating live state into bytes — and trusting them again later. Save the wandering world, inspect the byte layout (hover!), load it back and verify the round-trip hash. Save as legacy v1 to trigger a schema migration (the v2 'gold' field is absent → defaulted on load). Corrupt a byte and watch the checksum catch it."))
        row = QHBoxLayout()
        left = QWidget(); left.setFixedWidth(300)
        lv = QVBoxLayout(left); lv.setContentsMargins(0, 0, 0, 0)
        gb1 = QGroupBox("Operations"); b1 = QGridLayout(gb1)
        b2 = QPushButton("💾 Save (v2)"); b2.clicked.connect(lambda: self._save(2))
        b1_ = QPushButton("💾 Save as legacy v1")
        b1_.setToolTip("Old schema — no gold field. Loading it triggers migration.")
        b1_.clicked.connect(lambda: self._save(1))
        ld = QPushButton("📂 Load"); ld.clicked.connect(self._load)
        co = QPushButton("☠ Corrupt a byte"); co.clicked.connect(self._corrupt)
        pa = QPushButton("⏸ pause sim"); pa.setCheckable(True); pa.setChecked(True)
        pa.toggled.connect(lambda on: (pa.setText("⏸ pause sim" if on else "▶ resume sim"),
                                       setattr(self, "sim_on", on)))
        rs = QPushButton("↻ new world"); rs.clicked.connect(self._new_world)
        b1.addWidget(b2, 0, 0); b1.addWidget(ld, 0, 1)
        b1.addWidget(b1_, 1, 0); b1.addWidget(co, 1, 1)
        b1.addWidget(pa, 2, 0); b1.addWidget(rs, 2, 1)
        lv.addWidget(gb1)
        gb2 = QGroupBox("Integrity"); b2v = QVBoxLayout(gb2)
        self.lbl_live = QLabel("live hash   —")
        self.lbl_saved = QLabel("saved hash  —")
        for l in (self.lbl_live, self.lbl_saved): l.setFont(mono(10))
        b2v.addWidget(self.lbl_live); b2v.addWidget(self.lbl_saved)
        lv.addWidget(gb2)
        lv.addWidget(WorldMap(self))
        lv.addStretch(1)
        row.addWidget(left)

        right = QVBoxLayout()
        self.byte_view = ByteCanvas()
        self.text_view = QLabel(); self.text_view.setFont(mono(9))
        self.text_view.setTextFormat(Qt.RichText)
        self.text_view.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.text_view.setStyleSheet("background:#101114; border:1px solid #2f3238; border-radius:6px; padding:8px;")
        self.text_view.hide()
        self.view_btn = QPushButton("🔀 switch to text view")
        self.view_btn.clicked.connect(self._toggle_view)
        right.addWidget(self.view_btn)
        right.addWidget(self.byte_view, 1)
        right.addWidget(self.text_view, 1)
        row.addLayout(right, 1)
        v.addLayout(row)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["id", "kind", "x", "y", "hp", "gold", "vx,vy (NOT saved)"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setMaximumHeight(150)
        v.addWidget(self.table)

        self.log = QPlainTextEdit(); self.log.setReadOnly(True)
        self.log.setFont(mono(9)); self.log.setMaximumBlockCount(200)
        self.log.setMinimumHeight(90)
        v.addWidget(self.log)

        st = QHBoxLayout(); st.addWidget(QLabel("sim time"))
        self.t_lbl = QLabel("0.0 s"); self.t_lbl.setFont(mono(10)); self.t_lbl.setStyleSheet(f"color:{C_ACCENT};")
        st.addWidget(self.t_lbl); st.addStretch(1)
        v.addLayout(st)

        self.timer = QTimer(self); self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)
        self._new_world(first=True)

    def _new_world(self, first=False):
        self.ents, self.t, self.next_id = [], 0.0, 1
        for kind, n in ((0, 1), (1, 3), (2, 2)):
            for _ in range(n):
                ang = random.uniform(0, 2 * math.pi)
                self.ents.append(SEnt(self.next_id, kind,
                                      random.uniform(8, 92), random.uniform(8, 92),
                                      math.cos(ang) * 6, math.sin(ang) * 6,
                                      100.0 if kind != 1 else random.uniform(40, 90),
                                      random.randint(0, 30) if kind == 2 else 0))
                self.next_id += 1
        self._log("—" * 46)
        self._log(f"new world: {len(self.ents)} entities (fresh state)")
        if not first: self._refresh_table()

    def _log(self, s):
        self.log.appendPlainText(f"[{self.t:6.1f}] {s}")

    def _tick(self):
        self.tick_n += 1
        if not self.sim_on: return
        dt = 0.033
        self.t += dt
        for e in self.ents:
            e.x += e.vx * dt; e.y += e.vy * dt
            if e.x < 4 or e.x > 96: e.vx = -e.vx
            if e.y < 4 or e.y > 96: e.vy = -e.vy
            if e.kind == 1: e.hp = max(0.0, e.hp - 0.4 * dt)
            if e.kind == 0 and random.random() < 0.008: e.gold += 1
        self.t_lbl.setText(f"{self.t:.1f} s")
        if self.tick_n % 6 == 0:
            self._refresh_table()
            lh = world_hash(self.ents)
            self.lbl_live.setText(f"live hash   0x{lh:04X}")
            self.lbl_saved.setText("saved hash  " +
                (f"0x{self.saved_hash:04X} {'✓' if lh == self.saved_hash else ''}" if self.saved_hash is not None else "—"))
            self.lbl_live.setStyleSheet(f"color:{C_GREEN if lh == self.saved_hash else C_ACCENT};")

    def _refresh_table(self):
        self.table.setRowCount(0)
        for r, e in enumerate(self.ents):
            vals = [f"#{e.id}", ENT_KINDS[e.kind], f"{e.x:.1f}", f"{e.y:.1f}",
                    f"{e.hp:.1f}", str(e.gold), f"{e.vx:.0f},{e.vy:.0f}"]
            self.table.insertRow(r)
            for c, txt in enumerate(vals):
                it = QTableWidgetItem(txt)
                if c == 1: it.setForeground(QColor(KIND_COLORS[e.kind]))
                if c == 6: it.setForeground(QColor(C_DIM))
                self.table.setItem(r, c, it)

    def _save(self, version):
        self.buf, self.annot = serialize_world(self.ents, version)
        self.saved_hash, self.saved_t = world_hash(self.ents), self.t
        self.byte_view.set_buffer(self.buf, self.annot)
        if not self.text_view.isHidden(): self._fill_text_view()
        cs = _struct.unpack("<H", self.buf[-2:])[0]
        self._log(f"saved {len(self.buf)} bytes · schema v{version} · {len(self.ents)} entities · checksum 0x{cs:04X}")
        if version == 1:
            self._log("note: v1 has no 'gold' field — this file can't remember gold")

    def _corrupt(self):
        if not self.buf:
            self._log("nothing saved yet — save first, then corrupt"); return
        off = random.randint(7, len(self.buf) - 3)
        old = self.buf[off]
        self.buf = self.buf[:off] + bytes([old ^ 0xA5]) + self.buf[off + 1:]
        self.byte_view.set_buffer(self.buf, self.annot)
        self._log(f"☠ byte 0x{off:02X} corrupted (0x{old:02X} → 0x{old ^ 0xA5:02X}) — payload changed, checksum didn't")

    def _load(self):
        if not self.buf:
            self._log("no save file — press Save first"); return
        ents, err, migrated = deserialize_world(self.buf)
        if err:
            self._log(f"✗ LOAD FAILED: {err}")
            self.bus.emit("world_load_failed", error=err[:40])
            return
        gap = self.t - self.saved_t
        self.ents = ents
        self._log(f"✓ loaded {len(ents)} entities from schema v{self.buf[4]} — checksum OK")
        if migrated:
            self._log(f"  ↳ migration: v1 → v2 · 'gold' absent in file, defaulted to 0 for {len(ents)} entities")
            self.bus.emit("world_migrated", count=len(ents))
        self._log("  ↳ velocities reset to 0 (they were never saved — ephemeral vs persistent state)")
        self._log(f"  ↳ time travel: discarded {gap:.1f} s of live simulation since the save")
        self._log("  ↳ round-trip verified: loaded hash == saved hash ✓")
        self.bus.emit("checkpoint_made", bytes_len=len(self.buf))

    def _toggle_view(self):
        to_text = self.byte_view.isVisible()
        self.byte_view.setVisible(not to_text)
        self.text_view.setVisible(to_text)
        self.view_btn.setText("🔀 switch to hex view" if to_text else "🔀 switch to text view")
        if to_text: self._fill_text_view()

    def _fill_text_view(self):
        if not self.buf:
            self.text_view.setText("<span style='color:#9aa0a6;'>nothing saved yet</span>"); return
        version = self.buf[4]
        ents, err, migrated = deserialize_world(self.buf)
        rows = "".join(
            f"    {{ <span style='color:{C_ACCENT};'>id</span>: {e.id}, "
            f"<span style='color:{C_GREEN};'>kind</span>: \"{ENT_KINDS[e.kind]}\", "
            f"<span style='color:{C_ORANGE};'>pos</span>: [{e.x:.1f}, {e.y:.1f}], "
            f"<span style='color:{C_PINK};'>hp</span>: {e.hp:.1f}, "
            f"<span style='color:{C_YELLOW};'>gold</span>: {e.gold}"
            f"{'  <span style=\"color:#9aa0a6;\"># added by migration</span>' if migrated else ''} }},<br>"
            for e in (ents or []))
        cs = _struct.unpack("<H", self.buf[-2:])[0]
        self.text_view.setText(
            f"<span style='color:#9aa0a6;'>// same bytes, human view — trade size for readability</span><br>"
            f"<span style='color:{C_ACCENT};'>ELSV</span>  <span style='color:{C_PURPLE};'>version: {version}</span><br>"
            f"entities: [<br>{rows}]<br>"
            f"<span style='color:{C_RED};'>checksum: 0x{cs:04X}</span>"
            + ("<br><span style='color:#ef5350;'>✗ failed validation: " + err + "</span>" if err else ""))

    def showEvent(self, e):
        if not self.timer.isActive(): self.timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop(); super().hideEvent(e)


# ========================================================= DETERMINISM LAB ==
DET_W, DET_H = 640.0, 400.0
KEY_R, KEY_L, KEY_D, KEY_U = 1, 2, 4, 8

class _DetWorld:
    """Zero hidden state: seeded init + pure step(state, dt, inputs)."""
    def __init__(self, seed):
        rng = random.Random(seed)
        self.hero = [DET_W / 2, DET_H / 2, 0.0, 0.0]
        self.balls = [[rng.uniform(40, DET_W - 40), rng.uniform(40, DET_H - 40),
                       rng.uniform(-90, 90), rng.uniform(-90, 90)] for _ in range(8)]

    def step(self, dt, keys):
        h = self.hero
        h[2] += ((keys & KEY_R) - (keys & KEY_L)) * 360 * dt
        h[3] += ((keys & KEY_D) - (keys & KEY_U)) * 360 * dt
        h[2] *= 0.985; h[3] *= 0.985
        h[2] = max(-240.0, min(240.0, h[2])); h[3] = max(-240.0, min(240.0, h[3]))
        h[0] += h[2] * dt; h[1] += h[3] * dt
        if h[0] < 10:  h[0] = 10;  h[2] = abs(h[2])
        if h[0] > DET_W - 10: h[0] = DET_W - 10; h[2] = -abs(h[2])
        if h[1] < 10:  h[1] = 10;  h[3] = abs(h[3])
        if h[1] > DET_H - 10: h[1] = DET_H - 10; h[3] = -abs(h[3])
        for b in self.balls:
            b[0] += b[2] * dt; b[1] += b[3] * dt
            if b[0] < 9:  b[0] = 9;  b[2] = abs(b[2])
            if b[0] > DET_W - 9: b[0] = DET_W - 9; b[2] = -abs(b[2])
            if b[1] < 9:  b[1] = 9;  b[3] = abs(b[3])
            if b[1] > DET_H - 9: b[1] = DET_H - 9; b[3] = -abs(b[3])

    def snapshot(self):
        return (round(self.hero[0], 2), round(self.hero[1], 2),
                tuple((round(b[0], 2), round(b[1], 2)) for b in self.balls))

def det_hash(snap):
    return zlib.crc32(repr(snap).encode()) & 0xFFFF

class _DetTimeline(QWidget):
    def __init__(self):
        super().__init__()
        self.marks = deque(maxlen=1600)
        self.setFixedHeight(46)

    def add(self, ok): self.marks.append(ok); self.update()
    def clear(self): self.marks.clear(); self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(C_PANEL))
        w, h = self.width(), self.height()
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(8, 12),
                   f"per-frame hash check — green = match, red = DIVERGED ({len(self.marks)} frames)")
        n = len(self.marks)
        if not n: return
        bw = w / self.marks.maxlen
        x0 = w - n * bw
        p.setPen(Qt.NoPen)
        for i, ok in enumerate(self.marks):
            p.fillRect(QRectF(x0 + i * bw, 20, max(1.0, bw - 0.5), h - 26),
                       QColor(C_GREEN if ok else C_RED))

class _DetCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.keys = 0
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumHeight(300)

    def keyPressEvent(self, e):
        if e.isAutoRepeat(): e.accept(); return
        m = {Qt.Key_Right: KEY_R, Qt.Key_Left: KEY_L, Qt.Key_Down: KEY_D, Qt.Key_Up: KEY_U}
        if e.key() in m:
            self.keys |= m[e.key()]; e.accept(); self.setFocus()
        else: super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        m = {Qt.Key_Right: KEY_R, Qt.Key_Left: KEY_L, Qt.Key_Down: KEY_D, Qt.Key_Up: KEY_U}
        self.keys &= ~m.get(e.key(), 0); e.accept()

    def mousePressEvent(self, e): self.setFocus()

    def paintEvent(self, ev):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#0c0d10"))
        w, h = self.width(), self.height()
        s = min(w / DET_W, h / DET_H)
        ox, oy = (w - DET_W * s) / 2, (h - DET_H * s) / 2
        p.setPen(QPen(QColor(C_BORDER), 1)); p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(ox, oy, DET_W * s, DET_H * s))
        pg = self.page
        rec = pg.rec_snaps if pg.mode == "replay" else None
        if rec is not None and pg.frame < len(rec):
            hs, hb = rec[pg.frame][0], rec[pg.frame][1]
            for i, (gx, gy) in enumerate(hb):
                b = pg.world.balls[i]
                if abs(gx - b[0]) + abs(gy - b[1]) > 0.5:
                    p.setBrush(Qt.NoBrush)
                    p.setPen(QPen(QColor(255, 255, 255, 90), 1, Qt.DashLine))
                    p.drawEllipse(QPointF(ox + gx * s, oy + gy * s), 9 * s, 9 * s)
            if abs(hs[0] - pg.world.hero[0]) + abs(hs[1] - pg.world.hero[1]) > 0.5:
                p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(C_ACCENT, 100), 1, Qt.DashLine))
                p.drawRect(QRectF(ox + hs[0] * s - 9 * s, oy + hs[1] * s - 9 * s, 18 * s, 18 * s))
        p.setPen(Qt.NoPen)
        for b in pg.world.balls:
            p.setBrush(QColor(C_GREEN)); p.setOpacity(0.85)
            p.drawEllipse(QPointF(ox + b[0] * s, oy + b[1] * s), 9 * s, 9 * s)
        p.setOpacity(1.0)
        hx, hy = pg.world.hero
        p.setBrush(QColor(C_ACCENT))
        p.drawRect(QRectF(ox + hx * s - 9 * s, oy + hy * s - 9 * s, 18 * s, 18 * s))
        p.setPen(QColor("white")); p.setFont(mono(7))
        p.drawText(QPointF(ox + hx * s - 4, oy + hy * s + 3), "☺")
        p.setFont(mono(9)); y = 18
        for ln in pg.hud:
            p.setPen(QColor(ln[1])); p.drawText(QPointF(12, y), ln[0]); y += 15
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(12, self.height() - 8),
                   "click here, then drive with ARROW KEYS · dashed ghosts = the original run — when ghosts separate, that IS desync")

class DeterminismPage(QWidget):
    DT = 1.0 / 60.0
    MAX_FRAMES = 1800

    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.seed = 1337
        self.world = _DetWorld(self.seed)
        self.mode = "stopped"
        self.frame = 0
        self.rec_inputs, self.rec_snaps, self.rec_hashes = {}, [], []
        self.arm_diverge = False
        self.desync_frame = None
        self.hud = []
        v = QVBoxLayout(self)
        v.addWidget(page_header("Determinism & Replays",
            "If step(state, dt, inputs) is pure — seeded init, fixed timestep, no hidden randomness — then the SAME inputs MUST produce the SAME world, forever. That's replays, lockstep netcode and deterministic tests. Record a run (drive with arrows), replay it: every frame's state hash must match. Then tick the divergence injector — one 0.01 nudge to one velocity — and watch chaos amplify a rounding error into a totally different world. The dashed ghosts are the original run."))
        row = QHBoxLayout()
        self.rec_b = QPushButton("⏺ Record"); self.rec_b.clicked.connect(self._record)
        self.stop_b = QPushButton("⏹ Stop"); self.stop_b.clicked.connect(self._stop)
        self.rep_b = QPushButton("▶ Replay"); self.rep_b.setEnabled(False); self.rep_b.clicked.connect(self._replay)
        self.seed_b = QPushButton("🎲 new seed"); self.seed_b.clicked.connect(self._new_seed)
        self.div_cb = QCheckBox("☠ inject divergence mid-replay (+0.01 to one vx)")
        for b in (self.rec_b, self.stop_b, self.rep_b, self.seed_b): row.addWidget(b)
        row.addSpacing(10); row.addWidget(self.div_cb); row.addStretch(1)
        v.addLayout(row)
        h = QHBoxLayout()
        left = QWidget(); left.setFixedWidth(290)
        lv = QVBoxLayout(left); lv.setContentsMargins(0, 0, 0, 0)
        gb = QGroupBox("The determinism contract"); bv = QVBoxLayout(gb)
        for t in ("• seed ALL randomness",
                  "• fixed timestep — never variable dt",
                  "• no dict-order iteration in simulation",
                  "• no unsynchronized threads touching state",
                  "• same binary, same math library, same result",
                  "• inputs are DATA: (frame, keys) pairs",
                  "",
                  "Break any one line and a 0.001 difference",
                  "compounds — the feared 'replay desync'"):
            l = QLabel(t); l.setObjectName("dim"); bv.addWidget(l)
        lv.addWidget(gb)
        gb2 = QGroupBox("Status"); b2 = QVBoxLayout(gb2)
        self.st_mode = QLabel("mode: stopped"); self.st_mode.setFont(mono(10))
        self.st_frame = QLabel("frame 0 / 0"); self.st_frame.setFont(mono(10))
        self.st_hash = QLabel("hash —"); self.st_hash.setFont(mono(10))
        self.st_verdict = QLabel(""); self.st_verdict.setFont(mono(10)); self.st_verdict.setWordWrap(True)
        for l in (self.st_mode, self.st_frame, self.st_hash, self.st_verdict): b2.addWidget(l)
        lv.addWidget(gb2)
        lv.addStretch(1)
        h.addWidget(left)
        right = QVBoxLayout()
        self.canvas = _DetCanvas(self)
        self.timeline = _DetTimeline()
        right.addWidget(self.canvas, 1)
        right.addWidget(self.timeline)
        h.addLayout(right, 1)
        v.addLayout(h)
        self.timer = QTimer(self); self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)
        self._sync_hud("press ⏺ Record, click the arena, drive with arrows")

    def _new_seed(self):
        self.seed = random.randint(1, 99999)
        self._stop(); self.world = _DetWorld(self.seed); self.canvas.update()
        self._sync_hud(f"seed {self.seed} — record a fresh run")

    def _record(self):
        self.mode = "recording"; self.frame = 0
        self.world = _DetWorld(self.seed)
        self.rec_inputs, self.rec_snaps, self.rec_hashes = {}, [], []
        self.desync_frame = None; self.timeline.clear()
        self.rep_b.setEnabled(False)
        self.canvas.setFocus()

    def _stop(self):
        if self.mode == "recording" and len(self.rec_snaps) > 10:
            self.rep_b.setEnabled(True)
        self.mode = "stopped"
        self.canvas.update()

    def _replay(self):
        if not self.rec_snaps: return
        self.mode = "replay"; self.frame = 0
        self.world = _DetWorld(self.seed)
        self.desync_frame = None; self.timeline.clear()
        self.canvas.setFocus()

    def _sync_hud(self, verdict="", verdict_color=C_DIM):
        self.hud = [(f"mode: {self.mode}   ·   seed {self.seed}", C_TEXT),
                    (f"frame {self.frame}/{len(self.rec_snaps) if self.mode == 'replay' else '…'}", C_TEXT),
                    (f"state hash 0x{det_hash(self.world.snapshot()):04X}", C_ACCENT)]
        if verdict: self.hud.append((verdict, verdict_color))

    def _tick(self):
        if self.mode == "stopped":
            self.canvas.update(); return
        dt = self.DT
        if self.mode == "recording":
            keys = self.canvas.keys
            self.rec_inputs[self.frame] = keys
            snap = self.world.snapshot()
            self.rec_snaps.append(snap); self.rec_hashes.append(det_hash(snap))
            self.world.step(dt, keys)
            self.timeline.add(True)
            self.frame += 1
            self._sync_hud("recording… drive with arrows", C_YELLOW)
            if self.frame >= self.MAX_FRAMES:
                self._stop(); self.rep_b.setEnabled(True)
        else:
            keys = self.rec_inputs.get(self.frame, 0)
            if self.arm_diverge and self.frame == int(len(self.rec_snaps) * 0.55):
                self.world.balls[3][2] += 0.01
            self.world.step(dt, keys)
            ok = self.frame < len(self.rec_hashes) and \
                 det_hash(self.world.snapshot()) == self.rec_hashes[self.frame]
            self.timeline.add(ok)
            if not ok and self.desync_frame is None:
                self.desync_frame = self.frame
                self.bus.emit("replay_desync", frame=self.frame)
            self.frame += 1
            if self.desync_frame is not None:
                self._sync_hud(f"✗ DESYNC at frame {self.desync_frame} — one float, worlds apart", C_RED)
            else:
                self._sync_hud("replaying… hashes matching ✓", C_GREEN)
            if self.frame >= len(self.rec_snaps) - 1:
                self.mode = "stopped"
                if self.desync_frame is None:
                    self.bus.emit("replay_verified", frames=len(self.rec_snaps))
                    self._sync_hud("✓ full replay verified — bit-perfect", C_GREEN)
        self.st_mode.setText(f"mode: {self.mode}")
        self.st_frame.setText(f"frame {self.frame} / {len(self.rec_snaps)}")
        self.st_hash.setText(f"hash 0x{det_hash(self.world.snapshot()):04X}")
        self.st_verdict.setText(self.hud[-1][0])
        self.st_verdict.setStyleSheet(f"color:{self.hud[-1][1]};")
        self.canvas.update()

    def showEvent(self, e):
        if not self.timer.isActive(): self.timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop(); super().hideEvent(e)


# =========================================================== MULTIPLAYER LAB =
NET_W, NET_H = 120.0, 50.0
NET_PSPEED, NET_BSPEED = 11.0, 6.0
NET_INPUT_MS, NET_SNAP_MS = 60.0, 45.0

def _nclamp(p):
    return (min(NET_W - 1.5, max(1.5, p[0])), min(NET_H - 1.5, max(1.5, p[1])))

def _nmove(p, v, dt):
    return _nclamp((p[0] + v[0] * dt, p[1] + v[1] * dt))

class _NetCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.keys = set()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumHeight(400)

    def keyPressEvent(self, e):
        if not e.isAutoRepeat() and e.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            self.keys.add(e.key()); e.accept(); self.setFocus()
        else: super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        self.keys.discard(e.key()); e.accept()

    def mousePressEvent(self, e): self.setFocus()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        pg = self.page
        pred = pg.pred_cb.isChecked()
        CR = QRectF(10, 8, w - 20, h * 0.56)
        SR = QRectF(10, h * 0.60, w * 0.58, h * 0.30)
        GR = QRectF(SR.right() + 10, h * 0.60, w - SR.right() - 30, h * 0.30)
        def mapr(r):
            s = min(r.width() / NET_W, r.height() / NET_H)
            return s, QPointF(r.left() + (r.width() - NET_W * s) / 2,
                              r.top() + (r.height() - NET_H * s) / 2)
        def world_bg(r, title, sub):
            p.setPen(QPen(QColor(C_BORDER), 1)); p.setBrush(QColor("#0c0d10"))
            p.drawRoundedRect(r, 8, 8)
            s, o = mapr(r)
            p.save(); p.setClipRect(r)
            p.setPen(QPen(QColor("#171a1f"), 1))
            for gx in range(0, int(NET_W) + 1, 10):
                p.drawLine(QPointF(o.x() + gx * s, r.top()), QPointF(o.x() + gx * s, r.bottom()))
            for gy in range(0, int(NET_H) + 1, 10):
                p.drawLine(QPointF(r.left(), o.y() + gy * s), QPointF(r.right(), o.y() + gy * s))
            p.setPen(QColor(C_DIM)); p.setFont(mono(8))
            p.drawText(QPointF(r.left() + 8, r.top() + 14), title)
            if sub: p.drawText(QPointF(r.left() + 8, r.top() + 26), sub)
            p.restore()
            return s, o
        def ship(pos, s, o, color, ghost=False, tri=False):
            cx, cy = o.x() + pos[0] * s, o.y() + pos[1] * s
            p.setBrush(Qt.NoBrush if ghost else QColor(color))
            p.setPen(QPen(QColor(color), 1.5, Qt.DashLine if ghost else Qt.SolidLine))
            if tri:
                p.drawPolygon(QPolygonF([QPointF(cx, cy - 7 * s), QPointF(cx - 6 * s, cy + 5 * s),
                                         QPointF(cx + 6 * s, cy + 5 * s)]))
            else:
                p.drawRoundedRect(QRectF(cx - 2.2 * s, cy - 2.2 * s, 4.4 * s, 4.4 * s), 2, 2)
        s, o = world_bg(CR, "YOUR CLIENT — what you see & feel",
                        "prediction ON: you move instantly, server snaps you back when it disagrees" if pred
                        else "prediction OFF: you only move when snapshots arrive (1996 feel)")
        now = pg.now
        for i, (x, y, alive, tat) in enumerate(pg.coin_client):
            cx, cy = o.x() + x * s, o.y() + y * s
            if alive:
                pulse = 1.0 + 0.15 * math.sin(now / 300 + i)
                p.setBrush(QColor(C_YELLOW)); p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(cx, cy), 1.4 * s * pulse, 1.4 * s * pulse)
            elif now - tat < 350:
                k = (now - tat) / 350
                p.setBrush(Qt.NoBrush); p.setPen(QPen(_qc(C_YELLOW, int(200 * (1 - k))), 2))
                p.drawEllipse(QPointF(cx, cy), (1.4 + k * 3) * s, (1.4 + k * 3) * s)
        bs = list(pg.bot_snaps)
        if bs:
            (t1, p1), (t2, p2) = bs[-2] if len(bs) > 1 else (bs[0], bs[0])
            k = max(0.0, min(1.3, (now - t2) / max(1.0, t2 - t1)))
            bpos = (p1[0] + (p2[0] - p1[0]) * k, p1[1] + (p2[1] - p1[1]) * k)
            ship(bpos, s, o, C_ORANGE, tri=True)
        sp = pg.last_snap_p
        if pred and sp and math.hypot(sp[0] - pg.c_pos[0], sp[1] - pg.c_pos[1]) > 0.25:
            p.setPen(QPen(_qc("#888888", 130), 1))
            p.drawLine(QPointF(o.x() + sp[0] * s, o.y() + sp[1] * s),
                       QPointF(o.x() + pg.c_pos[0] * s, o.y() + pg.c_pos[1] * s))
            ship(sp, s, o, "#888888", ghost=True)
        ship(pg.c_pos, s, o, C_ACCENT)
        p.setFont(mono(9)); y = 44
        for ln in pg.hud:
            p.setPen(QColor(ln[1])); p.drawText(QPointF(18, y), ln[0]); y += 15
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(18, CR.bottom() - 8),
                   "click here, drive with ARROW KEYS · the bot shoves you — only the SERVER decides shoves, coins and positions")
        s2, o2 = world_bg(SR, f"SERVER TRUTH — tick {pg.srv_tick_n} (~22 Hz)",
                          f"queue: {len(pg.inflight)} packets in flight")
        for (x, y, alive, _t) in pg.coins:
            if alive:
                p.setBrush(QColor(C_YELLOW)); p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(o2.x() + x * s2, o2.y() + y * s2), 1.4 * s2, 1.4 * s2)
        ship(pg.srv_b, s2, o2, C_ORANGE, tri=True)
        ship(pg.srv_p, s2, o2, C_ACCENT)
        p.setPen(QPen(QColor(C_BORDER), 1)); p.setBrush(QColor("#0c0d10"))
        p.drawRoundedRect(GR, 8, 8)
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(GR.left() + 8, GR.top() + 14),
                   "prediction error per snapshot (units) — spikes = corrections")
        base = GR.bottom() - 12
        if len(pg.err_log) > 1:
            span = 140.0
            pts = [QPointF(GR.right() - (now - t) / span * (GR.width() - 20),
                           base - min(3.0, err) / 3.0 * (GR.height() - 34))
                   for (t, err) in pg.err_log if now - t <= span]
            if len(pts) > 1:
                p.setPen(QPen(QColor(C_GREEN), 1.5)); p.drawPolyline(QPolygonF(pts))
        p.setPen(QPen(_qc(C_RED, 120), 1, Qt.DashLine))
        ey = base - 1.2 / 3.0 * (GR.height() - 34)
        p.drawLine(QPointF(GR.left() + 6, ey), QPointF(GR.right() - 6, ey))
        p.setPen(QColor(C_RED)); p.setFont(mono(7))
        p.drawText(QPointF(GR.left() + 8, ey - 3), "1.2 — rubber-band territory")

class NetplayPage(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.now = 0.0
        self.srv_p, self.srv_b = (20.0, 25.0), (100.0, 25.0)
        self.srv_cmd, self.srv_last_seq, self.srv_tick_n, self.srv_acc = (0.0, 0.0), 0, 0, 0.0
        base = [(15, 10), (60, 8), (105, 42), (30, 44), (90, 15)]
        self.coins = [[x, y, True, 0.0] for x, y in base]
        self.coin_client = [[x, y, True, 0.0] for x, y in base]
        self.coins_collected = 0
        self.inflight = []
        self.seq, self.input_acc = 0, 0.0
        self.cmds, self.hist = {}, deque()
        self.c_pos = (20.0, 25.0)
        self.bot_snaps, self.snaps_received = deque(maxlen=2), 0
        self.err_log, self.corrections, self.last_err = deque(maxlen=240), 0, 0.0
        self.last_snap_p = None
        self.lag_secs, self._lag_emitted, self._corr_t = 0.0, False, -1e9
        self.hud = []
        v = QVBoxLayout(self)
        v.addWidget(page_header("Multiplayer Lab — prediction & reconciliation",
            "The server is the ONLY authority: it simulates you and the bot at ~22 Hz from your input packets. With prediction ON, your client applies inputs instantly and — when an old snapshot arrives — rewinds to the server's answer and replays the few inputs it hasn't acknowledged. Small divergence = invisible; the bot's SHOVE is decided server-side, so you get visibly rubber-banded. Toggle prediction OFF to feel raw snapshot movement."))
        row = QHBoxLayout()
        row.addWidget(QLabel("latency"))
        self.lat_s = QSlider(Qt.Horizontal); self.lat_s.setRange(20, 350); self.lat_s.setValue(140)
        self.lat_s.setMaximumWidth(110); row.addWidget(self.lat_s)
        row.addWidget(QLabel("jitter"))
        self.jit_s = QSlider(Qt.Horizontal); self.jit_s.setRange(0, 100); self.jit_s.setValue(25)
        self.jit_s.setMaximumWidth(100); row.addWidget(self.jit_s)
        row.addWidget(QLabel("loss %"))
        self.loss_s = QSlider(Qt.Horizontal); self.loss_s.setRange(0, 35); self.loss_s.setValue(4)
        self.loss_s.setMaximumWidth(90); row.addWidget(self.loss_s)
        self.pred_cb = QCheckBox("client prediction"); self.pred_cb.setChecked(True)
        self.chase_cb = QCheckBox("bot hunts you"); self.chase_cb.setChecked(True)
        rst = QPushButton("↻ reset round"); rst.clicked.connect(self._reset)
        row.addSpacing(10); row.addWidget(self.pred_cb); row.addWidget(self.chase_cb); row.addWidget(rst)
        row.addStretch(1)
        v.addLayout(row)
        self.canvas = _NetCanvas(self)
        v.addWidget(self.canvas, 1)
        self.timer = QTimer(self); self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)

    def _read_keys(self):
        k = self.canvas.keys
        dx = (Qt.Key_Right in k) - (Qt.Key_Left in k)
        dy = (Qt.Key_Down in k) - (Qt.Key_Up in k)
        m = math.hypot(dx, dy) or 1.0
        return (dx / m * NET_PSPEED, dy / m * NET_PSPEED)

    def _reset(self):
        self.srv_p, self.srv_b, self.c_pos = (20.0, 25.0), (100.0, 25.0), (20.0, 25.0)
        self.inflight.clear(); self.hist.clear(); self.cmds.clear()
        self.seq = self.srv_last_seq = self.srv_tick_n = 0
        self.err_log.clear(); self.corrections = 0; self.snaps_received = 0
        self.bot_snaps.clear()

    def _enqueue(self, kind, data):
        lat = max(15.0, self.lat_s.value() + random.uniform(-self.jit_s.value(), self.jit_s.value()))
        drop = random.random() * 100 < self.loss_s.value()
        self.inflight.append(dict(kind=kind, data=data, arrive=self.now + lat, drop=drop))

    def _server_tick(self):
        self.srv_tick_n += 1
        dt = NET_SNAP_MS / 1000.0
        self.srv_p = _nmove(self.srv_p, self.srv_cmd, dt)
        if self.chase_cb.isChecked():
            d = math.hypot(self.srv_p[0] - self.srv_b[0], self.srv_p[1] - self.srv_b[1]) or 1.0
            v = ((self.srv_p[0] - self.srv_b[0]) / d * NET_BSPEED,
                 (self.srv_p[1] - self.srv_b[1]) / d * NET_BSPEED)
        else:
            t = self.srv_tick_n * 0.05
            tgt = (60 + 40 * math.sin(t * 0.5), 25 + 18 * math.cos(t * 0.33))
            d = math.hypot(tgt[0] - self.srv_b[0], tgt[1] - self.srv_b[1]) or 1.0
            v = ((tgt[0] - self.srv_b[0]) / d * NET_BSPEED * 0.7,
                 (tgt[1] - self.srv_b[1]) / d * NET_BSPEED * 0.7)
        self.srv_b = _nmove(self.srv_b, v, dt)
        d = math.hypot(self.srv_p[0] - self.srv_b[0], self.srv_p[1] - self.srv_b[1])
        if d < 3.0:
            nx = (self.srv_p[0] - self.srv_b[0]) / (d or 1.0)
            ny = (self.srv_p[1] - self.srv_b[1]) / (d or 1.0)
            push = (3.0 - d) * 0.55
            self.srv_p = _nclamp((self.srv_p[0] + nx * push, self.srv_p[1] + ny * push))
            self.srv_b = _nclamp((self.srv_b[0] - nx * push, self.srv_b[1] - ny * push))
        for c in self.coins:
            if c[2] and math.hypot(self.srv_p[0] - c[0], self.srv_p[1] - c[1]) < 2.2:
                c[2] = False; c[3] = self.now; self.coins_collected += 1
            elif not c[2] and self.now - c[3] > 2500:
                for _ in range(8):
                    c[0], c[1] = random.uniform(5, NET_W - 5), random.uniform(5, NET_H - 5)
                    if math.hypot(c[0] - self.srv_p[0], c[1] - self.srv_p[1]) > 12: break
                c[2] = True
        self._enqueue('snap', dict(tick=self.srv_tick_n, p=self.srv_p, seq=self.srv_last_seq,
                                   b=self.srv_b, coins=[c[2] for c in self.coins]))

    def _reconcile(self, d):
        S, sp = d['seq'], d['p']
        pos_at_S = next((pos for (s2, pos) in self.hist if s2 == S), None)
        ref = pos_at_S if pos_at_S is not None else self.c_pos
        err = math.hypot(ref[0] - sp[0], ref[1] - sp[1])
        newpos, newhist = sp, [(s2, pos) for (s2, pos) in self.hist if s2 <= S]
        for s3 in sorted(s3 for s3 in self.cmds if s3 > S):
            newpos = _nmove(newpos, self.cmds[s3], 1 / 60)
            newhist.append((s3, newpos))
        self.c_pos, self.hist = newpos, deque(newhist)
        self.err_log.append((self.now, err)); self.last_err = err
        if err > 0.10:
            self.corrections += 1
            if err > 1.2 and self.now - self._corr_t > 1200:
                self._corr_t = self.now
                self.bus.emit("net_corrected", err=round(err, 2), tick=d['tick'])

    def _tick(self):
        self.now += 16.0
        cmd = self._read_keys()
        self.input_acc += 16.0
        while self.input_acc >= NET_INPUT_MS:
            self.input_acc -= NET_INPUT_MS
            self.seq += 1
            self.cmds[self.seq] = cmd
            self._enqueue('in', dict(seq=self.seq, cmd=cmd))
            while len(self.cmds) > 240: self.cmds.pop(min(self.cmds))
        self.srv_acc += 16.0
        while self.srv_acc >= NET_SNAP_MS:
            self.srv_acc -= NET_SNAP_MS
            self._server_tick()
        due = [pk for pk in self.inflight if pk['arrive'] <= self.now]
        self.inflight = [pk for pk in self.inflight if pk['arrive'] > self.now]
        for pk in due:
            if pk['drop']: continue
            d = pk['data']
            if pk['kind'] == 'in':
                if d['seq'] > self.srv_last_seq:
                    self.srv_last_seq, self.srv_cmd = d['seq'], d['cmd']
            else:
                self.snaps_received += 1
                self.bot_snaps.append((self.now, d['b']))
                self.last_snap_p = d['p']
                for i, alive in enumerate(d['coins']):
                    cc = self.coin_client[i]
                    if cc[2] != alive:
                        cc[2], cc[3] = alive, self.now
                if self.pred_cb.isChecked():
                    self._reconcile(d)
                else:
                    self.c_pos = d['p']
                    self.err_log.append((self.now, 0.0)); self.last_err = 0.0
        if self.pred_cb.isChecked():
            self.c_pos = _nmove(self.c_pos, cmd, 0.016)
            self.hist.append((self.seq, self.c_pos))
            while len(self.hist) > 240: self.hist.popleft()
        else:
            self.lag_secs += 0.016
            if self.lag_secs >= 8 and not self._lag_emitted:
                self._lag_emitted = True
                self.bus.emit("lag_lived", secs=8)
        rtt = self.lat_s.value() * 2
        self.hud = [
            ("prediction " + ("ON — instant input, server reconciles" if self.pred_cb.isChecked()
                              else "OFF — raw snapshots"),
             C_GREEN if self.pred_cb.isChecked() else C_RED),
            (f"rtt ≈ {rtt} ms · snapshots {self.snaps_received} · inputs in flight "
             f"{len([p for p in self.inflight if p['kind'] == 'in'])}", C_TEXT),
            (f"corrections {self.corrections} · last error {self.last_err:.2f} u · coins {self.coins_collected} "
             f"(pop = one RTT late!)", C_ACCENT)]
        self.canvas.update()

    def showEvent(self, e):
        if not self.timer.isActive(): self.timer.start()
        self.canvas.setFocus(); super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop(); super().hideEvent(e)


# ================================================================ INPUT =====
ACTIONS = [
    ("Jump",      [Qt.Key_Space,  Qt.Key_W]),
    ("Fire",      [Qt.Key_F,      Qt.Key_Return]),
    ("Reload",    [Qt.Key_R,      None]),
    ("Move Left", [Qt.Key_Left,   Qt.Key_A]),
    ("Move Right",[Qt.Key_Right,  Qt.Key_D]),
    ("Interact",  [Qt.Key_E,      None]),
]

class AnalogStick(QWidget):
    moved = Signal(float, float, float, float)

    def __init__(self):
        super().__init__()
        self.dead = 0.25
        self.vec = (0.0, 0.0)
        self.setMinimumSize(210, 210)

    def _process(self, vx, vy):
        m = math.hypot(vx, vy)
        if m <= self.dead or m == 0.0: return 0.0, 0.0
        k = (m - self.dead) / (1.0 - self.dead) / m
        return vx * k, vy * k

    def _set_from(self, pos):
        cx, cy = self.width() / 2, self.height() / 2
        R = min(cx, cy) - 14
        vx, vy = (pos.x() - cx) / R, (pos.y() - cy) / R
        m = math.hypot(vx, vy)
        if m > 1.0: vx, vy = vx / m, vy / m
        self.vec = (vx, vy)
        px, py = self._process(vx, vy)
        self.moved.emit(vx, vy, px, py)
        self.update()

    def mousePressEvent(self, e):     self._set_from(e.position())
    def mouseMoveEvent(self, e):      self._set_from(e.position())
    def mouseReleaseEvent(self, e):
        self.vec = (0.0, 0.0)
        self.moved.emit(0.0, 0.0, 0.0, 0.0)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        cx, cy = self.width() / 2, self.height() / 2
        R = min(cx, cy) - 14
        p.setBrush(QColor(C_PANEL)); p.setPen(QPen(QColor(C_BORDER), 1))
        p.drawEllipse(QPointF(cx, cy), R, R)
        p.setPen(QPen(QColor("#3a3d45"), 1))
        p.drawLine(QPointF(cx - R, cy), QPointF(cx + R, cy))
        p.drawLine(QPointF(cx, cy - R), QPointF(cx, cy + R))
        p.setPen(QPen(QColor(C_ORANGE), 1, Qt.DashLine))
        p.drawEllipse(QPointF(cx, cy), R * self.dead, R * self.dead)
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QRectF(0, cy + R * self.dead - 8, self.width(), 16), Qt.AlignCenter,
                   f"dead zone {self.dead:.2f}")
        kx, ky = cx + self.vec[0] * R, cy + self.vec[1] * R
        p.setPen(QPen(QColor(C_ACCENT), 2))
        p.drawLine(QPointF(cx, cy), QPointF(kx, ky))
        p.setBrush(QColor(C_ACCENT)); p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(kx, ky), 10, 10)

class MagBar(QWidget):
    def __init__(self, color):
        super().__init__()
        self.f, self.color = 0.0, color
        self.setFixedHeight(12)

    def set(self, f): self.f = max(0.0, min(1.0, f)); self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setPen(QPen(QColor(C_BORDER), 1))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 5, 5)
        if self.f > 0:
            p.setBrush(QColor(self.color)); p.setPen(Qt.NoPen)
            p.drawRoundedRect(1, 1, max(8, int((self.width() - 2) * self.f)), self.height() - 2, 5, 5)

class InputPage(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.bindings = {name: list(keys) for name, keys in ACTIONS}
        self.capture = None
        self.pressed = set()
        self.last_raw = (0.0, 0.0)
        self.setFocusPolicy(Qt.StrongFocus)
        v = QVBoxLayout(self)
        v.addWidget(page_header("Input Mapper",
            "Gameplay never sees hardware: raw key events (left) are translated through an action map (middle) — rebind any slot by clicking it, then press a key. Analog inputs (right) get a dead zone and rescaling so tiny stick noise never reaches gameplay. Click anywhere here first so the page has keyboard focus."))
        h = QHBoxLayout()
        gb1 = QGroupBox("1 · Raw input events"); b1 = QVBoxLayout(gb1)
        self.status = QLabel("—"); self.status.setObjectName("dim"); self.status.setWordWrap(True)
        b1.addWidget(self.status)
        self.rawlog = QPlainTextEdit(); self.rawlog.setReadOnly(True)
        self.rawlog.setFont(mono(9)); self.rawlog.setMaximumBlockCount(300)
        self.rawlog.setFocusPolicy(Qt.NoFocus)
        b1.addWidget(self.rawlog, 1)
        h.addWidget(gb1, 1)

        gb2 = QGroupBox("2 · Action mapping → 3 · gameplay state"); b2 = QVBoxLayout(gb2)
        grid = QGridLayout()
        grid.addWidget(QLabel("action"), 0, 0)
        grid.addWidget(QLabel("binding A"), 0, 1)
        grid.addWidget(QLabel("binding B"), 0, 2)
        grid.addWidget(QLabel("pressed"), 0, 3)
        self.key_btns, self.leds = {}, {}
        for r, (name, keys) in enumerate(ACTIONS, start=1):
            grid.addWidget(QLabel(name), r, 0)
            for slot in range(2):
                btn = QPushButton(self._keyname(self.bindings[name][slot]))
                btn.setFocusPolicy(Qt.NoFocus)
                btn.clicked.connect(lambda _=False, n=name, s=slot: self._arm(n, s))
                grid.addWidget(btn, r, 1 + slot)
                self.key_btns[(name, slot)] = btn
            led = QFrame(); led.setFixedSize(18, 18)
            led.setStyleSheet(self._led_style(False))
            grid.addWidget(led, r, 3, Qt.AlignCenter)
            self.leds[name] = led
        b2.addLayout(grid)
        note = QLabel("LEDs poll the pressed-key set each event — actions fire on press transitions.")
        note.setObjectName("dim"); note.setWordWrap(True)
        b2.addWidget(note)
        b2.addStretch(1)
        h.addWidget(gb2, 1)

        gb3 = QGroupBox("4 · Analog: dead zone & rescale"); b3 = QVBoxLayout(gb3)
        self.stick = AnalogStick()
        self.stick.moved.connect(self._on_stick)
        b3.addWidget(self.stick)
        row = QHBoxLayout(); row.addWidget(QLabel("dead zone"))
        self.dead_lbl = QLabel("0.25")
        ds = QSlider(Qt.Horizontal); ds.setRange(0, 50); ds.setValue(25)
        ds.valueChanged.connect(self._on_dead)
        row.addWidget(ds); row.addWidget(self.dead_lbl)
        b3.addLayout(row)
        self.raw_mag = MagBar(C_DIM);  self.proc_mag = MagBar(C_GREEN)
        self.lbl_raw = QLabel("raw |v| 0.00"); self.lbl_proc = QLabel("after dead zone |v| 0.00")
        self.lbl_raw.setFont(mono(9)); self.lbl_proc.setFont(mono(9))
        b3.addWidget(self.lbl_raw); b3.addWidget(self.raw_mag)
        b3.addWidget(self.lbl_proc); b3.addWidget(self.proc_mag)
        h.addWidget(gb3, 1)
        v.addLayout(h)
        v.addStretch(1)

    def _keyname(self, key):
        return QKeySequence(key).toString() if key else "— click to bind —"

    def _led_style(self, on):
        bg = C_GREEN if on else "#26282e"
        return f"background:{bg}; border:1px solid {C_BORDER}; border-radius:9px;"

    def _arm(self, action, slot):
        self.capture = (action, slot)
        self.status.setText(f"⌨ press any key for '{action}' (slot {'B' if slot else 'A'})  ·  Esc cancels")
        self.key_btns[(action, slot)].setText("… press a key …")
        self.setFocus()

    def keyPressEvent(self, e):
        if self.capture:
            action, slot = self.capture
            if e.key() == Qt.Key_Escape:
                self.status.setText("rebind cancelled")
            else:
                self.bindings[action][slot] = e.key()
                kn = self._keyname(e.key())
                self.bus.emit("action_rebound", action=action, key=kn)
                self.status.setText(f"'{action}' slot {'B' if slot else 'A'} → {kn}")
            self.capture = None
            self._sync_bindings(); e.accept(); return
        if e.isAutoRepeat(): return
        self.pressed.add(e.key())
        kn = QKeySequence(e.key()).toString() or hex(e.key())
        fired = [n for n, ks in self.bindings.items() if e.key() in ks]
        self.rawlog.appendPlainText(f"press   {kn:<10}" + (f" → action: {', '.join(fired)}" if fired else " → (unbound)"))
        self._refresh_leds(); e.accept()

    def keyReleaseEvent(self, e):
        if e.isAutoRepeat(): return
        self.pressed.discard(e.key())
        kn = QKeySequence(e.key()).toString() or hex(e.key())
        self.rawlog.appendPlainText(f"release {kn:<10}")
        self._refresh_leds(); e.accept()

    def _sync_bindings(self):
        for (name, slot), btn in self.key_btns.items():
            btn.setText(self._keyname(self.bindings[name][slot]))

    def _refresh_leds(self):
        for name in self.leds:
            active = any(k is not None and k in self.pressed for k in self.bindings[name])
            self.leds[name].setStyleSheet(self._led_style(active))

    def _on_dead(self, val):
        self.stick.dead = val / 100.0
        self.dead_lbl.setText(f"{val/100:.2f}")
        rx, ry = self.last_raw
        px, py = self.stick._process(rx, ry)
        self._show_mags(rx, ry, px, py)
        self.stick.update()

    def _on_stick(self, rx, ry, px, py):
        self.last_raw = (rx, ry)
        self._show_mags(rx, ry, px, py)

    def _show_mags(self, rx, ry, px, py):
        rm = math.hypot(rx, ry); pm = math.hypot(px, py)
        self.lbl_raw.setText(f"raw  ({rx:+.2f}, {ry:+.2f})   |v| {rm:.2f}")
        self.lbl_proc.setText(f"after dead zone  ({px:+.2f}, {py:+.2f})   |v| {pm:.2f}")
        self.raw_mag.set(rm); self.proc_mag.set(pm)

    def mousePressEvent(self, e):
        self.setFocus(); super().mousePressEvent(e)

    def showEvent(self, e):
        self.setFocus(); super().showEvent(e)


# ========================================================= EVENT BUS MONITOR =
EVENT_DEFS = [
    ("collision_detected", C_ORANGE, {"a": 3, "b": 7}),
    ("play_sound",         C_GREEN,  {"clip": "explosion.wav", "volume": 0.8}),
    ("entity_destroyed",   C_RED,    {"entity": 12}),
    ("damage_taken",       C_PINK,   {"target": 4, "amount": 25}),
    ("level_loaded",       C_ACCENT, {"name": "level_02"}),
]
EVENT_COLORS = {n: c for n, c, _ in EVENT_DEFS}
LISTENER_DEFS = [
    ("AudioSystem",  C_GREEN,  {"play_sound", "collision_detected", "entity_destroyed"}),
    ("Achievements", C_YELLOW, {"damage_taken", "level_loaded"}),
    ("ParticleFX",   C_PURPLE, {"collision_detected", "entity_destroyed"}),
    ("Logger",       "#26c6da", {"*"}),
]

class FlowWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.packets, self.flash = [], {}
        self.is_subscribed = lambda name: True
        self.setMinimumHeight(240)
        self.timer = QTimer(self); self.timer.setInterval(33)
        self.timer.timeout.connect(self._anim)

    def emit_event(self, name, color, targets):
        self.packets.append([name, color, 0.0, list(targets)])
        if not self.timer.isActive(): self.timer.start()

    def _anim(self):
        done = []
        for pk in self.packets:
            pk[2] += 0.045
            if pk[2] >= 1.0: done.append(pk)
        for pk in done:
            for name in pk[3]: self.flash[name] = 1.0
        self.packets = [pk for pk in self.packets if pk[2] < 1.0]
        for n in list(self.flash):
            self.flash[n] -= 0.07
            if self.flash[n] <= 0: del self.flash[n]
        self.update()
        if not self.packets and not self.flash: self.timer.stop()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        bw_, bh = 150, 28
        cx, busw = w / 2, 30
        m = 26
        n_e, n_l = len(EVENT_DEFS), len(LISTENER_DEFS)
        em = [(20, m + (h - 2 * m) * i / max(1, n_e - 1)) for i in range(n_e)]
        li = [(w - 20 - bw_, m + (h - 2 * m) * i / max(1, n_l - 1)) for i in range(n_l)]
        p.setFont(mono(8))
        for (x, y) in em:
            p.setPen(QPen(QColor("#3a3d45"), 1))
            p.drawLine(QPointF(x + bw_, y + bh / 2), QPointF(cx - busw / 2, y + bh / 2))
        for (name, col, evs), (x, y) in zip(LISTENER_DEFS, li):
            sub = self.is_subscribed(name)
            c = QColor(col) if sub else QColor("#3a3d45"); c.setAlpha(160 if sub else 255)
            p.setPen(QPen(c, 1, Qt.DashLine))
            p.drawLine(QPointF(cx + busw / 2, y + bh / 2), QPointF(x, y + bh / 2))
        p.setBrush(QColor("#152833")); p.setPen(QPen(QColor(C_ACCENT), 2))
        p.drawRoundedRect(QRectF(cx - busw / 2, 12, busw, h - 24), 8, 8)
        p.save(); p.translate(cx, h / 2); p.rotate(-90)
        p.setPen(QColor(C_ACCENT))
        f = mono(9); f.setLetterSpacing(QFont.PercentageSpacing, 160); p.setFont(f)
        p.drawText(QRectF(-100, -10, 200, 20), Qt.AlignCenter, "EVENT BUS")
        p.restore()
        p.setFont(mono(8))
        for (name, col, _), (x, y) in zip(EVENT_DEFS, em):
            r = QRectF(x, y, bw_, bh)
            p.setBrush(QColor(C_PANEL)); p.setPen(QPen(QColor(col), 1))
            p.drawRoundedRect(r, 6, 6)
            p.setPen(QColor(C_TEXT)); p.drawText(r, Qt.AlignCenter, name)
        for (name, col, evs), (x, y) in zip(LISTENER_DEFS, li):
            sub = self.is_subscribed(name)
            r = QRectF(x, y, bw_, bh)
            fl = self.flash.get(name, 0.0)
            p.setBrush(QColor("#2b3b46") if sub else QColor(C_PANEL))
            p.setPen(QPen(QColor(col) if sub else QColor("#3a3d45"), 2 if fl > 0 else 1))
            p.drawRoundedRect(r, 6, 6)
            p.setPen(QColor(C_TEXT if sub else C_DIM))
            p.drawText(r, Qt.AlignCenter, ("● " if sub else "○ ") + name)
        for name, color, t, targets in self.packets:
            ex, ey = em[next(i for i, d in enumerate(EVENT_DEFS) if d[0] == name)]
            start = QPointF(ex + bw_, ey + bh / 2)
            bus_l = QPointF(cx - busw / 2, ey + bh / 2)
            col = QColor(color)
            if t < 0.5:
                pos = QPointF(lerp(start.x(), bus_l.x(), t * 2), start.y())
                self._dot(p, pos, col, 1.0)
            else:
                k = (t - 0.5) * 2
                bus_r = QPointF(cx + busw / 2, ey + bh / 2)
                if not targets:
                    self._dot(p, QPointF(cx, ey + bh / 2), col, 1.0 - k)
                for lname in targets:
                    ix = next(i for i, d in enumerate(LISTENER_DEFS) if d[0] == lname)
                    lx, ly = li[ix]
                    pos = QPointF(lerp(bus_r.x(), lx, k), lerp(bus_r.y(), ly + bh / 2, k))
                    self._dot(p, pos, col, 1.0)

    def _dot(self, p, pos, col, alpha):
        glow = QColor(col); glow.setAlpha(int(70 * alpha))
        p.setPen(Qt.NoPen); p.setBrush(glow)
        p.drawEllipse(pos, 9, 9)
        c = QColor(col); c.setAlpha(int(255 * alpha))
        p.setBrush(c); p.drawEllipse(pos, 4, 4)

class EventBusPage(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        v = QVBoxLayout(self)
        v.addWidget(page_header("Event Bus Monitor",
            "Emitters never know who listens — that's decoupling. Toggle listeners and emit events below, or run other labs: the ECS playground, Resource Manager, Profiler, Shader Lab and every diagram publish onto this same bus, live. (High-frequency stats arrive batched at 1 Hz — per-frame traffic doesn't belong on a bus.)"))
        self.flow = FlowWidget()
        v.addWidget(self.flow, 1)
        bottom = QHBoxLayout()
        gb1 = QGroupBox("Emit events"); b1 = QVBoxLayout(gb1)
        for name, color, payload in EVENT_DEFS:
            btn = QPushButton(name)
            btn.setToolTip(str(payload))
            btn.clicked.connect(lambda _=False, n=name, pl=payload: self.bus.emit(n, **pl))
            b1.addWidget(btn)
        bottom.addWidget(gb1)
        gb2 = QGroupBox("Listeners (subscribers)"); b2 = QVBoxLayout(gb2)
        self.listener_checks = {}
        for name, color, evs in LISTENER_DEFS:
            cb = QCheckBox(name); cb.setChecked(True)
            txt = "any event (*)" if "*" in evs else ", ".join(sorted(evs))
            lbl = QLabel(txt); lbl.setObjectName("dim"); lbl.setFont(mono(7))
            b2.addWidget(cb); b2.addWidget(lbl)
            self.listener_checks[name] = cb
        bottom.addWidget(gb2)
        gb3 = QGroupBox("Traffic log"); b3 = QVBoxLayout(gb3)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True)
        self.log.setFont(mono(9)); self.log.setMaximumBlockCount(400)
        b3.addWidget(self.log)
        bottom.addWidget(gb3, 1)
        v.addLayout(bottom)
        self.flow.is_subscribed = lambda name: self.listener_checks[name].isChecked()
        bus.event_fired.connect(self._on_event)

    def _on_event(self, ev):
        targets = [n for n, _, evs in LISTENER_DEFS
                   if self.listener_checks[n].isChecked() and ("*" in evs or ev.name in evs)]
        if ev.name in EVENT_COLORS:
            self.flow.emit_event(ev.name, EVENT_COLORS[ev.name], targets)
        payload = ", ".join(f"{k}={v}" for k, v in ev.payload.items())
        dest = ", ".join(targets) if targets else "✉ dropped — no subscribers"
        self.log.appendPlainText(f"[{time.strftime('%H:%M:%S')}] {ev.name}({payload}) → {dest}")


# ==================================================================== QUIZ ==
QUIZ = [
    dict(q="What is the primary job of the game loop?",
         o=["Compile engine shaders once at startup", "Orchestrate input → update → render once per frame",
            "Manage the OS window and GPU drivers", "Encode/decode video cutscenes"], a=1,
         why="The loop runs every frame: read input, advance the simulation (update), draw the world (render). Everything else hangs off this rhythm."),
    dict(q="Why do engines simulate physics at a FIXED timestep instead of the real frame time?",
         o=["It uses less CPU", "GPUs require it", "It makes the simulation deterministic and stable, independent of frame rate", "Fixed timesteps render faster"], a=2,
         why="Same dt every step → reproducible results (vital for replays/netcode) and stable integration at any FPS."),
    dict(q="The 'spiral of death' happens when…",
         o=["A build fails repeatedly", "Fixed updates take longer than the fixed step, so the accumulator grows forever", "The camera spirals toward the floor", "VSync is disabled"], a=1,
         why="If update() can't finish within one fixed step, each frame needs more catch-up steps than the last. Try the lag injector!"),
    dict(q="In an ECS, a component is…",
         o=["A base class entities inherit from", "Plain data attached to an entity — no behavior", "A UI widget", "A GPU buffer"], a=1,
         why="Components are pure data. Behavior lives in systems that process every entity owning a given component set."),
    dict(q="What makes ECS memory access fast (data-oriented design)?",
         o=["Components are stored contiguously per type, so iterating them is cache-friendly", "Entities live in a binary tree", "It mirrors GPU VRAM layout", "It avoids all allocations"], a=0,
         why="Systems iterate dense tables of one component type instead of chasing pointers across scattered objects."),
    dict(q="Render interpolation between fixed updates exists to…",
         o=["Blend skeletal animations", "Avoid visual stutter when the render rate ≠ physics rate", "Anti-alias the image", "Interpolate textures"], a=1,
         why="The renderer draws BETWEEN discrete physics states using the accumulator's leftover fraction (alpha)."),
    dict(q="Why do engines use an event bus (publish/subscribe)?",
         o=["It's faster than function calls", "To decouple systems: emitters don't need to know who reacts", "To compress network traffic", "To replace the game loop"], a=1,
         why="This very app's achievements work that way — emitters never reference listeners."),
    dict(q="The resource/asset manager's core responsibilities are…",
         o=["Drawing meshes", "Loading, caching (deduplicating) and unloading assets within a memory budget", "Compiling gameplay scripts", "Scheduling OS threads"], a=1,
         why="Handles + reference counting load each asset once; async streaming keeps frames smooth; references dropping frees memory."),
    dict(q="Broad phase vs narrow phase in collision detection:",
         o=["Broad = precise tests on everything; narrow = cheap pruning", "Broad = cheap pruning of candidate pairs (spatial grids); narrow = precise contact tests", "They're synonyms", "Broad runs on CPU, narrow on GPU"], a=1,
         why="Broad phase cheaply discards impossible pairs; only survivors get the exact (costly) tests."),
    dict(q="What is a draw call?",
         o=["A JavaScript callback", "A command telling the GPU to render geometry with a given state — expensive enough that engines batch them", "A physics query", "A poker move"], a=1,
         why="Engines cull, sort and batch (instancing, atlases) to render the same scene with fewer calls."),
    dict(q="Client-side prediction in netcode means…",
         o=["The server predicts the player's next move", "The client applies its own inputs instantly and reconciles against server snapshots later", "Guessing packet loss", "Compressing inputs"], a=1,
         why="Feel-now, correct-later: rewind to the authoritative state and replay unacknowledged inputs (see the Multiplayer Lab)."),
    dict(q="A replay system can store only player inputs instead of world state because…",
         o=["Inputs are smaller", "Given the same seed and fixed timestep, the same inputs must reproduce the same world", "The GPU stores replays", "Randomness is unnecessary"], a=1,
         why="Determinism: same inputs ⇒ same world. One unpinned float and the replay desyncs (see the Determinism Lab)."),
]

class QuizPage(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.q_idx, self.score, self.radios = 0, 0, []
        v = QVBoxLayout(self)
        v.addWidget(page_header("Quiz", "Twelve questions on everything the other tabs demonstrate."))
        self.stack = QStackedWidget(); v.addWidget(self.stack, 1)
        card = QWidget(); cv = QVBoxLayout(card); cv.setSpacing(12)
        self.progress = QLabel(); self.progress.setObjectName("dim")
        self.question = QLabel(); self.question.setWordWrap(True)
        self.question.setStyleSheet("font-size:15px; font-weight:600;")
        self.opts = QVBoxLayout()
        self.feedback = QLabel(); self.feedback.setWordWrap(True); self.feedback.hide()
        row = QHBoxLayout()
        self.check_btn = QPushButton("Check answer"); self.check_btn.clicked.connect(self._check)
        self.next_btn = QPushButton("Next →"); self.next_btn.setEnabled(False); self.next_btn.clicked.connect(self._next)
        row.addStretch(1); row.addWidget(self.check_btn); row.addWidget(self.next_btn)
        for w in (self.progress, self.question): cv.addWidget(w)
        cv.addLayout(self.opts); cv.addWidget(self.feedback); cv.addLayout(row)
        cv.addStretch(1)
        self.stack.addWidget(card)
        res = QWidget(); rv = QVBoxLayout(res); rv.setAlignment(Qt.AlignCenter)
        self.result_big = QLabel(); self.result_big.setAlignment(Qt.AlignCenter)
        self.result_big.setStyleSheet("font-size:26px; font-weight:800; color:#4fc3f7;")
        self.result_sub = QLabel(); self.result_sub.setAlignment(Qt.AlignCenter); self.result_sub.setObjectName("dim")
        again = QPushButton("↻ Try again"); again.clicked.connect(self._restart)
        for w in (self.result_big, self.result_sub): rv.addWidget(w)
        rv.addSpacing(16); rv.addWidget(again, alignment=Qt.AlignCenter)
        self.stack.addWidget(res)
        self._show_q()

    def _show_q(self):
        q = QUIZ[self.q_idx]
        self.progress.setText(f"Question {self.q_idx + 1} / {len(QUIZ)}    ·    score {self.score}")
        self.question.setText(q["q"])
        while self.opts.count():
            it = self.opts.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        self.radios = []
        for opt in q["o"]:
            rb = QRadioButton(opt); self.opts.addWidget(rb); self.radios.append(rb)
        self.feedback.hide(); self.feedback.setStyleSheet("")
        self.check_btn.setEnabled(True); self.next_btn.setEnabled(False)
        self.next_btn.setText("See results →" if self.q_idx == len(QUIZ) - 1 else "Next →")
        self.stack.setCurrentIndex(0)

    def _check(self):
        pick = next((i for i, rb in enumerate(self.radios) if rb.isChecked()), None)
        q = QUIZ[self.q_idx]
        if pick is None:
            self.feedback.setStyleSheet(f"color:{C_DIM};")
            self.feedback.setText("Select an answer above first.")
            self.feedback.show(); return
        correct = pick == q["a"]
        if correct: self.score += 1
        for rb in self.radios: rb.setEnabled(False)
        self.check_btn.setEnabled(False); self.next_btn.setEnabled(True)
        if correct:
            self.feedback.setStyleSheet(f"color:{C_GREEN};")
            self.feedback.setText(f"✔ Correct!  {q['why']}")
        else:
            self.feedback.setStyleSheet(f"color:{C_RED};")
            self.feedback.setText(f"✘ The answer is: “{q['o'][q['a']]}”.  {q['why']}")
        self.feedback.show()
        self.progress.setText(f"Question {self.q_idx + 1} / {len(QUIZ)}    ·    score {self.score}")

    def _next(self):
        self.q_idx += 1
        if self.q_idx >= len(QUIZ):
            pct = self.score / len(QUIZ)
            verdict = ("Engine-architect material 🏆" if pct >= 0.9 else
                       "Solid understanding 💪" if pct >= 0.7 else
                       "Getting there — revisit the labs 🔁" if pct >= 0.5 else
                       "Rebuild the loop and try again 🛠")
            self.result_big.setText(f"{self.score} / {len(QUIZ)}")
            self.result_sub.setText(verdict)
            self.bus.emit("quiz_finished", score=self.score, total=len(QUIZ))
            self.stack.setCurrentIndex(1)
        else:
            self._show_q()

    def _restart(self):
        self.q_idx, self.score = 0, 0
        self._show_q()


# ============================================================= CAPSTONE =====
CAP_MODULES = ["Game Loop", "Input", "ECS", "Physics", "Renderer", "Resources", "Audio", "Events"]
PHASE_ORDER = ["Input", "ECS", "Physics", "Audio", "Events", "Renderer"]
MILESTONES = [
    ("boot",      "Boot the engine"),
    ("moved",     "Move the player (needs Input)"),
    ("spawned",   "Entities exist (needs ECS)"),
    ("collision", "Witness a collision (needs Physics)"),
    ("audio",     "Hear a hit (needs Audio)"),
    ("textures",  "Load textures at boot (needs Resources)"),
    ("fwd",       "Forward an event to the app bus (needs Events)"),
    ("all10",     "Run 10 s with ALL 8 modules"),
]

class _WireCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setMinimumHeight(190)
        self._rects = {}
        self.setMouseTracking(True)

    def _layout(self):
        w = self.width()
        self._rects = {}
        lw = 130
        self._rects["Game Loop"] = QRectF(w / 2 - lw / 2, 14, lw, 44)
        n = len(CAP_MODULES) - 1
        bw = min(96.0, (w - 32 - (n - 1) * 8) / n)
        total = n * bw + (n - 1) * 8
        x = (w - total) / 2
        for name in CAP_MODULES[1:]:
            self._rects[name] = QRectF(x, 108, bw, 42)
            x += bw + 8

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        self._layout()
        pg = self.page
        hub = self._rects["Game Loop"]
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(10, 14), "engine wiring — click a ghost to add a module · click an added module to remove (while stopped)")
        for name, r in self._rects.items():
            if name == "Game Loop": continue
            if name in pg.modules:
                p.setPen(QPen(QColor("#4a5568"), 1))
                p.drawLine(QPointF(r.center().x(), r.top()), QPointF(hub.center().x(), hub.bottom()))
        active = [m for m in PHASE_ORDER if m in pg.modules]
        for name, r in self._rects.items():
            on = name in pg.modules
            cur = pg.running and name == (active[pg.phase % len(active)] if active else None)
            if name == "Game Loop":
                p.setBrush(QColor("#152833")); p.setPen(QPen(QColor(C_ACCENT), 2 if pg.running else 1))
            elif on:
                p.setBrush(QColor("#332a15") if cur else QColor("#243039"))
                p.setPen(QPen(QColor(C_YELLOW) if cur else QColor("#5a8fb0"), 2 if cur else 1))
            else:
                p.setBrush(QColor("#15171b")); p.setPen(QPen(QColor("#3a3d45"), 1, Qt.DashLine))
            p.drawRoundedRect(r, 7, 7)
            p.setPen(QColor(C_TEXT) if on else QColor(C_DIM)); p.setFont(self.font())
            p.drawText(r, Qt.AlignCenter, ("＋ " + name) if not on else name)
        if pg.running:
            k = (pg.framen % 20) / 20.0
            for name, r in self._rects.items():
                if name in pg.modules and name != "Game Loop":
                    x = lerp(hub.center().x(), r.center().x(), k)
                    y = lerp(hub.bottom(), r.top(), k)
                    p.setBrush(QColor(C_ACCENT)); p.setPen(Qt.NoPen)
                    p.drawEllipse(QPointF(x, y), 2.5, 2.5)
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(10, self.height() - 6),
                   "modules light up in frame order: input → ecs → physics → audio → events → renderer")

    def mousePressEvent(self, e):
        pg = self.page
        for name, r in self._rects.items():
            if r.contains(e.position()):
                if name == "Game Loop": break
                if name in pg.modules:
                    if pg.running:
                        pg._log("pause first to remove modules"); break
                    pg.remove_module(name)
                else:
                    if pg.booted and pg.running:
                        pg._log("pause first to add modules"); break
                    pg.add_module(name)
                break

    def mouseMoveEvent(self, e):
        over = any(r.contains(e.position()) for r in self._rects.values())
        self.setCursor(Qt.PointingHandCursor if over else Qt.ArrowCursor)

class _MiniCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setFocusPolicy(Qt.StrongFocus)
        self.keys = set()
        self.setMinimumHeight(300)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            self.keys.add(e.key()); e.accept(); self.setFocus()
        else: super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        self.keys.discard(e.key()); e.accept()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#0c0d10"))
        w, h = self.width(), self.height()
        pg = self.page
        p.setPen(QPen(QColor("#191b1f"), 1))
        for gx in range(0, w, 40): p.drawLine(gx, 0, gx, h)
        for gy in range(0, h, 40): p.drawLine(0, gy, w, gy)
        if "Renderer" not in pg.modules:
            p.setPen(QColor(C_DIM)); p.setFont(mono(10))
            p.drawText(QRectF(self.rect()), Qt.AlignCenter,
                       "no Renderer module — the simulation IS running\n"
                       "state updates every frame, you just can't see it\n"
                       "(this is why headless servers work)")
            return
        textured = "Resources" in pg.modules and pg.textures_loaded
        for s in pg.sparks:
            p.setPen(Qt.NoPen); p.setBrush(QColor(s[4]))
            p.setOpacity(max(0.0, s[3]))
            p.drawEllipse(QPointF(s[0], s[1]), 2.5, 2.5)
        p.setOpacity(1.0)
        for b in pg.balls:
            if textured:
                p.setBrush(QColor(b[2])); p.setPen(Qt.NoPen)
            else:
                p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(b[2]), 1.5))
            p.drawEllipse(QRectF(b[0] - 7, b[1] - 7, 14, 14))
        px, py = pg.px, pg.py
        if textured:
            for i in range(2):
                for j in range(2):
                    p.setBrush(QColor(C_ACCENT) if (i + j) % 2 == 0 else QColor("#1b4a63"))
                    p.setPen(Qt.NoPen)
                    p.drawRect(QRectF(px - 11 + i * 11, py - 11 + j * 11, 11, 11))
        else:
            p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(C_ACCENT), 1.5))
            p.drawRect(QRectF(px - 11, py - 11, 22, 22))
        if pg.pulse > 0:
            p.setPen(QPen(_qc(C_GREEN, int(160 * pg.pulse)), 2))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(px, py), 16 + (1 - pg.pulse) * 26, 16 + (1 - pg.pulse) * 26)
        p.setPen(QColor(C_DIM)); p.setFont(mono(9))
        lines = [f"uptime {pg.uptime:5.1f}s · fps {pg.fps:4.0f} · entities {len(pg.balls) + 1} · modules: {len(pg.modules)}/8"]
        if "Input" not in pg.modules:
            lines.append("player frozen — no Input module")
        elif "Physics" not in pg.modules and pg.balls:
            lines.append("balls wrap through walls — no Physics module")
        for i, ln in enumerate(lines):
            p.drawText(QPointF(10, 18 + 15 * i), ln)
        if not pg.balls and "ECS" in pg.modules:
            p.setPen(QColor(C_YELLOW)); p.drawText(QPointF(10, h - 12), "press ＋spawn to create entities")

class CapstonePage(QWidget):
    TICK = 1.0 / 60.0

    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.modules = set()
        self.booted = self.running = False
        self.px = self.py = 200.0
        self.balls, self.sparks = [], []
        self.pulse = 0.0
        self.uptime, self.fps, self.framen, self.phase = 0.0, 0.0, 0, 0
        self.textures_loaded = False
        self.acc = 0.0
        self.milestones = {k: False for k, _ in MILESTONES}
        self.last_beep = 0.0
        self.last_ev = 0.0
        self.t0 = time.perf_counter()
        self.fps_n, self.fps_t = 0, time.perf_counter()
        v = QVBoxLayout(self)
        v.addWidget(page_header("Engine Builder — capstone",
            "Assemble a working mini-engine one module at a time. Click ghost boxes in the wiring diagram (nothing works until Game Loop exists — try running without it). Notice the payoffs: no Renderer = a running-but-invisible sim, no Resources = wireframe graphics, no Physics = balls passing through walls, no Events = collisions never reach the app's Event Bus. Complete all milestones to ship it."))
        h = QHBoxLayout()
        left = QWidget(); left.setFixedWidth(300)
        lv = QVBoxLayout(left); lv.setContentsMargins(0, 0, 0, 0)
        gb1 = QGroupBox("Boot & run"); b1 = QGridLayout(gb1)
        self.boot_btn = QPushButton("⚙ Boot engine"); self.boot_btn.clicked.connect(self._boot)
        self.run_btn = QPushButton("▶ Run"); self.run_btn.setEnabled(False); self.run_btn.clicked.connect(self._toggle_run)
        spawn = QPushButton("＋ spawn 5"); spawn.clicked.connect(self._spawn)
        self.beep_cb = QCheckBox("🔊 real beeps")
        rst = QPushButton("↻ reset"); rst.clicked.connect(self._reset)
        b1.addWidget(self.boot_btn, 0, 0); b1.addWidget(self.run_btn, 0, 1)
        b1.addWidget(spawn, 1, 0); b1.addWidget(rst, 1, 1)
        lv.addWidget(gb1)
        gb2 = QGroupBox("Modules"); b2 = QVBoxLayout(gb2)
        self.mod_lbls = {}
        for m in CAP_MODULES:
            l = QLabel("○ " + m); l.setFont(mono(10)); l.setObjectName("dim")
            b2.addWidget(l); self.mod_lbls[m] = l
        lv.addWidget(gb2)
        gb3 = QGroupBox("Milestones"); b3 = QVBoxLayout(gb3)
        self.ms_lbls = {}
        for key, label in MILESTONES:
            l = QLabel("☐ " + label); l.setFont(mono(9)); l.setObjectName("dim")
            b3.addWidget(l); self.ms_lbls[key] = l
        lv.addWidget(gb3)
        lv.addStretch(1)
        h.addWidget(left)
        right = QVBoxLayout()
        self.wires = _WireCanvas(self)
        self.mini = _MiniCanvas(self)
        right.addWidget(self.wires)
        right.addWidget(self.mini, 1)
        h.addLayout(right, 1)
        v.addLayout(h)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True)
        self.log.setFont(mono(9)); self.log.setMaximumBlockCount(300)
        self.log.setMinimumHeight(96)
        v.addWidget(self.log)
        self.timer = QTimer(self); self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)
        self._log("engine builder v1.0 — no modules installed. Click a ghost box to begin (Game Loop is the heart).")

    def _log(self, s):
        self.log.appendPlainText(f"[{time.perf_counter() - self.t0:6.1f}] {s}")

    def _sync_labels(self):
        for m in CAP_MODULES:
            l = self.mod_lbls[m]
            on = m in self.modules
            l.setText(("● " if on else "○ ") + m)
            l.setStyleSheet(f"color:{C_GREEN if on else '#9aa0a6'};")
            l.setObjectName("" if on else "dim")
        for key, label in MILESTONES:
            l = self.ms_lbls[key]
            done = self.milestones[key]
            l.setText(("☑ " if done else "☐ ") + label)
            l.setStyleSheet(f"color:{C_GREEN}; font-weight:600;" if done else "")
        self.run_btn.setEnabled(self.booted and "Game Loop" in self.modules)

    def add_module(self, m):
        if m in self.modules: return
        self.modules.add(m)
        self._log(f"installed module: {m}")
        self._sync_labels(); self.wires.update(); self.mini.setFocus()

    def remove_module(self, m):
        self.modules.discard(m)
        if m == "Game Loop" and self.running: self._toggle_run()
        self._log(f"removed module: {m}")
        self._sync_labels(); self.wires.update()

    def _boot(self):
        self.booted = True
        self.textures_loaded = "Resources" in self.modules
        self._log("── boot sequence ──")
        order = ["Resources", "Input", "ECS", "Physics", "Audio", "Events", "Renderer", "Game Loop"]
        msgs = {"Resources": f"loading textures… {'✓ 12 textures resident' if self.textures_loaded else '✗ nothing to load — wireframe fallback'}",
                "Input": "keyboard/action map ready", "ECS": "entity tables allocated",
                "Physics": "collision worlds initialized", "Audio": "mixer online (2 buses)",
                "Events": "bus ready", "Renderer": "swapchain created",
                "Game Loop": "entering main loop ✓"}
        delay = 90
        for m in order:
            if m in self.modules:
                QTimer.singleShot(delay, lambda mm=m: self._log(f"  [{mm.lower()}] {msgs[mm]}"))
                delay += 110
        QTimer.singleShot(delay, lambda: (self._log(f"boot complete — {len(self.modules)}/8 modules · "
                                                    f"{'press ▶ Run' if 'Game Loop' in self.modules else 'Game Loop MISSING'}"),
                                          self._milestone("boot")))
        self.run_btn.setEnabled(False)
        QTimer.singleShot(delay + 60, self._sync_labels)
        if "ECS" in self.modules and not self.balls:
            QTimer.singleShot(delay, self._spawn_initial)

    def _spawn_initial(self):
        for _ in range(6): self._spawn_one()

    def _toggle_run(self):
        self.running = not self.running
        self.run_btn.setText("⏸ Pause" if self.running else "▶ Run")
        self._log("main loop running — input → update → render every frame" if self.running else "main loop halted")
        self.mini.setFocus()

    def _spawn(self):
        if "ECS" not in self.modules:
            self._log("can't spawn — no ECS module"); return
        for _ in range(5): self._spawn_one()

    def _spawn_one(self):
        c = random.choice(PALETTE)
        self.balls.append([random.uniform(30, max(40, self.mini.width() - 30)),
                           random.uniform(30, max(40, self.mini.height() - 30)),
                           c, random.uniform(-120, 120), random.uniform(-120, 120)])

    def _reset(self):
        self.running = False; self.booted = False
        self.modules = set(); self.balls = []; self.sparks = []
        self.uptime = self.acc = 0.0
        self.textures_loaded = False
        self.milestones = {k: False for k, _ in MILESTONES}
        self.run_btn.setText("▶ Run"); self.run_btn.setEnabled(False)
        self._log("world destroyed — fresh project")
        self._sync_labels(); self.wires.update()

    def _milestone(self, key):
        if self.milestones[key]: return
        self.milestones[key] = True
        label = next(l for k, l in MILESTONES if k == key)
        self._log(f"🏁 milestone: {label}")
        self.bus.emit("capstone_milestone", id=key)
        if all(self.milestones.values()):
            self._log("🚢 ALL MILESTONES COMPLETE — you built an engine. Ship it!")
            self.bus.emit("capstone_complete", modules=len(self.modules))

    def _tick(self):
        self.fps_n += 1
        now = time.perf_counter()
        if now - self.fps_t >= 0.5:
            self.fps = self.fps_n / (now - self.fps_t); self.fps_n = 0; self.fps_t = now
        if not (self.booted and self.running and "Game Loop" in self.modules):
            self.mini.update(); self.wires.update(); return
        self.acc += 0.016
        steps = 0
        while self.acc >= self.TICK and steps < 5:
            self.acc -= self.TICK; steps += 1
            self.uptime += self.TICK
            self.framen += 1
            n_active = max(1, len([m for m in PHASE_ORDER if m in self.modules]))
            self.phase = (self.phase + 1) % n_active
            W, H = max(60, self.mini.width()), max(60, self.mini.height())
            if "Input" in self.modules:
                k = self.mini.keys
                dx = (Qt.Key_Right in k) - (Qt.Key_Left in k)
                dy = (Qt.Key_Down in k) - (Qt.Key_Up in k)
                if dx or dy:
                    self.px = min(W - 14, max(14, self.px + dx * 170 * self.TICK))
                    self.py = min(H - 14, max(14, self.py + dy * 170 * self.TICK))
                    self._milestone("moved")
            phys = "Physics" in self.modules
            for b in self.balls:
                b[0] += b[3] * self.TICK; b[1] += b[4] * self.TICK
                if phys:
                    if b[0] < 8:  b[0] = 8;  b[3] = abs(b[3])
                    if b[0] > W - 8:  b[0] = W - 8;  b[3] = -abs(b[3])
                    if b[1] < 8:  b[1] = 8;  b[4] = abs(b[4])
                    if b[1] > H - 8:  b[1] = H - 8;  b[4] = -abs(b[4])
                else:
                    if b[0] < -20: b[0] = W + 10
                    if b[0] > W + 20: b[0] = -10
                    if b[1] < -20: b[1] = H + 10
                    if b[1] > H + 20: b[1] = -10
            if phys and self.balls:
                collisions = []
                for i in range(len(self.balls)):
                    b2 = self.balls[i]
                    if (b2[0] - self.px) ** 2 + (b2[1] - self.py) ** 2 < 18 ** 2:
                        d = max(0.2, math.hypot(b2[0] - self.px, b2[1] - self.py))
                        b2[3] = (b2[0] - self.px) / d * 160
                        b2[4] = (b2[1] - self.py) / d * 160
                        collisions.append(((b2[0] + self.px) / 2, (b2[1] + self.py) / 2))
                    for j in range(i + 1, len(self.balls)):
                        a = self.balls[j]
                        if (a[0] - b2[0]) ** 2 + (a[1] - b2[1]) ** 2 < 18 ** 2:
                            a[3], b2[3] = b2[3], a[3]
                            a[4], b2[4] = b2[4], a[4]
                            collisions.append(((a[0] + b2[0]) / 2, (a[1] + b2[1]) / 2))
                if collisions:
                    self._milestone("collision")
                    if "Audio" in self.modules:
                        self.pulse = 1.0
                        self._milestone("audio")
                        if self.beep_cb.isChecked() and now - self.last_beep > 0.25:
                            self.last_beep = now; QApplication.beep()
                    if "Events" in self.modules:
                        self._milestone("fwd")
                        if now - self.last_ev > 0.3:
                            self.last_ev = now
                            self.bus.emit("mini_collision", count=len(collisions), x=int(collisions[0][0]))
                    if "Renderer" in self.modules:
                        for (cx, cy) in collisions[:4]:
                            self.sparks.append([cx, cy, 0, 0, 1.0, C_YELLOW])
            if self.balls: self._milestone("spawned")
            for s in self.sparks: s[3] -= 0.04
            self.sparks = [s for s in self.sparks if s[3] > 0]
            self.pulse = max(0.0, self.pulse - 0.03)
        if len(self.modules) == 8 and self.uptime >= 10.0:
            self._milestone("all10")
        self.mini.update(); self.wires.update()

    def showEvent(self, e):
        if not self.timer.isActive(): self.timer.start()
        self.mini.setFocus()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop(); super().hideEvent(e)


# =============================================================== DIAGRAMS ===
LAYER_DEFS = [
    ("Hardware",              C_RED,     "CPU runs your game loop; GPU turns draw lists into pixels; RAM/VRAM hold the data."),
    ("OS & drivers",          "#8d6e63", "The OS schedules threads and delivers device events. Drivers translate API commands for each GPU generation."),
    ("Graphics / audio APIs", C_YELLOW,  "Vulkan, D3D12, Metal, XAudio2 — standardized interfaces. Engines hide them behind an RHI."),
    ("Platform layer",        C_ORANGE,  "The engine's wrapper over OS specifics: windows, file IO, clocks, threads, sockets."),
    ("Engine core",           C_ACCENT,  "The reusable machinery: loop, ECS, physics, renderer, audio, resources, input. Game-agnostic."),
    ("Gameplay / scripts",    C_GREEN,   "The rules of THIS game. It calls into the engine; the engine knows nothing about it."),
    ("Tools & editor",        C_PINK,    "Level editor, importers, profilers — often a separate process, not shipped with the game."),
]

class _LayersCanvas(QWidget):
    TRACES = {
        "input": ([0, 1, 2, 3, 4, 5],
                  ["key physically pressed", "OS delivers WM_KEYDOWN", "graphics/event API",
                   "platform layer polls events", "input system → 'Jump' action", "gameplay script reacts"]),
        "frame": ([5, 4, 3, 2, 1, 0],
                  ["script moved the player", "renderer builds the draw list", "platform: begin frame",
                   "RHI encodes commands", "driver translates", "GPU rasterizes → pixels"]),
    }

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.trace, self.kind = None, None
        self._rects = []
        self.setMinimumHeight(360)
        self.setMouseTracking(True)
        self.timer = QTimer(self); self.timer.setInterval(30)
        self.timer.timeout.connect(self._tick)

    def begin_trace(self, kind):
        path, labels = self.TRACES[kind]
        self.kind = kind
        self.trace = {"path": path, "labels": labels, "i": 0, "k": 0.0}
        if not self.timer.isActive(): self.timer.start()

    def _tick(self):
        if not self.trace:
            self.timer.stop(); return
        self.trace["k"] += 0.055
        if self.trace["k"] >= 1.0:
            self.trace["k"] = 0.0
            self.trace["i"] += 1
            if self.trace["i"] >= len(self.trace["path"]) - 1:
                self.owner.bus.emit("layer_traced", trace=self.kind)
                self.trace = None
                self.timer.stop()
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        n, m, gap = len(LAYER_DEFS), 12, 7
        bh = (h - 2 * m - (n - 1) * gap) / n
        self._rects = []
        f = self.font()
        for i, (name, color, _) in enumerate(LAYER_DEFS):
            y = h - m - (i + 1) * bh - i * gap
            r = QRectF(14, y, w - 28, bh)
            self._rects.append(r)
            sel = i == self.owner.selected
            p.setBrush(QColor("#243039") if sel else QColor(C_PANEL))
            p.setPen(QPen(QColor(color), 3 if sel else 1))
            p.drawRoundedRect(r, 8, 8)
            p.setPen(QColor(C_TEXT)); f.setBold(sel); p.setFont(f)
            p.drawText(r.adjusted(14, 0, -50, 0), Qt.AlignVCenter | Qt.AlignLeft, name)
            p.setPen(QColor(C_DIM)); p.setFont(mono(8))
            p.drawText(r.adjusted(0, 0, -14, 0), Qt.AlignVCenter | Qt.AlignRight, f"L{i}")
        if self.trace:
            path, labels = self.trace["path"], self.trace["labels"]
            i, k = self.trace["i"], min(self.trace["k"], 1.0)
            a = self._rects[path[i]].center(); b = self._rects[path[i + 1]].center()
            p.setPen(QPen(_qc(C_ACCENT, 150), 2)); p.drawLine(a, b)
            pos = QPointF(lerp(a.x(), b.x(), k), lerp(a.y(), b.y(), k))
            glow = QColor(C_ACCENT); glow.setAlpha(80)
            p.setPen(Qt.NoPen); p.setBrush(glow); p.drawEllipse(pos, 12, 12)
            p.setBrush(QColor(C_ACCENT)); p.drawEllipse(pos, 5, 5)
            p.setPen(QColor(C_YELLOW)); p.setFont(mono(9))
            p.drawText(QPointF(20, 20), "▶ " + labels[min(i + 1, len(labels) - 1)])
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(16, h - 2), "hardware at the bottom · your game at the top")

    def mousePressEvent(self, e):
        for i, r in enumerate(self._rects):
            if r.contains(e.position()):
                self.owner.selected = i
                self.owner._sync_desc()
                self.update(); break

    def mouseMoveEvent(self, e):
        over = any(r.contains(e.position()) for r in self._rects)
        self.setCursor(Qt.PointingHandCursor if over else Qt.ArrowCursor)

class LayersDiagram(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.selected = 4
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)
        v.addWidget(diag_header("Engine layers — where does your code sit?",
            "Every engine is a stack: hardware at the bottom, your game at the top. Click a layer to read what it owns, then run a trace to watch a keypress climb the stack — or a draw call descend it."))
        h = QHBoxLayout()
        self.canvas = _LayersCanvas(self)
        h.addWidget(self.canvas, 1)
        side = QWidget(); sv = QVBoxLayout(side); sv.setContentsMargins(0, 0, 0, 0)
        b1 = QPushButton("⌨  Trace: keypress → action")
        b1.clicked.connect(lambda: self.canvas.begin_trace("input"))
        b2 = QPushButton("🖼  Trace: draw a frame")
        b2.clicked.connect(lambda: self.canvas.begin_trace("frame"))
        self.desc = QLabel(); self.desc.setWordWrap(True); self.desc.setMinimumWidth(250)
        sv.addWidget(b1); sv.addWidget(b2); sv.addSpacing(12)
        sv.addWidget(QLabel("<b>Layer detail</b>")); sv.addWidget(self.desc); sv.addStretch(1)
        h.addWidget(side)
        v.addLayout(h)
        self._sync_desc()

    def _sync_desc(self):
        name, color, txt = LAYER_DEFS[self.selected]
        self.desc.setText(f"<span style='color:{color}; font-weight:700;'>{name}</span><br>{txt}")

    def start(self): pass
    def stop(self): self.canvas.timer.stop(); self.canvas.trace = None


class _PipeCanvas(QWidget):
    STAGES = [("Main thread · simulate", C_ACCENT, 26),
              ("Render thread · build commands", C_PURPLE, 18),
              ("GPU · execute", C_GREEN, 22)]

    def __init__(self, page):
        super().__init__()
        self.page = page
        self.scroll = 0.0
        self.setMinimumHeight(230)
        self.timer = QTimer(self); self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)

    def _tick(self):
        self.scroll += 1.15
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        pipe = self.page.pipe_cb.isChecked()
        period = 26 if pipe else 66
        offs = [0, 26, 40] if pipe else [0, 26, 44]
        left, top = 205, 16
        laneh = (h - top - 56) / 3
        f = self.font()
        for r, (name, color, sw) in enumerate(self.STAGES):
            ly = top + r * laneh
            p.setPen(QColor(C_BORDER)); p.drawLine(left, ly + laneh / 2, w - 10, ly + laneh / 2)
            p.setPen(QColor(C_TEXT)); f.setBold(False); p.setFont(f)
            p.drawText(QRectF(8, ly, left - 16, laneh), Qt.AlignVCenter | Qt.AlignRight, name)
            base = int(self.scroll // period)
            for k in range(-2, int((w - left) / period) + 3):
                bx = left + k * period + offs[r] - (self.scroll % period)
                p.setBrush(QColor(color)); p.setPen(Qt.NoPen)
                p.drawRoundedRect(QRectF(bx, ly + 8, sw - 2, laneh - 16), 3, 3)
                if r == 0:
                    p.setPen(QColor(C_DIM)); p.setFont(mono(8))
                    p.drawText(QPointF(bx, ly + laneh - 1), f"F{k + base}")
        if pipe:
            stats = "pipelined · throughput: 1 frame / 26 ticks  (≈2.5× faster)  ·  idle: main 0% · render-thr 31% · GPU 15%"
        else:
            stats = "synchronized (no overlap) · throughput: 1 frame / 66 ticks  ·  idle: main 61% · render-thr 73% · GPU 67%"
        p.setPen(QColor(C_YELLOW if pipe else C_RED)); p.setFont(mono(9))
        p.drawText(QPointF(10, h - 24), stats)
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(10, h - 8),
                   "the GPU renders frame N while the CPU is already simulating N+1 — sync every stage and hardware sits idle")

    def start(self):
        if not self.timer.isActive(): self.timer.start()

    def stop(self): self.timer.stop()

class CpuGpuDiagram(QWidget):
    def __init__(self, bus):
        super().__init__()
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)
        v.addWidget(diag_header("CPU / GPU pipeline — why frames overlap",
            "Simulating, building render commands and executing on the GPU are three stages on different processors. Pipelining them means the GPU renders one frame while the CPU prepares the next — roughly 2.5× the throughput of a fully synchronized loop."))
        row = QHBoxLayout()
        self.pipe_cb = QCheckBox("pipelined (CPU & GPU overlap)"); self.pipe_cb.setChecked(True)
        row.addWidget(self.pipe_cb); row.addStretch(1)
        v.addLayout(row)
        self.canvas = _PipeCanvas(self)
        v.addWidget(self.canvas, 1)

    def start(self): self.canvas.start()
    def stop(self): self.canvas.stop()


class _AccCanvas(QWidget):
    FIXED = 1000.0 / 60.0

    def __init__(self, page):
        super().__init__()
        self.page = page
        self.acc, self.alpha = 0.0, 0.0
        self.last_updates, self.trips = 0, 0
        self.tokens, self.recent = [], deque(maxlen=70)
        self.setMinimumHeight(340)
        self.timer = QTimer(self); self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)

    def _tick(self):
        dt = self.page.avg_ms * random.uniform(0.6, 1.4)
        self.recent.append(dt)
        self.acc += dt
        n = 0
        while self.acc >= self.FIXED and n < 8:
            self.acc -= self.FIXED; n += 1
            self.tokens.append([120, self.height() - 80, -1.0, 16])
        if n >= 8:
            self.acc = 0.0; self.trips += 1
            self.page.bus.emit("spiral_guard", load_ms=int(self.page.avg_ms))
        self.alpha = self.acc / self.FIXED
        self.last_updates = n
        for tk in self.tokens:
            tk[2] += 0.5; tk[1] += tk[2]
        self.tokens = [tk for tk in self.tokens if tk[1] < self.height() - 42]
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(24, 20), "arriving frame times (dt, jittery)")
        x = 24
        p.setPen(Qt.NoPen)
        for dt in list(self.recent)[-60:]:
            bh_ = min(46.0, dt * 1.4)
            p.setBrush(QColor(C_ACCENT if dt <= self.FIXED else C_ORANGE))
            p.drawRect(QRectF(x, 56 - bh_, 4, bh_))
            x += 6
        p.setPen(QPen(QColor(C_GREEN, 120), 1, Qt.DashLine))
        p.drawLine(QPointF(20, 56 - self.FIXED * 1.4), QPointF(x + 10, 56 - self.FIXED * 1.4))
        p.setPen(QColor(C_GREEN)); p.drawText(QPointF(x + 14, 60), "16.7 ms budget")
        tx, ty, tw, tb = 30, 96, 64, h - 66
        tank_h = tb - ty
        p.setPen(QPen(QColor(C_BORDER), 1)); p.setBrush(QColor("#0d0f12"))
        p.drawRect(QRectF(tx, ty, tw, tank_h))
        px = tank_h / 90.0
        lvl = min(self.acc, 90.0) * px
        danger = self.acc > 3 * self.FIXED
        p.setBrush(QColor(C_RED if danger else C_ACCENT)); p.setPen(Qt.NoPen)
        p.drawRect(QRectF(tx + 1, tb - lvl, tw - 2, lvl))
        f = mono(8)
        for k in range(1, 5):
            gy = tb - k * self.FIXED * px
            if gy > ty:
                p.setPen(QPen(QColor(C_BORDER), 1)); p.drawLine(QPointF(tx, gy), QPointF(tx + tw, gy))
                p.setPen(QColor(C_DIM)); p.setFont(f)
                p.drawText(QPointF(tx + tw + 4, gy + 3), f"{k} step{'s' if k > 1 else ''}")
        p.setPen(QColor(C_DIM)); p.setFont(mono(9))
        p.drawText(QPointF(tx - 6, tb + 18), "accumulator")
        p.drawText(QPointF(tx - 6, tb + 32), f"{self.acc:5.1f} ms")
        for tkx, tky, _, _ in self.tokens:
            p.setBrush(QColor(C_GREEN)); p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(tkx, tky, 16, 14), 3, 3)
        p.setPen(QColor(C_GREEN)); p.setFont(mono(9))
        p.drawText(QPointF(112, tb + 14), "update()  ·  each green block = one fixed 1/60 s step consumed")
        sx = min(w - 240, 420)
        p.setPen(QColor(C_TEXT)); p.setFont(mono(10))
        lines = [f"updates last frame : {self.last_updates}",
                 f"render alpha       : {self.alpha:.2f}",
                 f"guard trips        : {self.trips}"]
        for i, ln in enumerate(lines):
            p.drawText(QPointF(sx, 40 + 18 * i), ln)
        p.setPen(QPen(QColor(C_BORDER), 1)); p.setBrush(QColor("#0d0f12"))
        p.drawRect(QRectF(sx, 40 + 18 * 3, 160, 12))
        p.setBrush(QColor(C_PURPLE)); p.setPen(Qt.NoPen)
        p.drawRect(QRectF(sx + 1, 40 + 18 * 3 + 1, max(0.0, 158 * self.alpha), 10))
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(sx, 40 + 18 * 5), "alpha = leftover fraction of a step → interpolates rendering")
        p.drawText(QPointF(sx, 40 + 18 * 6), "raise avg frame time above ~17 ms and the tank never drains")

    def start(self):
        if not self.timer.isActive(): self.timer.start()

    def stop(self): self.timer.stop()

class AccumulatorDiagram(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.avg_ms = 16.0
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)
        v.addWidget(diag_header("The accumulator — how fixed timestep works",
            "Real frame times jitter (watch the arrivals). Each one is POURED into the accumulator tank; whenever a full 16.7 ms step has pooled, one update() token drops out and the tank drains. Whatever remains sets the render-interpolation alpha. This is the same math the Game Loop Lab runs — here you can watch it."))
        row = QHBoxLayout()
        row.addWidget(QLabel("average real frame time"))
        self.avg_lbl = QLabel("16 ms")
        s = QSlider(Qt.Horizontal); s.setRange(8, 40); s.setValue(16)
        s.valueChanged.connect(lambda val: (setattr(self, "avg_ms", float(val)),
                                            self.avg_lbl.setText(f"{val} ms")))
        row.addWidget(s); row.addWidget(self.avg_lbl); row.addStretch(1)
        v.addLayout(row)
        self.canvas = _AccCanvas(self)
        v.addWidget(self.canvas, 1)

    def start(self): self.canvas.start()
    def stop(self): self.canvas.stop()


MEM_FIELDS = ["x", "y", "vx", "vy", "mesh", "mat", "sfx", "ai"]
MEM_USEFUL = 4
MEM_ENTITIES = 6

class _MemCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.tick_n, self.step_i = 0, 0
        self.fetched, self.used = set(), set()
        self.note = ""
        self.setMinimumHeight(300)
        self.timer = QTimer(self); self.timer.setInterval(90)
        self.timer.timeout.connect(self._tick)

    def _steps(self):
        if self.page.aos_rb.isChecked():
            return [({(e, c) for c in range(8)},
                     {(e, c) for c in range(MEM_USEFUL)},
                     f"fetch entity #{e} — the cache line drags ALL 8 fields; movement uses 4")
                    for e in range(MEM_ENTITIES)]
        return [({(f, e) for e in range(MEM_ENTITIES)},
                 {(f, e) for e in range(MEM_ENTITIES)},
                 f"stream the '{MEM_FIELDS[f]}' column — 6 contiguous values, nothing else")
                for f in range(MEM_USEFUL)]

    def _tick(self):
        steps = self._steps()
        self.tick_n += 1
        if self.step_i >= len(steps):
            if self.tick_n % 10 == 0:
                self.step_i, self.fetched, self.used = 0, set(), set()
                self.note = ""
        elif self.tick_n % 3 == 0:
            fr, us, self.note = steps[self.step_i]
            self.fetched |= fr; self.used |= us
            self.step_i += 1
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        aos = self.page.aos_rb.isChecked()
        rows = MEM_ENTITIES if aos else len(MEM_FIELDS)
        cols = len(MEM_FIELDS) if aos else MEM_ENTITIES
        cw = min(52.0, (w - 150) / max(1, cols))
        ch = min(34.0, (h - 110) / max(1, rows))
        ox, oy = 96, 64
        p.setFont(mono(9))
        for c in range(cols):
            p.setPen(QColor(C_DIM))
            p.drawText(QRectF(ox + c * cw, oy - 20, cw, 16), Qt.AlignCenter,
                       MEM_FIELDS[c] if aos else f"#{c}")
        for r in range(rows):
            p.setPen(QColor(C_DIM))
            p.drawText(QRectF(6, oy + r * ch, ox - 12, ch), Qt.AlignVCenter | Qt.AlignRight,
                       f"entity #{r}" if aos else MEM_FIELDS[r])
            for c in range(cols):
                useful = (c < MEM_USEFUL) if aos else (r < MEM_USEFUL)
                if (r, c) in self.used:
                    fill, pen = QColor(C_ACCENT), C_ACCENT
                elif (r, c) in self.fetched:
                    fill, pen = QColor("#3a2430"), C_RED
                else:
                    fill = QColor("#1b2430" if useful else "#171a1e")
                    pen = "#26303a" if useful else "#22252b"
                p.setBrush(fill); p.setPen(QPen(QColor(pen), 1))
                p.drawRoundedRect(QRectF(ox + c * cw + 1.5, oy + r * ch + 1.5, cw - 3, ch - 3), 3, 3)
        nf, nu = len(self.fetched), len(self.used)
        p.setFont(mono(10)); p.setPen(QColor(C_TEXT))
        p.drawText(QPointF(ox, 30), f"MovementSystem pass — {'AoS' if aos else 'SoA'}")
        p.setFont(mono(9))
        p.setPen(QColor(C_ORANGE)); p.drawText(QPointF(ox, 48), f"fetched: {nf} cells")
        p.setPen(QColor(C_ACCENT)); p.drawText(QPointF(ox + 150, 48), f"used: {nu} cells")
        if nf:
            waste = 100.0 * (nf - nu) / nf
            p.setPen(QColor(C_RED if waste > 5 else C_GREEN))
            p.drawText(QPointF(ox + 280, 48), f"wasted: {waste:.0f}%")
        if self.note:
            p.setPen(QColor(C_YELLOW)); p.setFont(mono(9))
            p.drawText(QPointF(20, h - 14), "▶ " + self.note)

    def start(self):
        if not self.timer.isActive(): self.timer.start()

    def stop(self): self.timer.stop()

class MemoryLayoutDiagram(QWidget):
    def __init__(self, bus):
        super().__init__()
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)
        v.addWidget(diag_header("Memory layout — AoS vs SoA (why ECS is fast)",
            "The MovementSystem needs x, y, vx, vy — nothing else. With AoS (one object per entity) every cache-line fetch drags in fields other systems own: half the traffic is wasted. With SoA (one dense column per component type) the system streams exactly the four arrays it needs. Same data, same math, half the memory traffic."))
        row = QHBoxLayout()
        self.aos_rb = QRadioButton("AoS — array of structs (object per entity)")
        self.soa_rb = QRadioButton("SoA — struct of arrays (column per field)")
        self.aos_rb.setChecked(True)
        self.aos_rb.toggled.connect(self._mode)
        row.addWidget(self.aos_rb); row.addWidget(self.soa_rb); row.addStretch(1)
        v.addLayout(row)
        self.canvas = _MemCanvas(self)
        v.addWidget(self.canvas, 1)

    def _mode(self):
        self.canvas.step_i = 0; self.canvas.fetched = set(); self.canvas.used = set()

    def start(self): self.canvas.start()
    def stop(self): self.canvas.stop()


class _QT:
    __slots__ = ("x", "y", "w", "h", "d", "items", "kids")

    def __init__(self, x, y, w, h, d):
        self.x, self.y, self.w, self.h, self.d = x, y, w, h, d
        self.items, self.kids = [], None

    def insert(self, i, pts):
        if self.kids:
            self.kids[self._quad(pts[i])].insert(i, pts); return
        self.items.append(i)
        if len(self.items) > 4 and self.d < 6:
            hw, hh = self.w / 2, self.h / 2
            self.kids = [_QT(self.x + (hw if k & 1 else 0), self.y + (hh if k & 2 else 0),
                             hw, hh, self.d + 1) for k in range(4)]
            for j in self.items:
                self.kids[self._quad(pts[j])].insert(j, pts)
            self.items = []

    def _quad(self, pt):
        return (1 if pt[0] > self.x + self.w / 2 else 0) + (2 if pt[1] > self.y + self.h / 2 else 0)

    def query(self, rx, ry, rw, rh, out):
        if rx > self.x + self.w or rx + rw < self.x or ry > self.y + self.h or ry + rh < self.y:
            return
        if self.kids:
            for k in self.kids: k.query(rx, ry, rw, rh, out)
        else:
            out.extend(self.items)

    def stats(self, nodes=0, depth=0):
        nodes += 1; depth = max(depth, self.d)
        if self.kids:
            for k in self.kids:
                nodes, depth = k.stats(nodes, depth)
        return nodes, depth

class _QTCanvas(QWidget):
    R = 70.0

    def __init__(self, page):
        super().__init__()
        self.page = page
        self.pts, self.root = [], None
        self.mouse = None
        self.setMouseTracking(True)
        self.setMinimumHeight(340)

    def scatter(self, n):
        w, h = max(self.width(), 300), max(self.height(), 220)
        self.pts = [(random.uniform(12, w - 12), random.uniform(12, h - 12),
                     random.choice(PALETTE)) for _ in range(n)]
        self.rebuild()

    def clear(self):
        self.pts, self.root = [], None
        self.update()

    def rebuild(self):
        w, h = max(self.width(), 10), max(self.height(), 10)
        self.root = _QT(0, 0, float(w), float(h), 0)
        for i, pt in enumerate(self.pts):
            self.root.insert(i, self.pts)
        self.update()

    def resizeEvent(self, e):
        w, h = max(self.width(), 10), max(self.height(), 10)
        self.pts = [(min(max(x, 12), w - 12), min(max(y, 12), h - 12), c) for x, y, c in self.pts]
        self.rebuild()
        super().resizeEvent(e)

    def mouseMoveEvent(self, e): self.mouse = e.position(); self.update()
    def leaveEvent(self, e):     self.mouse = None; self.update()

    def mousePressEvent(self, e):
        self.pts.append((e.position().x(), e.position().y(), random.choice(PALETTE)))
        self.rebuild()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        if not self.root: return
        def draw(node):
            leaf = node.kids is None
            p.setPen(QPen(QColor(90, 140, 190, 150 if leaf else 70), 1))
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(node.x + 1, node.y + 1, node.w - 2, node.h - 2))
            if node.kids:
                for k in node.kids: draw(k)
        draw(self.root)
        cands, hits = [], []
        if self.mouse:
            m = self.mouse
            self.root.query(m.x() - self.R, m.y() - self.R, self.R * 2, self.R * 2, cands)
            hits = [i for i in cands
                    if (self.pts[i][0] - m.x()) ** 2 + (self.pts[i][1] - m.y()) ** 2 <= self.R ** 2]
        p.setPen(Qt.NoPen)
        for i, (x, y, c) in enumerate(self.pts):
            p.setBrush(QColor(c)); p.drawEllipse(QPointF(x, y), 5, 5)
        if self.mouse:
            m = self.mouse
            for i in cands:
                p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(C_ORANGE), 2))
                p.drawEllipse(QPointF(self.pts[i][0], self.pts[i][1]), 8, 8)
            for i in hits:
                p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(C_GREEN), 2))
                p.drawEllipse(QPointF(self.pts[i][0], self.pts[i][1]), 10, 10)
            p.setPen(QPen(_qc(C_ACCENT, 130), 1, Qt.DashLine))
            p.setBrush(QColor(79, 195, 247, 12))
            p.drawEllipse(m, self.R, self.R)
        nodes, depth = self.root.stats()
        p.setFont(mono(9)); p.setPen(QColor(C_TEXT))
        p.drawText(QPointF(12, 18), f"points {len(self.pts)} · tree nodes {nodes} · max depth {depth} · capacity 4/leaf")
        if self.mouse:
            p.setPen(QColor(C_ORANGE))
            p.drawText(QPointF(12, 34), f"query: {len(cands)} candidates (orange) → {len(hits)} real hits (green)")
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(12, self.height() - 8),
                   "click: add points and watch it subdivide · move mouse: the tree returns only nearby candidates")

class QuadtreeDiagram(QWidget):
    def __init__(self, bus):
        super().__init__()
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)
        v.addWidget(diag_header("Quadtree — the tree cousin of the hash grid",
            "The Broad-Phase Lab used a uniform grid; a quadtree adapts instead: any leaf holding more than 4 points subdivides into 4 children (up to depth 6). A query only visits nodes whose rectangle overlaps the search circle. It handles clustered points far better than a fixed grid would."))
        row = QHBoxLayout()
        s = QPushButton("Scatter 40"); s.clicked.connect(lambda: self.canvas.scatter(40))
        c = QPushButton("Clear"); c.clicked.connect(self.canvas.clear)
        row.addWidget(s); row.addWidget(c); row.addStretch(1)
        v.addLayout(row)
        self.canvas = _QTCanvas(self)
        v.addWidget(self.canvas, 1)

    def start(self):
        if not self.canvas.pts: self.canvas.scatter(40)

    def stop(self): pass


MIX_SOURCES = [("Music", C_PURPLE), ("Ambience", "#26c6da"), ("Explosion", C_ORANGE), ("Footsteps", C_GREEN)]
MIX_BUSES = [("Music bus", C_PURPLE), ("SFX bus", C_ORANGE)]
MIX_ROUTES = {0: 0, 1: 0, 2: 1, 3: 1}

class _MixCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.muted = {f"s{i}": False for i in range(4)}
        self.muted.update({f"b{i}": False for i in range(2)})
        self.muted["m"] = False
        self.dots, self.vu = [], defaultdict(float)
        self.cd = {0: 0.3, 1: 0.6, 2: 1.5, 3: 0.4}
        self.boxes = {}
        self.setMinimumHeight(320)
        self.setMouseTracking(True)
        self.timer = QTimer(self); self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)

    def _layout(self):
        w, h = self.width(), self.height()
        bw, bh = 118, 40
        cols = [14, w * 0.42, w * 0.64, max(w * 0.64 + 150, w - 140)]
        self.boxes = {}
        for i, (name, _) in enumerate(MIX_SOURCES):
            self.boxes[f"s{i}"] = QRectF(cols[0], 24 + i * (h - 60) / 3.4, bw, bh)
        for i, (name, _) in enumerate(MIX_BUSES):
            self.boxes[f"b{i}"] = QRectF(cols[1], h * (0.30 if i == 0 else 0.62), bw, bh)
        self.boxes["m"] = QRectF(cols[2], h * 0.45, bw, bh)
        self.boxes["out"] = QRectF(cols[3], h * 0.45, bw, bh)

    def _tick(self):
        dt = 0.033
        for k in self.cd: self.cd[k] -= dt
        spawns = []
        for i in range(4):
            if self.cd[i] <= 0 and not self.muted[f"s{i}"]:
                spawns.append(i)
                self.cd[i] = (random.uniform(2.2, 4.5) if i == 2 else
                              {0: 1.1, 1: 0.8, 3: 0.5}[i])
        if spawns and 2 in spawns:
            for _ in range(2): spawns.append(2)
        for s in spawns:
            b = MIX_ROUTES[s]
            path = [self.boxes[f"s{s}"].center(), self.boxes[f"b{b}"].center(),
                    self.boxes["m"].center(), self.boxes["out"].center()]
            self.dots.append({"path": path, "t": 0.0, "seg": 0,
                              "color": MIX_SOURCES[s][1], "src": s, "live": True})
        for d in self.dots:
            if not d["live"]: continue
            d["t"] += dt * 0.9
            if d["t"] >= 1.0:
                d["t"] = 0.0; d["seg"] += 1
                key = [None, f"b{MIX_ROUTES[d['src']]}", "m", "out"][min(d["seg"], 3)]
                if key: self.vu[key] = 1.0
                if d["seg"] >= 3: d["live"] = False
        self.dots = [d for d in self.dots if d["live"]]
        for k in self.vu:
            self.vu[k] = max(0.0, self.vu[k] - dt * 1.6)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        self._layout()
        wires = [(f"s{i}", f"b{b}") for i, b in MIX_ROUTES.items()] + [("b0", "m"), ("b1", "m"), ("m", "out")]
        p.setFont(mono(8))
        for a, b in wires:
            if a in self.boxes and b in self.boxes:
                muted = self.muted.get(b, False) or self.muted.get(a, False)
                p.setPen(QPen(QColor("#3a3d45") if muted else QColor("#4a5568"),
                              2, Qt.DashLine if muted else Qt.SolidLine))
                p.drawLine(self.boxes[a].center(), self.boxes[b].center())
        def box(key, label, color, can_mute=True):
            r = self.boxes[key]
            off = self.muted.get(key, False)
            p.setBrush(QColor(C_PANEL) if off else QColor("#243039"))
            p.setPen(QPen(QColor("#3a3d45") if off else QColor(color),
                          2 if self.vu.get(key, 0) > 0.3 else 1))
            p.drawRoundedRect(r, 7, 7)
            p.setPen(QColor(C_DIM if off else C_TEXT))
            p.drawText(r.adjusted(8, 4, -8, -12), Qt.AlignLeft | Qt.AlignVCenter, label)
            if can_mute:
                p.drawText(r.adjusted(0, 0, -7, -3), Qt.AlignRight | Qt.AlignBottom, "🔇" if off else "🔊")
            vh = (r.height() - 14) * min(1.0, self.vu.get(key, 0.0))
            if vh > 0:
                p.setBrush(QColor(C_GREEN)); p.setPen(Qt.NoPen)
                p.drawRect(QRectF(r.left() + 4, r.bottom() - 4 - vh, 4, vh))
        for i, (name, color) in enumerate(MIX_SOURCES): box(f"s{i}", name, color)
        for i, (name, color) in enumerate(MIX_BUSES): box(f"b{i}", name, color)
        box("m", "Master", C_ACCENT)
        box("out", "🔊 Output", C_DIM, can_mute=False)
        for d in self.dots:
            a = d["path"][d["seg"]]; b = d["path"][d["seg"] + 1]
            pos = QPointF(lerp(a.x(), b.x(), d["t"]), lerp(a.y(), b.y(), d["t"]))
            c = QColor(d["color"])
            p.setPen(Qt.NoPen)
            glow = QColor(c); glow.setAlpha(60)
            p.setBrush(glow); p.drawEllipse(pos, 8, 8)
            p.setBrush(c); p.drawEllipse(pos, 3.5, 3.5)
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(14, self.height() - 8),
                   "click any box to mute it · every source feeds a bus, buses feed the master — duck the SFX bus and every explosion drops at once")

    def mousePressEvent(self, e):
        for key in list(self.boxes):
            if key in self.muted and self.boxes[key].contains(e.position()):
                self.muted[key] = not self.muted[key]
                self.update(); break

    def mouseMoveEvent(self, e):
        over = any(key in self.muted and r.contains(e.position()) for key, r in self.boxes.items())
        self.setCursor(Qt.PointingHandCursor if over else Qt.ArrowCursor)

    def start(self):
        if not self.timer.isActive(): self.timer.start()

    def stop(self): self.timer.stop()

class AudioMixerDiagram(QWidget):
    def __init__(self, bus):
        super().__init__()
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)
        v.addWidget(diag_header("Audio mixer — sources, channels, buses",
            "Audio rarely routes 1:1. Sources feed channel groups (buses), buses feed the master. That's how one fader ducks ALL sound effects under a cutscene, how a reverb is inserted once on the SFX bus instead of per-sound, and how 3D sources get distance-attenuated before mixing. Mute the SFX bus and watch every explosion die at the bus."))
        self.canvas = _MixCanvas(self)
        v.addWidget(self.canvas, 1)

    def start(self): self.canvas.start()
    def stop(self): self.canvas.stop()


SG_PARTS = [
    ("hull",   "Hull",    None,     C_ACCENT),
    ("turret", "Turret",  "hull",   C_GREEN),
    ("barrel", "Barrel",  "turret", C_PINK),
    ("wl",     "Whl L",   "hull",   C_ORANGE),
    ("wr",     "Whl R",   "hull",   C_ORANGE),
]
SG_PARENT = {k: par for k, _, par, _ in SG_PARTS}
SG_LABEL  = {k: lab for k, lab, _, _ in SG_PARTS}
SG_COLOR  = {k: c for k, _, _, c in SG_PARTS}

class _SGCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.t, self.sel = 0.0, "barrel"
        self.recomp_total = 0
        self._hits = {}
        self.setMinimumHeight(330)
        self.timer = QTimer(self); self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)

    def _tick(self):
        self.t += 0.016
        if self.page.drive_cb.isChecked():
            self.recomp_total += 5 if self.page.graph_rb.isChecked() else 1
        self.update()

    def _layout(self, w, h):
        t, graph = self.t, self.page.graph_rb.isChecked()
        drive = self.page.drive_cb.isChecked()
        amp = min(110.0, w * 0.16)
        hx = w * 0.30 + (math.sin(t * 0.9) * amp if drive else 0.0)
        hy = h * 0.60
        spin = t * 1.3
        tx, ty = hx + 6, hy - 30
        bx, by = tx + math.cos(spin) * 34, ty + math.sin(spin) * 34 * 0.45
        if graph:
            return {"hull": (hx, hy), "turret": (tx, ty), "barrel": (bx, by),
                    "wl": (hx - 34, hy + 21), "wr": (hx + 34, hy + 21)}
        fx = w * 0.30
        return {"hull": (hx, hy), "turret": (fx + 6, ty),
                "barrel": (fx + 6 + math.cos(spin) * 34, ty + math.sin(spin) * 34 * 0.45),
                "wl": (fx - 34, hy + 21 + (math.sin(t * 8) * 2 if drive else 0)),
                "wr": (fx + 34, hy + 21 - (math.sin(t * 8) * 2 if drive else 0))}

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        graph, drive = self.page.graph_rb.isChecked(), self.page.drive_cb.isChecked()
        pos = self._layout(w, h)
        tx, ty = pos["turret"]; bx, by = pos["barrel"]
        self._hits = {"turret": QRectF(tx - 18, ty - 18, 36, 36),
                      "wl": QRectF(pos["wl"][0] - 11, pos["wl"][1] - 11, 22, 22),
                      "wr": QRectF(pos["wr"][0] - 11, pos["wr"][1] - 11, 22, 22),
                      "barrel": QRectF(min(tx, bx) - 8, min(ty, by) - 8,
                                       abs(bx - tx) + 16, abs(by - ty) + 16),
                      "hull": QRectF(pos["hull"][0] - 50, pos["hull"][1] - 18, 100, 36)}
        ix, iy = 16, 44
        if graph:
            nodepos = {"hull": (ix + 58, iy), "turret": (ix + 8, iy + 30),
                       "wl": (ix + 108, iy + 30), "wr": (ix + 162, iy + 30),
                       "barrel": (ix + 8, iy + 60)}
            for k, par in SG_PARENT.items():
                if par:
                    a, b = nodepos[par], nodepos[k]
                    p.setPen(QPen(_qc(C_YELLOW, 210) if drive else QColor(C_BORDER), 1))
                    p.drawLine(QPointF(a[0] + 20, a[1] + 15), QPointF(b[0] + 20, b[1]))
            for k, (nx, ny) in nodepos.items():
                hot = drive and SG_PARENT.get(k)
                p.setBrush(QColor("#332a15") if hot else QColor(C_PANEL))
                p.setPen(QPen(QColor(C_YELLOW) if hot else QColor(SG_COLOR[k]), 1))
                p.drawRect(QRectF(nx, ny, 40, 15))
                p.setPen(QColor(C_TEXT)); p.setFont(mono(7))
                p.drawText(QRectF(nx, ny, 40, 15), Qt.AlignCenter, SG_LABEL[k])
            p.setPen(QColor(C_DIM)); p.setFont(mono(7))
            p.drawText(QPointF(ix, iy - 6), "hierarchy · yellow = dirty (inherits root motion)")
        else:
            p.setPen(QColor(C_DIM)); p.setFont(mono(7))
            p.drawText(QPointF(ix, iy - 6), "flat — no parents, no cascade")
            for i2, (k, *_r) in enumerate(SG_PARTS):
                nx = ix + i2 * 46
                p.setBrush(QColor(C_PANEL)); p.setPen(QPen(QColor(SG_COLOR[k]), 1))
                p.drawRect(QRectF(nx, iy, 40, 15))
                p.setPen(QColor(C_TEXT))
                p.drawText(QRectF(nx, iy, 40, 15), Qt.AlignCenter, SG_LABEL[k])
        p.setPen(QPen(QColor(SG_COLOR["barrel"]), 7, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(tx, ty), QPointF(bx, by))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(SG_COLOR["hull"]))
        p.drawRoundedRect(QRectF(pos["hull"][0] - 48, pos["hull"][1] - 17, 96, 34), 6, 6)
        for k in ("wl", "wr"):
            p.setBrush(QColor(SG_COLOR[k]))
            p.drawEllipse(QPointF(*pos[k]), 10, 10)
        p.setBrush(QColor(SG_COLOR["turret"]))
        p.drawEllipse(QPointF(tx, ty), 17, 17)
        r = self._hits[self.sel]
        p.setBrush(Qt.NoBrush); p.setPen(QPen(_qc("#ffffff", 170), 2, Qt.DashLine))
        p.drawRoundedRect(r.adjusted(-4, -4, 4, 4), 8, 8)
        p.setFont(mono(9)); p.setPen(QColor(C_TEXT))
        p.drawText(QPointF(16, 22), f"mode: {'scene graph (hierarchy)' if graph else 'flat entities'}")
        p.setPen(QColor(C_YELLOW if drive else C_DIM))
        if drive:
            p.drawText(QPointF(16, h - 40),
                       f"moving the root recomputes {5 if graph else 1} transform(s)/frame" + ("   ← cascade!" if graph else ""))
            p.setPen(QColor(C_DIM))
            p.drawText(QPointF(16, h - 26), f"cumulative root-motion recomputes: {self.recomp_total}")
        else:
            p.drawText(QPointF(16, h - 40), "tick 'drive the tank' to move the root")
        chain, cur = [], self.sel
        while cur: chain.append(cur); cur = SG_PARENT.get(cur)
        p.setPen(QColor(SG_COLOR[self.sel])); p.setFont(mono(9))
        if graph:
            p.drawText(QPointF(16, h - 12),
                       f"{SG_LABEL[self.sel]}: world = " + " → ".join(SG_LABEL[c] for c in reversed(chain)))
        else:
            p.drawText(QPointF(16, h - 12), f"{SG_LABEL[self.sel]}: world = local (no parents)")
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(w - 250, h - 12), "click a part to inspect its chain")

    def mousePressEvent(self, e):
        for k, r in self._hits.items():
            if r.contains(e.position()):
                self.sel = k; self.update(); break

    def mouseMoveEvent(self, e):
        over = any(r.contains(e.position()) for r in self._hits.values())
        self.setCursor(Qt.PointingHandCursor if over else Qt.ArrowCursor)

    def start(self):
        if not self.timer.isActive(): self.timer.start()

    def stop(self): self.timer.stop()

class SceneGraphDiagram(QWidget):
    def __init__(self, bus):
        super().__init__()
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)
        v.addWidget(diag_header("Scene graph vs flat entities — who owns whom?",
            "A scene graph keeps parent/child links: move the Tank and the turret, barrel and wheels come along for free (world = parent × local). That coherence is why editors love hierarchies — but motion cascades: every descendant's world transform must be recomputed. Flat entities have no parents: moving the hull recomputes exactly one transform — but the compound object visibly falls apart unless hierarchy is re-added as an optional component."))
        row = QHBoxLayout()
        self.graph_rb = QRadioButton("scene graph — parent/child")
        self.flat_rb  = QRadioButton("flat entities — no hierarchy")
        self.graph_rb.setChecked(True)
        self.drive_cb = QCheckBox("drive the tank (move the root)")
        self.drive_cb.setChecked(True)
        row.addWidget(self.graph_rb); row.addWidget(self.flat_rb)
        row.addSpacing(18); row.addWidget(self.drive_cb); row.addStretch(1)
        v.addLayout(row)
        self.canvas = _SGCanvas(self)
        v.addWidget(self.canvas, 1)

    def start(self): self.canvas.start()
    def stop(self): self.canvas.stop()


JOB_PHASES = [
    [("UpdateTransforms", C_ACCENT, [70, 55, 90, 60]),
     ("Animate/Skin",     C_GREEN,  [80, 65]),
     ("Broadphase",       C_ORANGE, [60, 75, 50])],
    [("Frustum cull",    C_PURPLE, [45, 40, 50]),
     ("Build draw calls", C_PINK,   [70, 85, 60, 55]),
     ("Submit (GPU)",     C_YELLOW, [40])],
]
PHASE_NAMES = ["simulate", "render"]
THREAD_NAMES = ["Main", "W0", "W1", "W2"]

@dataclass
class _Job:
    label: str; dur: float; color: str

class _Worker:
    def __init__(self, name):
        self.name = name
        self.dq = deque()
        self.cur = None
        self.rem = 0.0
        self.busy = self.idle = 0.0
        self.idle_from = None

class _ThreadCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.t = 0.0
        self.workers = [_Worker(n) for n in THREAD_NAMES]
        self.phase = self.frame = 0
        self.blocks = deque(maxlen=400)
        self.idles  = deque(maxlen=400)
        self.bands  = deque(maxlen=60)
        self.bars   = deque(maxlen=40)
        self.steals = []
        self.steal_count = 0
        self.events = deque(maxlen=4)
        self._last_bus = 0.0
        self.setMinimumHeight(340)
        self.timer = QTimer(self); self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)
        self._open_frame()

    def _distribute(self, jobs):
        for i, job in enumerate(jobs):
            self.workers[i % len(self.workers)].dq.append(job)

    def _phase_jobs(self, pi):
        out = []
        for name, color, durs in JOB_PHASES[pi]:
            for ci, d in enumerate(durs):
                out.append(_Job(f"{name}#{ci}" if len(durs) > 1 else name, float(d), color))
        random.shuffle(out)
        return out

    def _open_frame(self):
        self.phase = 0
        self.bands.append((self.t, self.frame))
        self.bars.append((self.t, f"frame {self.frame}"))
        self._distribute(self._phase_jobs(0))

    def _advance(self):
        self.phase += 1
        if self.phase >= len(JOB_PHASES):
            self.frame += 1
            self._open_frame()
        else:
            self.bars.append((self.t, f"barrier → {PHASE_NAMES[self.phase]}"))
            self.events.appendleft(f"▸ barrier: {PHASE_NAMES[self.phase]} jobs released")
            self._distribute(self._phase_jobs(self.phase))

    def _tick(self):
        self.speed = self.page.speed_s.value() / 10.0
        dt = 16.0 * self.speed
        self.t += dt
        stealing = self.page.steal_cb.isChecked()
        all_idle = True
        for wi, w in enumerate(self.workers):
            if w.cur:
                all_idle = False
                w.rem -= dt; w.busy += dt
                if w.rem <= 0:
                    job, t0 = w.cur
                    self.blocks.append((wi, t0, self.t, job.label, job.color))
                    w.cur = None
            if w.cur is None:
                job = w.dq.popleft() if w.dq else None
                if job is None and stealing:
                    victim = max(range(len(self.workers)), key=lambda i: len(self.workers[i].dq))
                    if len(self.workers[victim].dq) > 1:
                        job = self.workers[victim].dq.pop()
                        self.steal_count += 1
                        self.steals.append([time.monotonic(), victim, wi, job.label])
                        self.events.appendleft(f"⚡ {w.name} stole {job.label} from {self.workers[victim].name}")
                        now = time.monotonic()
                        if now - self._last_bus > 0.6:
                            self._last_bus = now
                            self.page.bus.emit("job_stolen", thief=w.name,
                                               victim=self.workers[victim].name, job=job.label)
                if job is not None:
                    if w.idle_from is not None:
                        self.idles.append((wi, w.idle_from, self.t)); w.idle_from = None
                    w.cur = (job, self.t); w.rem = job.dur; all_idle = False
                else:
                    w.idle += dt
                    if w.idle_from is None: w.idle_from = self.t
        if all_idle:
            self._advance()

    def _job_rect(self, p, wi, x, x2, top, laneh, label, color, done):
        x = max(x, 4); x2 = min(x2, self.width() - 6)
        if x2 - x < 1: return
        r = QRectF(x, top + wi * laneh + 7, x2 - x, laneh - 14)
        c = QColor(color)
        if not done: c.setAlpha(190)
        p.setBrush(c); p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, 3, 3)
        if x2 - x > 44:
            p.setPen(QColor("#10151a")); p.setFont(mono(7))
            p.drawText(r.adjusted(3, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft,
                       label[:int((x2 - x) / 4.6)])

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        window = 5200.0
        t0v = self.t - window
        left, top = 54, 26
        laneh = (h - top - 84) / len(self.workers)
        pxms = (w - left - 12) / window
        bands = list(self.bands)
        for bi, (bt, fno) in enumerate(bands):
            nt = bands[bi + 1][0] if bi + 1 < len(bands) else self.t
            if nt < t0v: continue
            x = left + (bt - t0v) * pxms; x2 = left + (nt - t0v) * pxms
            if fno % 2 == 0:
                p.fillRect(QRectF(max(left, x), top, x2 - max(left, x), laneh * 4),
                           QColor(255, 255, 255, 6))
            p.setPen(QColor(C_BORDER))
            p.drawLine(QPointF(max(left, x), top), QPointF(max(left, x), top + laneh * 4))
            p.setPen(QColor(C_DIM)); p.setFont(mono(8))
            p.drawText(QPointF(max(left, x) + 4, top - 8), f"frame {fno}")
        for (bt, lbl) in list(self.bars):
            if bt < t0v: continue
            x = left + (bt - t0v) * pxms
            if x > w - 6: continue
            p.setPen(QPen(QColor("#5a6572"), 1, Qt.DashLine))
            p.drawLine(QPointF(x, top), QPointF(x, top + laneh * 4))
            p.setFont(mono(7)); p.setPen(QColor("#5a6572"))
            p.drawText(QPointF(x + 3, top + laneh * 4 + 10), lbl)
        for wi, wkr in enumerate(self.workers):
            y = top + wi * laneh
            p.setPen(QColor(C_TEXT)); p.setFont(self.font())
            p.drawText(QRectF(6, y, left - 10, laneh), Qt.AlignVCenter | Qt.AlignRight, wkr.name)
            p.setPen(QColor("#1c1f24"))
            p.drawLine(QPointF(left, y + laneh / 2), QPointF(w - 6, y + laneh / 2))
        for wi, i0, i1 in list(self.idles):
            if i1 < t0v: continue
            x = max(left, left + (i0 - t0v) * pxms); x2 = left + (i1 - t0v) * pxms
            p.fillRect(QRectF(x, top + wi * laneh + 7, x2 - x, laneh - 14), QColor("#33261f"))
        for wi, wkr in enumerate(self.workers):
            if wkr.idle_from is not None:
                x = max(left, left + (wkr.idle_from - t0v) * pxms)
                p.fillRect(QRectF(x, top + wi * laneh + 7, left + (self.t - t0v) * pxms - x, laneh - 14),
                           QColor("#33261f"))
        for (wi, b0, b1, label, color) in list(self.blocks):
            if b1 < t0v: continue
            self._job_rect(p, wi, left + (b0 - t0v) * pxms, left + (b1 - t0v) * pxms,
                           top, laneh, label, color, done=True)
        for wi, wkr in enumerate(self.workers):
            if wkr.cur:
                job, b0 = wkr.cur
                self._job_rect(p, wi, left + (b0 - t0v) * pxms, left + (self.t - t0v) * pxms,
                               top, laneh, job.label + "…", job.color, done=False)
        nowrt = time.monotonic()
        self.steals = [s for s in self.steals if nowrt - s[0] < 0.9][-8:]
        for rt, vf, vt, lab in self.steals:
            a = 1.0 - (nowrt - rt) / 0.9
            x = left + (self.t - t0v) * pxms
            y1 = top + vf * laneh + laneh / 2; y2 = top + vt * laneh + laneh / 2
            c = _qc(C_YELLOW, int(230 * a))
            p.setPen(QPen(c, 2)); p.drawLine(QPointF(x, y1), QPointF(x, y2))
            p.setBrush(c); p.setPen(Qt.NoPen); p.drawEllipse(QPointF(x, y2), 3.5, 3.5)
            p.setPen(c); p.setFont(mono(9)); p.drawText(QPointF(x + 6, (y1 + y2) / 2 + 4), "⚡")
        xnow = left + (self.t - t0v) * pxms
        p.setPen(QPen(_qc("#ffffff", 90), 1)); p.drawLine(QPointF(xnow, top), QPointF(xnow, top + laneh * 4))
        sy = h - 52
        parts = "  ".join(f"{w2.name} {100 * w2.busy / max(1e-6, w2.busy + w2.idle):.0f}%"
                          for w2 in self.workers)
        tot_idle = sum(w2.idle for w2 in self.workers) / 1000.0
        p.setPen(QColor(C_TEXT)); p.setFont(mono(9))
        p.drawText(QPointF(8, sy), f"utilization: {parts}   ·   idle total {tot_idle:.1f}s   ·   steals {self.steal_count}")
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(8, sy + 15),
                   "gray-brown = idle bubble (wasted core) · ⚡ = steal from the BACK of a victim deque (owner pops the front)")
        for i, txt in enumerate(list(self.events)[:3]):
            p.setPen(_qc(C_YELLOW, 220) if i == 0 else QColor(C_DIM))
            p.drawText(QPointF(w - 350, 16 + i * 13), txt)

    def start(self):
        if not self.timer.isActive(): self.timer.start()

    def stop(self): self.timer.stop()

class ThreadingDiagram(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)
        v.addWidget(diag_header("Job system — threads, phases & work stealing",
            "Each frame is split into small jobs grouped into phases with a barrier between them (fork–join). Four threads pull jobs from their own deques. With work stealing, an idle thread doesn't wait — it steals from the BACK of the busiest victim's deque (the owner pops from the front), keeping contention low. Toggle stealing off and watch gray idle bubbles balloon."))
        row = QHBoxLayout()
        self.steal_cb = QCheckBox("work stealing"); self.steal_cb.setChecked(True)
        row.addWidget(self.steal_cb); row.addWidget(QLabel("sim speed"))
        self.speed_s = QSlider(Qt.Horizontal); self.speed_s.setRange(5, 40); self.speed_s.setValue(22)
        row.addWidget(self.speed_s); row.addStretch(1)
        v.addLayout(row)
        self.canvas = _ThreadCanvas(self)
        v.addWidget(self.canvas, 1)

    def start(self): self.canvas.start()
    def stop(self): self.canvas.stop()


GB_OPAQUE = [
    (28, 34, 9,  C_ORANGE, 0.80, 0.35),
    (48, 24, 11, C_GREEN,  0.30, 0.75),
    (66, 38, 8,  C_PURPLE, 0.60, 0.55),
    (40, 47, 7,  C_ACCENT, 0.45, 0.90),
    (58, 16, 6,  C_PINK,   0.90, 0.50),
    (76, 26, 9,  C_YELLOW, 0.50, 0.65),
    (22, 18, 7,  "#26c6da", 0.70, 0.45),
]
GB_GHOST  = (52, 40, 12, "#e0e0e0", 0.20, 0.30)
GB_LIGHTS = [
    (34, 16, 26, "#ffd180"), (63, 42, 30, "#80d8ff"),
    (45, 30, 22, "#ff8a80"), (80, 12, 20, "#ccff90"),
]

class _GBCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.t = 0.0
        self.setMinimumHeight(430)
        self.timer = QTimer(self); self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)

    def _tick(self):
        self.t += 0.016
        self.update()

    def _shade(self, hexcol, ox, oy, lights, ghost):
        f = 0.35
        for (lx, ly, lr, _c) in lights:
            f += max(0.0, 1.0 - math.hypot(ox - lx, oy - ly) / lr) ** 1.5
        f = min(1.55, f)
        c = QColor(hexcol)
        return QColor(min(255, int(c.red() * f)), min(255, int(c.green() * f)),
                      min(255, int(c.blue() * f)), 120 if ghost else 255)

    def _panel(self, p, R, objs, kind, lights=None):
        p.fillRect(R, QColor({"albedo": "#141518", "normal": "#1a2030",
                              "rough": "#15171a", "depth": "#000000",
                              "mini": "#0c0d10"}[kind]))
        sx, sy = R.width() / 100.0, R.height() / 60.0
        items = sorted(objs, key=lambda o: o[5]) if kind == "depth" else objs
        for (ox, oy, r, col, rough, z, *rest) in items:
            ghost = bool(rest and rest[0])
            cx, cy, rr = R.left() + ox * sx, R.top() + oy * sy, r * sx
            if ghost:
                p.setBrush(Qt.NoBrush); p.setPen(QPen(_qc("#90a4ae", 150), 1, Qt.DashLine))
                p.drawEllipse(QPointF(cx, cy), rr, rr)
                p.setPen(_qc("#90a4ae", 200)); p.setFont(mono(7))
                p.drawText(QRectF(cx - rr, cy - 6, rr * 2, 12), Qt.AlignCenter, "✗")
                continue
            if kind == "albedo":   fill = QColor(col)
            elif kind == "normal":
                g = QRadialGradient(QPointF(cx - rr * 0.3, cy - rr * 0.35), rr * 1.6)
                g.setColorAt(0, QColor(185, 210, 255)); g.setColorAt(0.65, QColor(70, 100, 175))
                g.setColorAt(1, QColor(25, 40, 85))
                fill = QBrush(g)
            elif kind == "rough":
                gg = int(215 - rough * 175); fill = QColor(gg, gg, gg)
            elif kind == "depth":
                gg = int(45 + z * 195); fill = QColor(gg, gg, gg)
            else:
                fill = self._shade(col, ox, oy, lights or [], False)
            p.setBrush(fill); p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), rr, rr)

    def _draw_lights(self, p, SR, lights):
        sx, sy = SR.width() / 100.0, SR.height() / 60.0
        for i, (lx, ly, lr, lc) in enumerate(lights):
            jx = math.sin(self.t * 0.7 + i * 1.7) * 6 if i == 0 else 0
            jy = math.cos(self.t * 0.6 + i * 2.1) * 4 if i == 0 else 0
            cx, cy = SR.left() + (lx + jx) * sx, SR.top() + (ly + jy) * sy
            g = QRadialGradient(QPointF(cx, cy), lr * sx)
            g.setColorAt(0, _qc(lc, 80)); g.setColorAt(1, _qc(lc, 0))
            p.setBrush(QBrush(g)); p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), lr * sx, lr * sy)
            p.setBrush(QColor(lc)); p.drawEllipse(QPointF(cx, cy), 3, 3)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        deferred = self.page.defer_rb.isChecked()
        n_o = self.page.obj_s.value() - 1
        nl = self.page.light_s.value()
        opq = GB_OPAQUE[:n_o]
        active = opq + [GB_GHOST + (True,)]
        n_total = n_o + 1
        T = 5.0; k = (self.t % T) / T
        fill_k = min(1.0, k / 0.55)
        light_k = max(0.0, min(1.0, (k - 0.55) / 0.45))
        lights = GB_LIGHTS[:nl]
        SR = QRectF(12, 24, min(420.0, w * 0.40), h * 0.40)
        sx, sy = SR.width() / 100.0, SR.height() / 60.0
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(SR.left(), SR.top() - 6),
                   "final image — " + ("shaded as objects are drawn" if not deferred else "G-buffer, then lit"))
        if deferred:
            m = max(0, min(n_o, math.ceil((fill_k if k < 0.55 else 1.0) * n_o)))
            self._panel(p, SR, opq[:m], "albedo")
            if light_k > 0:
                p.save()
                p.setClipRect(QRectF(SR.left(), SR.top(), SR.width() * light_k, SR.height()))
                self._panel(p, SR, opq[:m], "mini", lights=lights)
                self._draw_lights(p, SR, lights)
                p.restore()
                sweep_x = SR.left() + SR.width() * light_k
                p.setPen(QPen(QColor(C_YELLOW), 2))
                p.drawLine(QPointF(sweep_x, SR.top()), QPointF(sweep_x, SR.bottom()))
                p.setPen(QColor(C_YELLOW)); p.setFont(mono(8))
                p.drawText(QPointF(min(sweep_x + 4, SR.right() - 140), SR.top() + 12),
                           "fullscreen lighting pass ▶")
        else:
            m = max(0, min(n_total, math.ceil(fill_k * n_total)))
            self._draw_lights(p, SR, lights)
            for oi in range(m):
                ox, oy, r, col, rough, z = active[oi][:6]
                ghost = oi == n_o
                cx, cy = SR.left() + ox * sx, SR.top() + oy * sy
                p.setBrush(self._shade(col, ox, oy, lights, ghost)); p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(cx, cy), r * sx, r * sy)
                if oi == m - 1 and fill_k < 1.0:
                    frac = fill_k * n_total - oi
                    if frac < 0.4:
                        p.setPen(QPen(_qc(C_YELLOW, int(200 * (0.4 - frac) / 0.4)), 1))
                        p.setBrush(Qt.NoBrush)
                        for (lx, ly, lr, lc) in lights:
                            p.drawLine(QPointF(cx, cy),
                                       QPointF(SR.left() + lx * sx, SR.top() + ly * sy))
        gx, gy = SR.left() + GB_GHOST[0] * sx, SR.top() + GB_GHOST[1] * sy
        p.setBrush(self._shade(GB_GHOST[3], GB_GHOST[0], GB_GHOST[1], lights, True))
        p.setPen(QPen(_qc("#b0bec5", 170), 1, Qt.DashLine))
        p.drawEllipse(QPointF(gx, gy), GB_GHOST[2] * sx, GB_GHOST[2] * sy)
        y0 = SR.bottom() + 20
        ph = max(90.0, h - y0 - 30)
        pw = (w - 24 - 3 * 8) / 4.0
        def titled(R, title):
            p.setPen(QPen(QColor(C_BORDER), 1)); p.drawRoundedRect(R, 6, 6)
            p.setPen(QColor(C_DIM)); p.setFont(mono(8))
            p.drawText(QPointF(R.left() + 2, R.bottom() + 12), title)
        if deferred:
            for i2, (kind, title) in enumerate([("albedo", "① albedo"), ("normal", "② normals"),
                                                ("rough", "③ roughness"), ("depth", "④ depth")]):
                R = QRectF(12 + i2 * (pw + 8), y0, pw, ph)
                m2 = max(0, min(n_o, math.ceil((fill_k if k < 0.55 else 1.0) * n_o)))
                self._panel(p, R, opq[:m2] + [GB_GHOST + (True,)], kind)
                titled(R, title + "  (full-screen target)")
        else:
            R1 = QRectF(12, y0, pw, ph)
            self._panel(p, R1, active[:m], "mini", lights=lights)
            titled(R1, "color target (shaded inline)")
            R2 = QRectF(12 + pw + 8, y0, pw, ph)
            self._panel(p, R2, active[:m], "depth")
            titled(R2, "depth")
            logR = QRectF(12 + 2 * (pw + 8), y0, 2 * pw + 8, ph)
            p.fillRect(logR, QColor("#101114")); titled(logR, "draw batches — each loops ALL lights")
            yy = logR.top() + 22
            for oi in range(m):
                ghost = oi == n_o
                p.fillRect(QRectF(logR.left() + 8, yy - 7, 8, 8),
                           QColor("#555555") if ghost else QColor(active[oi][3]))
                p.setPen(QColor(C_TEXT)); p.setFont(mono(8))
                p.drawText(QPointF(logR.left() + 22, yy),
                           f"draw {'ghost (transparent)' if ghost else f'object {oi+1}'} → {nl} lights")
                yy += 14
                if yy > logR.bottom() - 4: break
        SB = QRectF(SR.right() + 12, SR.top(), max(200.0, w - 24 - SR.width() - 12), SR.height())
        p.fillRect(SB, QColor(C_PANEL)); p.setPen(QPen(QColor(C_BORDER), 1))
        p.drawRoundedRect(SB, 8, 8)
        x = SB.left() + 12; y = SB.top() + 20
        p.setFont(mono(9)); p.setPen(QColor(C_DIM))
        p.drawText(QPointF(x, y), "cost per frame"); y += 22
        p.setPen(QColor(C_TEXT if not deferred else C_DIM))
        p.drawText(QPointF(x, y), f"forward: objects × lights = {n_o}×{nl} = {n_o*nl} pairs"); y += 18
        p.setPen(QColor(C_TEXT if deferred else C_DIM))
        p.drawText(QPointF(x, y), f"deferred: {nl} fullscreen light passes — objects free"); y += 24
        def bar(label, mb, colhex):
            nonlocal y
            p.setPen(QColor(C_DIM)); p.setFont(mono(8))
            p.drawText(QPointF(x, y), label); y += 12
            bw = SB.width() - 24
            p.setPen(QPen(QColor(C_BORDER), 1)); p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(x, y, bw, 8))
            p.setBrush(QColor(colhex)); p.setPen(Qt.NoPen)
            p.drawRect(QRectF(x + 1, y + 1, max(2.0, (bw - 2) * mb / 40.0), 6)); y += 20
        bar("G-buffer memory (deferred) ≈ 33 MB @1080p", 33, C_PURPLE if deferred else "#555555")
        bar("render targets (forward)  ≈ 16 MB", 16, C_PINK if not deferred else "#555555")
        y += 2; p.setFont(mono(8))
        if deferred:
            msg = ("① filling G-buffer…" if k < 0.55 else
                   f"② lighting pass… {light_k:.0%}" if light_k < 1 else "done — swap buffers")
            p.setPen(QColor(C_YELLOW)); p.drawText(QPointF(x, y), msg); y += 15
            p.setPen(QColor(C_ORANGE))
            p.drawText(QPointF(x, y), "⚠ ghost rejected → forward pass after")
        else:
            p.setPen(QColor(C_YELLOW))
            p.drawText(QPointF(x, y), f"drawing object {max(1, m)}/{n_total}, shading inline"); y += 15
            p.setPen(QColor(C_GREEN))
            p.drawText(QPointF(x, y), "✔ transparency handled inline")

    def start(self):
        if not self.timer.isActive(): self.timer.start()

    def stop(self): self.timer.stop()

class GBufferDiagram(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)
        v.addWidget(diag_header("Forward vs deferred — the G-buffer split",
            "Forward shading draws each object and immediately loops over every light — cost grows as objects × lights, and transparency is free. Deferred first fills full-screen G-buffers (albedo, normals, roughness, depth — note the ghost sphere rejected from every one), then lights the result in fullscreen passes — cost per light is constant no matter how many objects you add, at the price of memory bandwidth and a separate pass for transparents."))
        row = QHBoxLayout()
        self.defer_rb = QRadioButton("deferred (G-buffer)")
        self.fwd_rb = QRadioButton("forward")
        self.defer_rb.setChecked(True)
        self.defer_rb.toggled.connect(lambda on: on and self.bus.emit("render_mode", mode="deferred"))
        self.fwd_rb.toggled.connect(lambda on: on and self.bus.emit("render_mode", mode="forward"))
        row.addWidget(self.defer_rb); row.addWidget(self.fwd_rb); row.addSpacing(16)
        row.addWidget(QLabel("objects"))
        self.obj_s = QSlider(Qt.Horizontal); self.obj_s.setRange(3, 8); self.obj_s.setValue(6)
        self.obj_s.setMaximumWidth(110); row.addWidget(self.obj_s)
        row.addWidget(QLabel("lights"))
        self.light_s = QSlider(Qt.Horizontal); self.light_s.setRange(1, 4); self.light_s.setValue(3)
        self.light_s.setMaximumWidth(90); row.addWidget(self.light_s)
        row.addStretch(1)
        v.addLayout(row)
        self.canvas = _GBCanvas(self)
        v.addWidget(self.canvas, 1)

    def start(self): self.canvas.start()
    def stop(self): self.canvas.stop()


RAMP_STOPS = [(0.0, "#1565c0"), (0.35, "#26c6da"), (0.65, "#ffee58"), (1.0, "#ef5350")]

def ramp_color(t):
    t = max(0.0, min(1.0, t))
    for (t0, c0), (t1, c1) in zip(RAMP_STOPS, RAMP_STOPS[1:]):
        if t <= t1:
            k = (t - t0) / max(1e-6, t1 - t0)
            a, b = QColor(c0), QColor(c1)
            return QColor(int(a.red() + (b.red() - a.red()) * k),
                          int(a.green() + (b.green() - a.green()) * k),
                          int(a.blue() + (b.blue() - a.blue()) * k))
    return QColor(RAMP_STOPS[-1][1])

def _bary(px, py, ax, ay, bx, by, cx, cy):
    v0x, v0y = bx - ax, by - ay
    v1x, v1y = cx - ax, cy - ay
    v2x, v2y = px - ax, py - ay
    d00 = v0x * v0x + v0y * v0y
    d01 = v0x * v1x + v0y * v1y
    d11 = v1x * v1x + v1y * v1y
    d20 = v2x * v0x + v2y * v0y
    d21 = v2x * v1x + v2y * v1y
    den = d00 * d11 - d01 * d01
    if abs(den) < 1e-9: return None
    l1 = (d11 * d20 - d01 * d21) / den
    l2 = (d00 * d21 - d01 * d20) / den
    l0 = 1.0 - l1 - l2
    if l0 < -0.002 or l1 < -0.002 or l2 < -0.002: return None
    return l0, l1, l2

class _ShaderCanvas(QWidget):
    STAGES = [("① vertex shader — 3 vertices in → positions + attributes out", 1.3),
              ("② primitive assembly — vertices form a triangle, clipped to view", 0.9),
              ("③ rasterizer — barycentric coverage test spawns fragments", 1.8),
              ("④ fragment shader — every fragment shades interpolated attributes", 2.6)]

    def __init__(self, page):
        super().__init__()
        self.page = page
        self.tri = [QPointF(0.30, 0.22), QPointF(0.74, 0.30), QPointF(0.42, 0.80)]
        self.drag, self.probe = None, None
        self.t = self.stage = self.stage_t = 0
        self._img, self._img_key = None, None
        self.frags = 0
        self.setMinimumHeight(360)
        self.setMouseTracking(True)
        self.timer = QTimer(self); self.timer.setInterval(30)
        self.timer.timeout.connect(self._tick)

    def _tick(self):
        self.t += 0.03
        self.stage_t += 0.03
        if self.stage_t >= self.STAGES[self.stage][1]:
            self.stage_t = 0.0
            self.stage = (self.stage + 1) % 4
        self.update()

    def _geom(self):
        side = min((self.width() - 70) / 2.0, self.height() - 120)
        return QRectF(16, 34, side, side), QRectF(self.width() - 16 - side, 34, side, side), side

    def _vw(self, i):
        tilt = self.page.tilt_s.value() / 50.0
        pv = self.tri[i]
        d = min(1.0, math.hypot(pv.x() - 0.5, pv.y() - 0.5) / 0.7)
        return 1.0 + tilt * d

    def _vals(self):
        return [s.value() / 100.0 for s in self.page.val_sliders]

    def _shade(self, lam):
        vals, ws = self._vals(), [self._vw(i) for i in range(3)]
        aff = sum(l * v for l, v in zip(lam, vals))
        num = sum(l * v / w for l, v, w in zip(lam, vals, ws))
        den = sum(l / w for l, w in zip(lam, ws))
        return aff, num / max(1e-6, den)

    def _rebuild_img(self):
        vals, ws = self._vals(), [self._vw(i) for i in range(3)]
        N = 120
        img = QImage(N, N, QImage.Format_ARGB32)
        img.fill(0)
        pts = [(v.x() * N, v.y() * N) for v in self.tri]
        for j in range(N):
            for i in range(N):
                lam = _bary(i + 0.5, j + 0.5, *pts[0], *pts[1], *pts[2])
                if lam is None: continue
                _, pv = self._shade(lam)
                c = ramp_color(pv); c.setAlpha(255)
                img.setPixel(i, j, c.rgba())
        self._img = img
        self._img_key = (tuple(round(c, 3) for v in self.tri for c in (v.x(), v.y())),
                         tuple(vals), self.page.tilt_s.value())

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        L, R, side = self._geom()
        key_hint = (tuple(round(c, 3) for v in self.tri for c in (v.x(), v.y())),
                    tuple(self._vals()), self.page.tilt_s.value())
        if key_hint != self._img_key or self._img is None: self._rebuild_img()
        for vp, name in ((L, "vertex stage — smooth primitives"), (R, "fragment stage — raster grid")):
            p.setPen(QPen(QColor(C_BORDER), 1)); p.setBrush(QColor("#0c0d10"))
            p.drawRoundedRect(vp, 8, 8)
            p.setPen(QColor(C_DIM)); p.setFont(mono(8))
            p.drawText(QPointF(vp.left(), vp.top() - 8), name)
        p.drawImage(L, self._img)
        wpts = [QPointF(L.left() + v.x() * side, L.top() + v.y() * side) for v in self.tri]
        edge_col = QColor(C_ACCENT) if self.stage >= 1 else _qc(C_ACCENT, 70)
        p.setPen(QPen(edge_col, 2)); p.setBrush(Qt.NoBrush)
        p.drawPolygon(QPolygonF(wpts))
        vals, pulse = self._vals(), (math.sin(self.t * 6) + 1) / 2
        for i, wp in enumerate(wpts):
            if self.stage == 0:
                p.setBrush(Qt.NoBrush); p.setPen(QPen(_qc(C_YELLOW, int(160 * pulse)), 2))
                p.drawEllipse(wp, 13 + 3 * pulse, 13 + 3 * pulse)
            p.setBrush(ramp_color(vals[i])); p.setPen(QPen(QColor("white"), 2))
            p.drawEllipse(wp, 6, 6)
            p.setPen(QColor(C_TEXT)); p.setFont(mono(8))
            p.drawText(QPointF(wp.x() + 10, wp.y() - 8),
                       f"v{i}={vals[i]:.2f} 1/w={1.0/self._vw(i):.2f}")
        N = self.page.grid_s.value()
        cell = side / N
        p.setPen(QPen(QColor("#1a1d22"), 1))
        for k in range(N + 1):
            p.drawLine(QPointF(R.left() + k * cell, R.top()), QPointF(R.left() + k * cell, R.bottom()))
            p.drawLine(QPointF(R.left(), R.top() + k * cell), QPointF(R.right(), R.top() + k * cell))
        reveal = 1.0 if self.stage > 2 else (self.stage_t / self.STAGES[2][1] if self.stage == 2 else 0.0)
        total, idx, self.frags = N * N, 0, 0
        rpts = [(v.x(), v.y()) for v in self.tri]
        p.setPen(Qt.NoPen)
        for j in range(N):
            for i in range(N):
                idx += 1
                cx, cy = R.left() + (i + 0.5) * cell, R.top() + (j + 0.5) * cell
                lam = _bary(cx, cy, *rpts[0], *rpts[1], *rpts[2])
                if lam is None: continue
                self.frags += 1
                if idx / total > reveal: continue
                _, pv = self._shade(lam)
                p.setBrush(ramp_color(pv) if self.stage >= 3 else QColor("#dfe6ee"))
                p.drawRect(QRectF(cx - cell / 2 + 0.5, cy - cell / 2 + 0.5, cell - 1, cell - 1))
        p.setBrush(Qt.NoBrush); p.setPen(QPen(_qc(C_ACCENT, 120), 1, Qt.DashLine))
        p.drawPolygon(QPolygonF([QPointF(R.left() + v.x() * side, R.top() + v.y() * side) for v in self.tri]))
        if self.probe and R.contains(self.probe):
            u, v2 = ((self.probe.x() - R.left()) / side, (self.probe.y() - R.top()) / side)
            lam = _bary(u, v2, *rpts[0], *rpts[1], *rpts[2])
            if lam:
                aff, pv = self._shade(lam)
                p.setPen(QPen(QColor("white"), 1)); p.setBrush(Qt.NoBrush)
                p.drawEllipse(self.probe, 5, 5)
                p.drawLine(QPointF(self.probe.x() - 9, self.probe.y()), QPointF(self.probe.x() + 9, self.probe.y()))
                p.drawLine(QPointF(self.probe.x(), self.probe.y() - 9), QPointF(self.probe.x(), self.probe.y() + 9))
                bx = min(self.probe.x() + 12, R.right() - 176); by = min(self.probe.y() + 12, R.bottom() - 72)
                p.setBrush(QColor(10, 12, 16, 220)); p.setPen(QPen(QColor(C_BORDER), 1))
                p.drawRect(QRectF(bx, by, 168, 64))
                p.setFont(mono(8))
                p.setPen(QColor(C_DIM))
                p.drawText(QPointF(bx + 8, by + 14), f"λ {lam[0]:.2f} {lam[1]:.2f} {lam[2]:.2f}")
                p.setPen(QColor(C_RED))
                p.drawText(QPointF(bx + 8, by + 28), f"Δ {abs(aff - pv) / max(pv, 1e-6) * 100:5.1f}%")
                p.setPen(QColor(C_TEXT)); p.drawText(QPointF(bx + 8, by + 42), f"affine {aff:.3f}")
                p.setPen(QColor(C_GREEN)); p.drawText(QPointF(bx + 8, by + 56), f"persp  {pv:.3f}")
        p.setPen(QColor(C_YELLOW)); p.setFont(mono(10))
        p.drawText(QPointF(16, h - 46), self.STAGES[self.stage][0])
        p.setPen(QColor(C_DIM)); p.setFont(mono(9))
        p.drawText(QPointF(16, h - 28),
                   f"fragments: {self.frags}  (grid {N}×{N})  ·  3 vertices became {self.frags} fragments — the rasterizer is where workload explodes")
        p.drawText(QPointF(16, h - 12),
                   "drag vertices (left) · probe with the mouse (right) · tilt adds perspective: affine vs GPU-correct values diverge")

    def _vhit(self, pos):
        L, _, side = self._geom()
        for i, v in enumerate(self.tri):
            if QLineF(QPointF(L.left() + v.x() * side, L.top() + v.y() * side), pos).length() < 14:
                return i
        return None

    def mousePressEvent(self, e):
        self.drag = self._vhit(e.position())

    def mouseMoveEvent(self, e):
        L, R, side = self._geom()
        if self.drag is not None:
            self.tri[self.drag] = QPointF(
                min(0.95, max(0.05, (e.position().x() - L.left()) / side)),
                min(0.95, max(0.05, (e.position().y() - L.top()) / side)))
        self.probe = e.position() if R.contains(e.position()) else None
        self.update()

    def mouseReleaseEvent(self, e): self.drag = None

    def leaveEvent(self, e):
        self.probe = None; self.update()

    def start(self):
        if not self.timer.isActive(): self.timer.start()

    def stop(self): self.timer.stop()

class ShaderPipelineDiagram(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)
        v.addWidget(diag_header("Shader pipeline — vertices in, fragments out",
            "The vertex shader touches only 3 vertices, each carrying an attribute. The rasterizer asks, for every grid cell (fragment) the triangle covers: 'which blend of the 3 vertices am I?' — barycentric coordinates λ. Add tilt: real GPUs interpolate attributes perspective-correctly (weighted by 1/w); plain screen-space interpolation visibly diverges — the classic PS1 warping. Drag vertices, probe values, change the grid to see edge aliasing."))
        row = QHBoxLayout()
        row.addWidget(QLabel("grid"))
        self.grid_lbl = QLabel("22")
        self.grid_s = QSlider(Qt.Horizontal); self.grid_s.setRange(8, 40); self.grid_s.setValue(22)
        self.grid_s.setMaximumWidth(120)
        self.grid_s.valueChanged.connect(lambda val: (self.grid_lbl.setText(str(val)),
                                                      self.bus.emit("raster_resolution", cells=val)))
        row.addWidget(self.grid_s); row.addWidget(self.grid_lbl); row.addSpacing(16)
        row.addWidget(QLabel("perspective tilt"))
        self.tilt_lbl = QLabel("0.7")
        self.tilt_s = QSlider(Qt.Horizontal); self.tilt_s.setRange(0, 100); self.tilt_s.setValue(35)
        self.tilt_s.setMaximumWidth(120)
        self.tilt_s.valueChanged.connect(lambda val: self.tilt_lbl.setText(f"{val/50:.1f}"))
        row.addWidget(self.tilt_s); row.addWidget(self.tilt_lbl); row.addSpacing(16)
        self.val_sliders = []
        for i in range(3):
            row.addWidget(QLabel(f"v{i}"))
            s = QSlider(Qt.Horizontal); s.setRange(0, 100); s.setValue([10, 90, 50][i])
            s.setMaximumWidth(100); self.val_sliders.append(s); row.addWidget(s)
        row.addStretch(1)
        v.addLayout(row)
        self.canvas = _ShaderCanvas(self)
        v.addWidget(self.canvas, 1)

    def start(self): self.canvas.start()
    def stop(self): self.canvas.stop()


WALL_FRACS = [
    (0.03, 0.03, 0.94, 0.020), (0.03, 0.950, 0.94, 0.020),
    (0.03, 0.03, 0.020, 0.94), (0.950, 0.03, 0.020, 0.94),
    (0.30, 0.10, 0.015, 0.42),
    (0.52, 0.45, 0.40, 0.015),
    (0.62, 0.58, 0.015, 0.30),
    (0.70, 0.15, 0.16, 0.015),
]

def _in_poly(x, y, poly):
    inside, n, j = False, len(poly), len(poly) - 1
    for i in range(n):
        xi, yi = poly[i].x(), poly[i].y()
        xj, yj = poly[j].x(), poly[j].y()
        if (yi > y) != (yj > y):
            xint = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < xint: inside = not inside
        j = i
    return inside

class _OcclCanvas(QWidget):
    FOV = math.radians(70.0)

    def __init__(self, page):
        super().__init__()
        self.page = page
        self.rects, self.segs, self.poly = [], [], []
        self.eye, self.aim = None, 0.0
        self.objs, self.drag = [], False
        self.saved, self._last_emit = 0, 0.0
        self.count = (0, 0, 0, 0)
        self._scattered = False
        self.setMinimumHeight(360)
        self.setMouseTracking(True)
        self.timer = QTimer(self); self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)

    def resizeEvent(self, e):
        w, h = max(self.width(), 60), max(self.height(), 60)
        self.rects = [QRectF(fx * w, fy * h, fw * w, fh * h) for fx, fy, fw, fh in WALL_FRACS]
        self.segs = []
        for r in self.rects:
            x0, y0, x1, y1 = r.left(), r.top(), r.right(), r.bottom()
            self.segs += [(x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)]
        if self.eye is None: self.eye = QPointF(w * 0.14, h * 0.72)
        self.eye = QPointF(min(max(20, self.eye.x()), w - 20), min(max(20, self.eye.y()), h - 20))
        if not self._scattered:
            self.scatter(42); self._scattered = True
        super().resizeEvent(e)

    def scatter(self, n):
        w, h = max(self.width(), 60), max(self.height(), 60)
        self.objs = []
        for _ in range(n):
            ang, spd = random.uniform(0, 2 * math.pi), random.uniform(8, 22)
            self.objs.append([random.uniform(30, w - 30), random.uniform(30, h - 30),
                              math.cos(ang) * spd, math.sin(ang) * spd, random.choice(PALETTE)])

    @staticmethod
    def _ray_seg(px, py, dx, dy, ax, ay, bx, by):
        sx, sy = bx - ax, by - ay
        den = dx * sy - dy * sx
        if abs(den) < 1e-9: return None
        t = ((ax - px) * sy - (ay - py) * sx) / den
        u = ((ax - px) * dy - (ay - py) * dx) / den
        if t > 1e-4 and 0.0 <= u <= 1.0: return t
        return None

    def _vispoly(self):
        w, h = self.width(), self.height()
        maxd = math.hypot(w, h)
        ex, ey = self.eye.x(), self.eye.y()
        angs = [self.aim - self.FOV / 2, self.aim + self.FOV / 2]
        for r in self.rects:
            for cx, cy in ((r.left(), r.top()), (r.right(), r.top()),
                           (r.right(), r.bottom()), (r.left(), r.bottom())):
                a = math.atan2(cy - ey, cx - ex)
                d = math.atan2(math.sin(a - self.aim), math.cos(a - self.aim))
                if abs(d) <= self.FOV / 2 + 0.06:
                    angs += [a - 0.0008, a + 0.0008]
        pts = []
        for a in sorted(angs):
            dx, dy = math.cos(a), math.sin(a)
            best = maxd
            for (ax, ay, bx, by) in self.segs:
                t = self._ray_seg(ex, ey, dx, dy, ax, ay, bx, by)
                if t is not None and t < best: best = t
            pts.append(QPointF(ex + dx * best, ey + dy * best))
        return pts, maxd

    def _tick(self):
        w, h = self.width(), self.height()
        dt = 0.033
        for o in self.objs:
            o[0] += o[2] * dt; o[1] += o[3] * dt
            if o[0] < 26 or o[0] > w - 26: o[2] = -o[2]
            if o[1] < 26 or o[1] > h - 26: o[3] = -o[3]
        pts, maxd = self._vispoly()
        self.poly = pts
        occ_mode = self.page.occl_rb.isChecked()
        half = self.FOV / 2
        in_f = vis = occ = 0
        for o in self.objs:
            dx, dy = o[0] - self.eye.x(), o[1] - self.eye.y()
            dist = math.hypot(dx, dy)
            ad = math.atan2(math.sin(math.atan2(dy, dx) - self.aim),
                            math.cos(math.atan2(dy, dx) - self.aim))
            o_in = dist <= maxd and abs(ad) <= half + 0.02
            o_vis = o_in and (not occ_mode or _in_poly(o[0], o[1], pts))
            if len(o) == 5:
                o.append(o_in); o.append(o_vis)
            else:
                o[5], o[6] = o_in, o_vis
            if o_in:
                in_f += 1
                if o_vis: vis += 1
                else: occ += 1
        if occ_mode:
            self.saved += occ
            now = time.monotonic()
            if now - self._last_emit > 1.0 and occ:
                self._last_emit = now
                self.page.bus.emit("occluded_stats", saved=self.saved)
        self.count = (len(self.objs), in_f, vis, occ)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        occ_mode = self.page.occl_rb.isChecked()
        for r in self.rects:
            p.setBrush(QColor("#2a2f38")); p.setPen(QPen(QColor("#4a5568"), 1))
            p.drawRoundedRect(r, 2, 2)
        if occ_mode and len(self.poly) > 2:
            poly = QPolygonF([QPointF(self.eye)] + self.poly)
            p.setBrush(QColor(79, 195, 247, 24)); p.setPen(QPen(_qc(C_ACCENT, 110), 1))
            p.drawPolygon(poly)
        else:
            maxd = math.hypot(self.width(), self.height())
            p.setPen(QPen(_qc(C_ACCENT, 90), 1, Qt.DashLine))
            for s in (-1, 1):
                a = self.aim + s * self.FOV / 2
                p.drawLine(self.eye, QPointF(self.eye.x() + math.cos(a) * maxd,
                                             self.eye.y() + math.sin(a) * maxd))
        for o in self.objs:
            pos = QPointF(o[0], o[1])
            o_in, o_vis = o[5], o[6]
            if not o_in:
                p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor("#33373d"), 1))
                p.drawEllipse(pos, 5, 5)
            elif o_vis:
                p.setBrush(QColor(o[4])); p.setPen(Qt.NoPen)
                p.drawEllipse(pos, 5.5, 5.5)
            else:
                p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(C_ORANGE), 1.5, Qt.DashLine))
                p.drawEllipse(pos, 7, 7)
                p.setPen(QColor(C_ORANGE)); p.setFont(mono(7))
                p.drawText(QPointF(o[0] - 3, o[1] + 3), "✗")
        p.setBrush(QColor(C_ACCENT)); p.setPen(QPen(QColor("white"), 2))
        p.drawEllipse(self.eye, 8, 8)
        p.setPen(QPen(QColor("white"), 2))
        p.drawLine(self.eye, QPointF(self.eye.x() + math.cos(self.aim) * 18,
                                     self.eye.y() + math.sin(self.aim) * 18))
        n, inf, vis, occ = self.count
        p.setFont(mono(9)); p.setPen(QColor(C_TEXT))
        p.drawText(QPointF(14, 20), f"objects {n} · in frustum {inf} · visible {vis}" +
                   (f" · occluded {occ}" if occ_mode else ""))
        p.setPen(QColor(C_GREEN if occ_mode else C_DIM))
        p.drawText(QPointF(14, 36),
                   f"occlusion draw-calls saved (cumulative): {self.saved}" if occ_mode
                   else "occlusion OFF — every frustum object becomes a draw call, walls are ignored")
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(14, self.height() - 10),
                   "move the mouse to aim the eye · drag the eye around corners · walls block the light-cone: behind them = occluded")

    def mouseMoveEvent(self, e):
        if self.drag:
            self.eye = QPointF(max(20, min(self.width() - 20, e.position().x())),
                               max(20, min(self.height() - 20, e.position().y())))
        dx, dy = e.position().x() - self.eye.x(), e.position().y() - self.eye.y()
        if dx * dx + dy * dy > 4: self.aim = math.atan2(dy, dx)
        self.update()

    def mousePressEvent(self, e):
        self.drag = QLineF(self.eye, e.position()).length() < 20

    def mouseReleaseEvent(self, e): self.drag = False

    def start(self):
        if not self.timer.isActive(): self.timer.start()

    def stop(self): self.timer.stop()

class OcclusionDiagram(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)
        v.addWidget(diag_header("Occlusion culling — the frustum isn't enough",
            "Frustum culling rejects what the camera can't see; occlusion culling also rejects what it CAN'T SEE BECAUSE SOMETHING IS IN FRONT OF IT. This diagram computes a real visibility polygon by ray-casting to every wall corner — only objects inside that polygon survive. Toggle occlusion off: hidden objects get drawn anyway (overdraw). Portals, BSPs and Hi-Z buffers are just faster ways to answer this same visibility question in 3D."))
        row = QHBoxLayout()
        self.occl_rb = QRadioButton("frustum + occlusion culling")
        self.frustum_rb = QRadioButton("frustum culling only")
        self.occl_rb.setChecked(True)
        sc = QPushButton("↻ Scatter objects"); sc.clicked.connect(lambda: self.canvas.scatter(42))
        row.addWidget(self.occl_rb); row.addWidget(self.frustum_rb)
        row.addSpacing(16); row.addWidget(sc); row.addStretch(1)
        v.addLayout(row)
        self.canvas = _OcclCanvas(self)
        v.addWidget(self.canvas, 1)

    def start(self): self.canvas.start()
    def stop(self): self.canvas.stop()


TICK_MS = 50.0

class _NetCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.now, self.tick_acc, self.seq = 0.0, 0.0, 0
        self.packets, self.delivered = [], deque()
        self.samples = deque(maxlen=420)
        self.received = self.dropped = 0
        self.cum_interp, self._last_emit, self.starved = 0.0, 0.0, False
        self.cur_v, self.cur_mode = 0.5, True
        self.setMinimumHeight(430)
        self.timer = QTimer(self); self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)

    def _truth(self, t):
        return 0.5 + 0.40 * math.sin(t * 0.0016) + 0.10 * math.sin(t * 0.00063 + 1.7)

    def _tick(self):
        pg = self.page
        self.now += 33.0
        self.tick_acc += 33.0
        while self.tick_acc >= TICK_MS:
            self.tick_acc -= TICK_MS
            self.seq += 1
            jit = pg.jit_s.value()
            lat = max(20.0, pg.lat_s.value() + random.uniform(-jit, jit))
            drop = random.random() * 100 < pg.loss_s.value()
            self.packets.append(dict(seq=self.seq, send=self.now, arrive=self.now + lat,
                                     drop=drop, val=self._truth(self.now)))
        for pk in self.packets[:]:
            if self.now >= pk["arrive"]:
                if pk["drop"]: self.dropped += 1
                else:
                    self.delivered.append((pk["send"], pk["val"], pk["arrive"]))
                    self.received += 1
                self.packets.remove(pk)
        while self.delivered and self.delivered[0][2] < self.now - 2600:
            self.delivered.popleft()
        d = self.delivered
        mode = pg.interp_cb.isChecked()
        self.starved = False
        if not d:
            v = self._truth(self.now)
        elif mode:
            target = d[-1][0] - pg.delay_s.value()
            v, self.starved = d[0][1], target < d[0][0]
            if not self.starved:
                for i in range(len(d) - 1):
                    t1, v1, _ = d[i]; t2, v2, _ = d[i + 1]
                    if t1 <= target <= t2:
                        v = v1 + (v2 - v1) * (target - t1) / max(1e-6, t2 - t1)
                        break
        else:
            v = d[-1][1]
        self.samples.append((self.now, v, mode))
        if mode: self.cum_interp += 0.033
        if self.now - self._last_emit > 5.0:
            self._last_emit = self.now
            pg.bus.emit("net_stats", interp_secs=int(self.cum_interp),
                        delay=pg.delay_s.value(), loss=pg.loss_s.value())
        self.cur_v, self.cur_mode = v, mode
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        W = 3000.0; t0 = self.now - W
        L, Rm = 10, 12
        def xs(t): return L + (t - t0) / W * (w - L - Rm)
        def vy(b0, b1, val): return b1 - max(0.0, min(1.0, val)) * (b1 - b0)
        yS0, yS1 = 34, 86
        yN0, yN1 = 96, 150
        yC0, yC1 = 160, 212
        ch0, ch1 = yC1 + 22, h - 52
        p.setFont(mono(8)); p.setPen(QColor(C_DIM))
        p.drawText(QPointF(L, yS0 - 6), "SERVER — truth @ 20 Hz (snapshot every tick)")
        p.drawText(QPointF(L, yN0 - 6), "NETWORK — latency ± jitter (✗ = dropped)")
        p.drawText(QPointF(L, yC0 - 6), "CLIENT — received snapshot buffer (render point)")
        for (b0, b1) in ((yS0, yS1), (yN0, yN1), (yC0, yC1), (ch0, ch1)):
            p.setPen(QPen(QColor("#1c1f24"), 1))
            p.drawLine(QPointF(L, (b0 + b1) / 2), QPointF(w - Rm, (b0 + b1) / 2))
        pts = [QPointF(xs(t), vy(yS0, yS1, self._truth(t)))
               for t in [t0 + i * W / 120 for i in range(121)]]
        p.setPen(QPen(QColor("#5a6572"), 1.5)); p.drawPolyline(QPolygonF(pts))
        p.setBrush(QColor(C_ACCENT)); p.setPen(Qt.NoPen)
        for (tk, _v, _a) in self.delivered:
            if t0 < tk: p.drawEllipse(QPointF(xs(tk), vy(yS0, yS1, self._truth(tk))), 2.2, 2.2)
        f = mono(8)
        for pk in self.packets:
            k = max(0.0, min(1.0, (self.now - pk["send"]) / max(1e-6, pk["arrive"] - pk["send"])))
            x = lerp(xs(pk["send"]), xs(pk["arrive"]), k)
            y = lerp(yS1, yC0, k)
            if pk["drop"]:
                p.setPen(QPen(_qc(C_RED, 190), 1)); p.setBrush(Qt.NoBrush)
                p.drawEllipse(QPointF(x, y), 5, 5)
                p.setFont(f)
                p.drawText(QPointF(x - 3, y + 3), "✗")
                p.setBrush(QColor(C_ACCENT)); p.setPen(Qt.NoPen)
            else:
                p.drawEllipse(QPointF(x, y), 4, 4)
        d = self.delivered
        p.setBrush(QColor(C_ACCENT)); p.setPen(Qt.NoPen)
        for (tk, val, arr) in d:
            if t0 < arr: p.drawRect(QRectF(xs(arr) - 2.5, vy(yC0, yC1, val) - 2.5, 5, 5))
        if d:
            la = d[-1][2]; delay = self.page.delay_s.value()
            x1, x2 = xs(la - delay), xs(la)
            p.setBrush(QColor(255, 209, 102, 26)); p.setPen(QPen(_qc(C_YELLOW, 120), 1, Qt.DashLine))
            p.drawRect(QRectF(x1, yC0, x2 - x1, yC1 - yC0))
            p.setPen(QColor(C_YELLOW)); p.setFont(f)
            p.drawText(QPointF(x1, yC0 - 2), f"⏱ render {delay} ms behind newest")
            p.setPen(QPen(QColor(C_YELLOW), 1)); p.drawLine(QPointF(x2, yC0), QPointF(x2, yC1))
        p.setFont(mono(8)); p.setPen(QColor(C_DIM))
        p.drawText(QPointF(L, ch0 - 6), "position over time — gray = server truth · green = interpolated · red = raw latest (staircase)")
        gt = [QPointF(xs(t), vy(ch0, ch1, self._truth(t))) for t in [t0 + i * W / 120 for i in range(121)]]
        p.setPen(QPen(QColor("#4a5568"), 1)); p.drawPolyline(QPolygonF(gt))
        runs, cur = [], []
        for s in self.samples:
            if t0 < s[0]:
                if cur and cur[-1][2] != s[2]: runs.append(cur); cur = []
                cur.append(s)
        if cur: runs.append(cur)
        for run in runs:
            col = C_GREEN if run[0][2] else C_RED
            p.setPen(QPen(QColor(col), 2))
            p.drawPolyline(QPolygonF([QPointF(xs(t), vy(ch0, ch1, v)) for t, v, _m in run]))
        p.setBrush(QColor(C_GREEN if self.cur_mode else C_RED)); p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(xs(self.now - 8), vy(ch0, ch1, self.cur_v)), 4, 4)
        pg = self.page
        p.setFont(mono(9))
        p.setPen(QColor(C_TEXT))
        p.drawText(QPointF(L, h - 30),
                   f"tick 20 Hz · latency {pg.lat_s.value()} ± {pg.jit_s.value()} ms · loss {pg.loss_s.value()}% · "
                   f"received {self.received} · dropped {self.dropped}")
        if pg.interp_cb.isChecked():
            msg = (f"interpolation ON — rendering {pg.delay_s.value()} ms in the past · display lags truth ≈ "
                   f"{pg.lat_s.value() + pg.delay_s.value()} ms")
            if self.starved:
                p.setPen(QColor(C_RED)); p.drawText(QPointF(L, h - 12),
                    msg + "   ⚠ BUFFER UNDERRUN — jitter/loss exceeded the delay")
            else:
                p.setPen(QColor(C_GREEN)); p.drawText(QPointF(L, h - 12), msg)
        else:
            p.setPen(QColor(C_RED)); p.drawText(QPointF(L, h - 12),
                "interpolation OFF — rendering the newest raw snapshot: every jitter/drop is a visible teleport")

    def start(self):
        if not self.timer.isActive(): self.timer.start()

    def stop(self): self.timer.stop()

class NetDiagram(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)
        v.addWidget(diag_header("Snapshot interpolation — render the past, feel the present",
            "Multiplayer servers simulate at 20 Hz; the network adds latency, jitter and loss. Naively rendering the newest arriving snapshot gives a staircase with teleport gaps. The fix: buffer snapshots and render a sliding window ~100 ms INTO THE PAST, interpolating between the two snapshots that bracket the render time. Push loss/jitter up or the delay down and watch buffer underruns — the classic tuning trade-off."))
        row = QHBoxLayout()
        for label, lo, hi, val in (("latency", 20, 400, 140), ("jitter", 0, 120, 40),
                                   ("loss %", 0, 30, 5), ("interp delay", 30, 300, 100)):
            row.addWidget(QLabel(label))
            s = _mk_slider(lo, hi, val)
            setattr(self, label.split()[0].lower() + "_s", s)
            row.addWidget(s)
        self.lat_s = self.latency_s; self.jit_s = self.jitter_s
        self.loss_s = self.loss_s if hasattr(self, "loss_s") else self.loss_s
        self.delay_s = self.interp_s
        self.interp_cb = QCheckBox("interpolate"); self.interp_cb.setChecked(True)
        row.addSpacing(10); row.addWidget(self.interp_cb); row.addStretch(1)
        v.addLayout(row)
        self.canvas = _NetCanvas(self)
        v.addWidget(self.canvas, 1)

    def start(self): self.canvas.start()
    def stop(self): self.canvas.stop()


MOD_LAYERS = [
    dict(key="base",  label="base/game.toml",   color=C_DIM,    vals={"damage": 10, "model": "sword_basic", "sound": "clank.wav", "fire_chance": 0.0}),
    dict(key="patch", label="patch_1.02.toml",  color=C_ACCENT, vals={"damage": 12}),
    dict(key="sharp", label="mod_sharper.toml", color=C_GREEN,  vals={"damage": 25, "sound": "shing.wav"}),
    dict(key="fire",  label="mod_fire.toml",    color=C_ORANGE, vals={"fire_chance": 0.35, "model": "sword_fire"}),
]
MOD_KEYS  = ["damage", "model", "sound", "fire_chance"]

class _ModCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.t, self.sweep = 0.0, 0
        self.flashes = {}
        self._rects = {}
        self.setMinimumHeight(340)
        self.timer = QTimer(self); self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)

    def _tick(self):
        self.t += 0.033
        self.sweep = (self.sweep + 1) % len(MOD_KEYS)
        for k in list(self.flashes):
            self.flashes[k] -= 0.05
            if self.flashes[k] <= 0: del self.flashes[k]
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        order = self.page.order
        enabled = self.page.enabled
        lw, lh_, gap = 236, 46, 10
        x0 = 24
        y0 = h - 24 - lh_
        defs = {L["key"]: L for L in MOD_LAYERS}
        for li, key in enumerate(order):
            L = defs[key]
            y = y0 - li * (lh_ + gap)
            on = enabled.get(key, True)
            r = QRectF(x0, y, lw, lh_)
            self._rects[key] = r
            p.setBrush(QColor("#243039") if on else QColor(C_PANEL))
            p.setPen(QPen(QColor(L["color"]), 1, Qt.SolidLine if on else Qt.DashLine))
            p.drawRoundedRect(r, 7, 7)
            p.setPen(QColor(C_TEXT if on else C_DIM)); p.setFont(self.font())
            p.drawText(r.adjusted(10, 5, -8, -20), Qt.AlignLeft | Qt.AlignVCenter,
                       ("" if on else "✗ ") + L["label"])
            p.setPen(QColor(L["color"]) if on else QColor(C_DIM)); p.setFont(mono(7))
            p.drawText(r.adjusted(10, 20, -8, -4), Qt.AlignLeft | Qt.AlignVCenter, ", ".join(L["vals"]))
            p.setPen(QColor(C_DIM)); p.setFont(mono(8))
            p.drawText(QPointF(x0 + lw + 8, y + lh_ / 2 + 3),
                       "loads last — wins conflicts" if li == len(order) - 1
                       else ("loads first (base)" if li == 0 else f"load order {li}"))
        key = MOD_KEYS[self.sweep]
        winner = self.page.resolve(key)
        prog = (self.t % 1.2) / 1.2
        p.setFont(mono(9)); p.setPen(QColor(C_YELLOW))
        p.drawText(QPointF(x0, y0 + lh_ + 34), f"lookup: {key}  →  {winner[1]}  (from {winner[2]})")
        for li, lkey in enumerate(order):
            if not enabled.get(lkey, True): continue
            y_center = y0 - li * (lh_ + gap) + lh_ / 2
            if prog * len(order) > li and defs[lkey].get(key) is not None:
                p.setBrush(QColor(C_YELLOW) if lkey == winner[2] else QColor(C_DIM))
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(x0 + lw - 14, y_center - 14), 4 if lkey == winner[2] else 3, 4)
        tx = x0 + lw + 190
        p.setPen(QColor(C_TEXT)); p.setFont(mono(10))
        p.drawText(QPointF(tx, 28), "resolved item")
        p.setFont(mono(9))
        for ki, key in enumerate(MOD_KEYS):
            y = 48 + ki * 40
            val, vkey, lkey = self.page.resolve(key)
            p.setPen(QColor(C_DIM)); p.drawText(QPointF(tx, y), key)
            col = defs[lkey]["color"] if lkey else C_DIM
            p.setBrush(QColor(col)); p.setPen(Qt.NoPen)
            p.drawRect(QRectF(tx + 108, y - 10, 8, 8))
            p.setPen(QColor(C_TEXT))
            p.drawText(QPointF(tx + 124, y), f"{val:.2f}" if isinstance(val, float) else str(val))
            p.setPen(QColor(C_DIM)); p.setFont(mono(7))
            p.drawText(QPointF(tx + 124, y + 13), f"← {lkey}")
            p.setFont(mono(9))
            shadowed = [defs[o]["label"] for o in order
                        if o != lkey and enabled.get(o, True) and defs[o].get(key) is not None]
            if shadowed:
                p.setPen(QColor(C_RED)); p.setFont(mono(7))
                p.drawText(QPointF(tx + 240, y), "⚔ shadowed: " + ", ".join(shadowed))
                p.setFont(mono(9))
        dmg = self.page.resolve("damage")[0]
        by = 48 + len(MOD_KEYS) * 40 + 6
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(tx, by), f"resolved damage ({dmg} of base 10 = ×{dmg/10:.1f})")
        p.setPen(QPen(QColor(C_BORDER), 1)); p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(tx, by + 8, 200, 10))
        p.setBrush(QColor(C_ORANGE)); p.setPen(Qt.NoPen)
        p.drawRect(QRectF(tx + 1, by + 9, max(2, 198 * min(1.0, dmg / 40)), 8))
        p.setPen(QColor(C_DIM))
        p.drawLine(QPointF(tx + 1 + 198 * 10 / 40, by + 4), QPointF(tx + 1 + 198 * 10 / 40, by + 22))

    def start(self):
        if not self.timer.isActive(): self.timer.start()

    def stop(self): self.timer.stop()

class ModdingDiagram(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.order = ["base", "patch", "sharp", "fire"]
        self.enabled = {"base": True, "patch": True, "sharp": False, "fire": False}
        self._last_emit = 0.0
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)
        v.addWidget(diag_header("Modding & data-driven design — the override stack",
            "Data-driven games keep tunables in files, not code. At boot, layers merge: base → official patch → mods, each later layer overriding keys defined earlier. Reorder the mods and the winner changes without touching either file. Conflicts aren't errors; load order IS the policy."))
        row = QHBoxLayout()
        row.addWidget(QLabel("load order:"))
        self.order_lbl = QLabel(); self.order_lbl.setFont(mono(9))
        row.addWidget(self.order_lbl); row.addStretch(1)
        for key in ("patch", "sharp", "fire"):
            cb = QCheckBox(key); cb.setChecked(self.enabled[key])
            cb.toggled.connect(lambda on, k=key: self._toggle(k, on))
            row.addWidget(cb)
            up = QPushButton("↑"); up.setFixedWidth(26); up.setToolTip("load later (higher priority)")
            up.clicked.connect(lambda _=False, k=key: self._move(k, +1))
            dn = QPushButton("↓"); dn.setFixedWidth(26)
            dn.clicked.connect(lambda _=False, k=key: self._move(k, -1))
            row.addWidget(up); row.addWidget(dn)
        v.addLayout(row)
        self.canvas = _ModCanvas(self)
        v.addWidget(self.canvas, 1)
        self._sync()

    def resolve(self, key):
        defs = {L["key"]: L for L in MOD_LAYERS}
        for lkey in reversed(self.order):
            if self.enabled.get(lkey, True) and defs[lkey].get(key) is not None:
                return defs[lkey][key], key, lkey
        return defs["base"].get(key), key, "base"

    def _toggle(self, key, on):
        self.enabled[key] = on
        self._sync()

    def _move(self, key, d):
        mods = [k for k in self.order if k != "base"]
        i = mods.index(key)
        j = min(len(mods) - 1, max(0, i + d))
        if i != j:
            mods[i], mods[j] = mods[j], mods[i]
            self.order = ["base"] + mods
            self._sync()

    def _sync(self):
        defs = {L["key"]: L for L in MOD_LAYERS}
        self.order_lbl.setText("  →  ".join(defs[k]["label"] for k in self.order))
        now = time.monotonic()
        for key in MOD_KEYS:
            act = [k for k in self.order if k != "base" and self.enabled.get(k, True)
                   and defs[k].get(key) is not None]
            if len(act) >= 2 and now - self._last_emit > 2.0:
                self._last_emit = now
                self.bus.emit("mod_conflict", key=key, layers=len(act),
                              winner=self.resolve(key)[2])
        self.canvas.update()

    def start(self): self.canvas.start()
    def stop(self): self.canvas.stop()


PATCH_CHUNKS, CHUNK_KB = 48, 64

class _PatchCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.phase = "idle"
        self.changed = set()
        self.client, self.packets = [0] * PATCH_CHUNKS, []
        self.check_t, self.check_k = 0.0, 0.0
        self.log = deque(maxlen=5)
        self.corrupt_armed = False
        self.transferred = 0
        self.repaired = 0
        self.setMinimumHeight(360)
        self.timer = QTimer(self); self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)

    def say(self, s):
        self.log.append(s); self.update()

    def new_release(self):
        self.changed = set(random.sample(range(PATCH_CHUNKS), random.randint(8, 16)))
        self.phase = "idle"
        self.client, self.packets = [0] * PATCH_CHUNKS, []
        self.transferred = self.repaired = 0
        self.say(f"📰 new build published on server ({len(self.changed)} chunks differ)")

    def check(self):
        if self.phase != "idle": return
        self.phase, self.check_k = "checking", 0.0
        self.say("🔍 comparing chunk hashes against server manifest…")

    def apply(self):
        if self.phase != "ready": return
        self.phase = "patching"
        self.say(f"⬇ patching {len(self.changed)} chunks ({len(self.changed)*CHUNK_KB} KB of {PATCH_CHUNKS*CHUNK_KB} KB)")

    def _tick(self):
        pg = self.page
        if self.phase == "checking":
            self.check_k += 0.03
            if self.check_k >= 1.0:
                self.phase = "ready"
                self.say(f"✔ manifest verified — {len(self.changed)} chunks outdated, patch is "
                         f"{len(self.changed)*CHUNK_KB} KB ({100 - 100*len(self.changed)/PATCH_CHUNKS:.0f}% saved)")
        elif self.phase == "patching":
            speed = 0.012 + pg.bw_s.value() * 0.010
            active = [pk for pk in self.packets]
            while len(active) < 3:
                nxt = next((c for c in sorted(self.changed)
                            if self.client[c] in (0, 1, 4)
                            and not any(pk["c"] == c for pk in self.packets)), None)
                if nxt is None: break
                self.packets.append(dict(c=nxt, k=0.0)); active.append(self.packets[-1])
                self.client[nxt] = 2
            for pk in self.packets:
                pk["k"] += speed
                if pk["k"] >= 1.0:
                    c = pk["c"]
                    if self.corrupt_armed:
                        self.corrupt_armed = False
                        self.client[c] = 4; self.repaired += 1
                        self.say(f"✗ chunk #{c:02d} failed hash check — quarantined, re-downloading")
                        self.packets.append(dict(c=c, k=0.0))
                        self.client[c] = 2
                        self.transferred += CHUNK_KB
                    else:
                        self.client[c] = 3; self.transferred += CHUNK_KB
            self.packets = [pk for pk in self.packets if pk["k"] < 1.0]
            if all(self.client[c] == 3 for c in self.changed):
                self.phase = "done"
                saved = 100 - 100 * (self.transferred / (PATCH_CHUNKS * CHUNK_KB))
                self.say(f"✅ update applied — {self.transferred} KB transferred ({saved:.0f}% less than full)"
                         + (f" · {self.repaired} chunk(s) re-fetched after corruption" if self.repaired else ""))
                pg.bus.emit("patch_saved", saved_pct=int(saved), repaired=self.repaired)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        cols, cs_, gap = 16, 16, 3
        gw = cols * (cs_ + gap) - gap
        gx0, gx1 = 22, w - 22 - gw
        gy = 58
        def grid(x0, title, state_of, server_side):
            p.setPen(QColor(C_TEXT)); p.setFont(mono(9))
            p.drawText(QPointF(x0, gy - 12), title)
            for i in range(PATCH_CHUNKS):
                r, c = divmod(i, cols)
                x, y = x0 + c * (cs_ + gap), gy + r * (cs_ + gap)
                st = state_of(i)
                if server_side:
                    fill = "#b26a1b" if i in self.changed else "#26282e"
                else:
                    fill = {0: "#26282e", 1: "#3d3220", 2: "#6b4a12",
                            3: "#2e5e3a", 4: "#6b2020"}.get(st, "#26282e")
                p.setBrush(QColor(fill)); p.setPen(QPen(QColor("#3a3d45"), 1))
                p.drawRect(QRectF(x, y, cs_, cs_))
                if st == 4:
                    p.setPen(QColor(C_RED)); p.setFont(mono(8))
                    p.drawText(QRectF(x, y, cs_, cs_), Qt.AlignCenter, "✗")
                if st == 2:
                    p.setBrush(QColor(255, 209, 102, int(90 + 70 * math.sin(time.monotonic() * 8))))
                    p.setPen(Qt.NoPen)
                    p.drawRect(QRectF(x, y, cs_, cs_))
        grid(gx0, "your install — v1.4.2", lambda i: self.client[i], False)
        grid(gx1, "server — v1.4.3", lambda i: 0, True)
        if self.phase == "checking":
            x = lerp(gx0, gx1 + gw, self.check_k)
            p.setPen(QPen(_qc(C_ACCENT, 180), 2))
            p.drawLine(QPointF(x, gy - 16), QPointF(x, gy + 3 * (cs_ + gap) + 4))
            p.setPen(QColor(C_ACCENT)); p.setFont(mono(9))
            p.drawText(QPointF(min(x + 6, w - 180), gy - 20), "hashing…")
        cx = w / 2
        p.setPen(QPen(QColor("#3a3d45"), 2, Qt.DashLine))
        p.drawLine(QPointF(cx, gy + 10), QPointF(cx, gy + 3 * (cs_ + gap)))
        for pk in self.packets:
            k = max(0.0, min(1.0, pk["k"]))
            y = lerp(gy + 3 * (cs_ + gap), gy + 10, k)
            p.setBrush(QColor(C_YELLOW if self.corrupt_armed and pk["k"] > 0.7 else C_ACCENT))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(cx - 12, y - 5, 24, 10), 3, 3)
            p.setPen(QColor("#10151a")); p.setFont(mono(7))
            p.drawText(QRectF(cx - 12, y - 5, 24, 10), Qt.AlignCenter, f"{pk['c']:02d}")
        done = sum(1 for c in self.changed if self.client[c] == 3)
        total_changed = max(1, len(self.changed))
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(22, h - 66), f"bandwidth {self.page.bw_s.value()} MB/s · transferred {self.transferred} KB")
        p.setPen(QPen(QColor(C_BORDER), 1)); p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(22, h - 58, w - 44, 12))
        p.setBrush(QColor(C_ACCENT) if self.phase != "done" else QColor(C_GREEN)); p.setPen(Qt.NoPen)
        p.drawRect(QRectF(23, h - 57, max(2, (w - 46) * done / total_changed), 10))
        msgs = dict(idle="press 'check for update' — the manifest is a hash list",
                    checking="comparing local chunk hashes with the server manifest…",
                    ready="patch ready — only orange chunks will travel down the wire",
                    patching="delta transfer: unchanged chunks are NEVER downloaded",
                    done="verified, applied, playable — this is how 60 GB games patch in 400 MB")
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        yy = h - 14
        for ln in list(self.log)[-3:]:
            p.drawText(QPointF(22, yy), ln); yy += 13
        p.setPen(QColor(C_YELLOW)); p.setFont(mono(9))
        p.drawText(QPointF(22, h - 52), msgs[self.phase])

    def start(self):
        if not self.timer.isActive(): self.timer.start()

    def stop(self): self.timer.stop()

class PatchingDiagram(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)
        v.addWidget(diag_header("Patching & packaging — why 60 GB games patch in 400 MB",
            "A patch is not a new download — it's a diff. The server manifest lists a hash per chunk; your client hashes its own chunks and downloads ONLY the ones that differ, verifying each arrival before swapping it into place (a corrupt chunk is re-fetched, never installed). Corrupt a chunk mid-flight and watch verification catch it."))
        row = QHBoxLayout()
        chk = QPushButton("🔍 Check for update"); chk.clicked.connect(self.canvas_check)
        self.apply_b = QPushButton("⬇ Apply patch"); self.apply_b.setEnabled(False)
        self.apply_b.clicked.connect(self.canvas_apply)
        corrupt = QPushButton("☠ corrupt next chunk")
        corrupt.clicked.connect(self._corrupt)
        rel = QPushButton("📰 new release"); rel.clicked.connect(self.canvas_release)
        row.addWidget(chk); row.addWidget(self.apply_b); row.addWidget(corrupt); row.addWidget(rel)
        row.addSpacing(12); row.addWidget(QLabel("bandwidth"))
        self.bw_s = QSlider(Qt.Horizontal); self.bw_s.setRange(1, 12); self.bw_s.setValue(4)
        self.bw_s.setMaximumWidth(110); row.addWidget(self.bw_s)
        row.addStretch(1)
        v.addLayout(row)
        self.canvas = _PatchCanvas(self)
        self.canvas.new_release()
        self.canvas.phase = "idle"
        self.canvas.log.clear()
        self.canvas.say("server holds v1.4.3 · your install is v1.4.2 — press check")
        v.addWidget(self.canvas, 1)

    def canvas_check(self):
        self.canvas.check(); self.apply_b.setEnabled(True)

    def canvas_apply(self):
        self.canvas.apply(); self.apply_b.setEnabled(False)

    def canvas_release(self):
        self.canvas.new_release(); self.apply_b.setEnabled(False)

    def _corrupt(self):
        self.canvas.corrupt_armed = True
        self.canvas.say("☠ bit-flip armed — the NEXT arriving chunk will fail its hash check")

    def start(self): self.canvas.start()
    def stop(self): self.canvas.stop()


PIPE_SOURCES = ["tree.blend", "bark.psd", "hero.fbx", "theme.wav", "rocks.blend"]
PIPE_INTERS = [
    ("tree.mesh", "tree.blend", 2.0), ("bark.dds", "bark.psd", 1.0),
    ("hero.mesh", "hero.fbx", 2.5), ("hero.skel", "hero.fbx", 1.0),
    ("theme.ogg", "theme.wav", 0.6), ("rocks.mesh", "rocks.blend", 1.8),
]
PIPE_BUNDLES = [("world.pak", ["tree.mesh", "bark.dds", "rocks.mesh", "hero.mesh"], 1.5),
                ("audio.pak", ["theme.ogg"], 0.4)]

class _PipeCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setMinimumHeight(340)
        self._rects = {}
        self.timer = QTimer(self); self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)

    def _tick(self):
        pg = self.page
        if pg.phase in ("hash", "import", "cook"):
            pg.k += 0.05
            if pg.k >= 1.0:
                pg.k = 0.0
                pg._advance_task()
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        pg = self.page
        cw, chh = 150, 30
        col_x = [20, w * 0.42, w - 20 - cw]
        self._rects.clear()
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        for x, t in zip(col_x, ("① source files (never ship)", "② compiled intermediates",
                                "③ cooked bundles (.pak)")):
            p.drawText(QPointF(x, 22), t)
        def draw_item(key, x, y, label, status, color):
            r = QRectF(x, y, cw, chh)
            self._rects[key] = r
            p.setBrush(QColor("#33261f") if status == "✏ dirty" else QColor("#243039"))
            p.setPen(QPen(QColor(color), 2 if pg.active_key == key else 1))
            p.drawRoundedRect(r, 6, 6)
            p.setPen(QColor(C_TEXT)); p.setFont(mono(8))
            p.drawText(r.adjusted(8, 0, -6, 0), Qt.AlignVCenter | Qt.AlignLeft, label)
            p.setPen(QColor(C_DIM))
            p.drawText(r.adjusted(0, 0, -6, -2), Qt.AlignRight | Qt.AlignBottom, status)
            if pg.active_key == key and pg.phase != "idle":
                p.setBrush(QColor(C_YELLOW)); p.setPen(Qt.NoPen)
                p.drawRect(QRectF(r.left() + 1, r.bottom() - 3, (cw - 2) * pg.k, 2))
        ys = {}
        for i, name in enumerate(PIPE_SOURCES):
            src = pg.sources[name]
            ys[name] = 40 + i * (chh + 10)
            draw_item("s:" + name, col_x[0], ys[name], name,
                      "✏ dirty" if src["dirty"] else "clean", C_ORANGE if src["dirty"] else C_BORDER)
        for i, (name, srcn, _c) in enumerate(PIPE_INTERS):
            it = pg.inters[name]
            ys[name] = 40 + i * (chh + 8)
            st = ("↻ rebuilt" if it.get("rebuilt") else "✔ fresh") if it["built"] else "— not built"
            draw_item("i:" + name, col_x[1], ys[name], name, st,
                      C_GREEN if it.get("rebuilt") else (C_BORDER if it["built"] else C_DIM))
        for i, (name, deps, _c) in enumerate(PIPE_BUNDLES):
            b = pg.bundles[name]
            ys[name] = 40 + i * (chh + 44)
            draw_item("b:" + name, col_x[2], ys[name], name,
                      ("⤴ cooked" if b["built"] else "— not built") + (" (updated)" if b.get("rebuilt") else ""),
                      C_ACCENT if b.get("rebuilt") else (C_BORDER if b["built"] else C_DIM))
        for (name, srcn, _c) in PIPE_INTERS:
            a = QPointF(col_x[0] + cw, ys[srcn] + chh / 2)
            b2 = QPointF(col_x[1], ys[name] + chh / 2)
            hot = pg.phase == "import" and pg.active_key == "i:" + name
            p.setPen(QPen(QColor(C_YELLOW) if hot else QColor("#3a3d45"), 2 if hot else 1))
            p.drawLine(a, b2)
        for (name, deps, _c) in PIPE_BUNDLES:
            for d in deps:
                a = QPointF(col_x[1] + cw, ys[d] + chh / 2)
                b2 = QPointF(col_x[2], ys[name] + chh / 2)
                hot = pg.phase == "cook" and pg.active_key == "b:" + name
                p.setPen(QPen(QColor(C_ACCENT) if hot else QColor("#3a3d45"), 2 if hot else 1))
                p.drawLine(a, b2)
        p.setFont(mono(9)); p.setPen(QColor(C_TEXT))
        p.drawText(QPointF(20, h - 44), pg.status_line)
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(20, h - 26),
                   "click a source to touch it (edit in DCC) · hash decides everything: untouched assets NEVER rebuild")
        p.drawText(QPointF(20, h - 12),
                   "sources stay in the studio; players get only intermediates: smaller, private, optimized for load speed")

    def start(self):
        if not self.timer.isActive(): self.timer.start()

    def stop(self): self.timer.stop()

class AssetPipelineDiagram(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.sources = {n: dict(dirty=False, hash=random.randint(10**6, 10**7)) for n in PIPE_SOURCES}
        self.inters = {n: dict(src=s, cost=c, built=False, rebuilt=False)
                       for n, s, c in PIPE_INTERS}
        self.bundles = {n: dict(deps=d, cost=c, built=False, rebuilt=False)
                        for n, d, c in PIPE_BUNDLES}
        self.phase, self.k = "idle", 0.0
        self.tasks, self.ti = [], 0
        self.active_key = None
        self.status_line = "idle — the build is a DAG walk driven by content hashes"
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)
        v.addWidget(diag_header("Asset pipeline — from .blend to .pak",
            "Shipped content is COMPILED, not copied. Sources are hashed; only assets whose hash changed get re-imported into intermediates optimized for load speed; bundles re-cook only when a dependency changed. That's why a one-texture edit rebuilds in seconds on a 100 GB project — the same content-addressing trick the patcher uses. Click sources to touch them, then build."))
        row = QHBoxLayout()
        b1 = QPushButton("🏗 build"); b1.clicked.connect(self.build)
        b2 = QPushButton("✏ touch all sources"); b2.clicked.connect(self._touch_all)
        b3 = QPushButton("🧹 clean build"); b3.clicked.connect(self._clean)
        row.addWidget(b1); row.addWidget(b2); row.addWidget(b3); row.addStretch(1)
        v.addLayout(row)
        self.canvas = _PipeCanvas(self)
        v.addWidget(self.canvas, 1)

    def _child_click(self, pos):
        for key, r in self.canvas._rects.items():
            if key.startswith("s:") and r.contains(pos):
                name = key[2:]
                self.sources[name].update(dirty=True, hash=random.randint(10**6, 10**7))
                self.status_line = f"touched {name} — everything depending on it is now stale"
                self.canvas.update(); return

    def _touch_all(self):
        for s in self.sources.values(): s.update(dirty=True, hash=random.randint(10**6, 10**7))
        self.status_line = "every source touched — next build ≈ a full rebuild"
        self.canvas.update()

    def _clean(self):
        for it in self.inters.values(): it.update(built=False, rebuilt=False)
        for b in self.bundles.values(): b.update(built=False, rebuilt=False)
        self.status_line = "clean: all intermediates deleted — build will import everything"
        self.canvas.update()

    def build(self):
        self.tasks = [("hash", None)]
        for n, it in self.inters.items():
            if not it["built"] or self.sources[it["src"]]["dirty"]:
                self.tasks.append(("import", n))
        for n, b in self.bundles.items():
            if not b["built"] or any(self.inters[d].get("rebuilt") or not self.inters[d]["built"]
                                     for d in b["deps"]):
                self.tasks.append(("cook", n))
        self.ti = 0; self.k = 0.0
        self._begin_task()
        for it in self.inters.values(): it["rebuilt"] = False
        for b in self.bundles.values(): b["rebuilt"] = False

    def _begin_task(self):
        kind, name = self.tasks[self.ti]
        self.phase = kind
        self.active_key = (None if name is None else
                           ("i:" + name if kind == "import" else "b:" + name))
        self.status_line = {"hash": "🔍 hashing source files…",
                            "import": f"⚙ importing {name} (source changed or missing)",
                            "cook": f"📦 cooking {name} (a dependency changed)"}[kind]
        self.canvas.update()

    def _advance_task(self):
        kind, name = self.tasks[self.ti]
        if kind == "import":
            it = self.inters[name]
            it.update(built=True, rebuilt=True)
            self.sources[it["src"]]["dirty"] = False
        elif kind == "cook":
            self.bundles[name].update(built=True, rebuilt=True)
        self.ti += 1
        if self.ti >= len(self.tasks):
            self.phase = "idle"; self.active_key = None
            rebuilt = sum(1 for _k, n in self.tasks if _k == "import")
            skipped = len(PIPE_INTERS) - rebuilt
            full = sum(i[2] for i in PIPE_INTERS) + sum(b[2] for b in PIPE_BUNDLES)
            spent = sum(it["cost"] for it in self.inters.values() if it.get("rebuilt")) + \
                    sum(b["cost"] for b in self.bundles.values() if b.get("rebuilt"))
            self.status_line = (f"✔ build done — {rebuilt} rebuilt, {skipped} skipped "
                                f"(~{spent:.1f}s of ~{full:.1f}s full rebuild)")
            self.bus.emit("build_done", rebuilt=rebuilt, skipped=skipped)
        else:
            self._begin_task()
        self.canvas.update()

    def start(self):
        self.canvas.start()
        self.canvas.mousePressEvent = lambda e: self._child_click(e.position())

    def stop(self): self.canvas.stop()


ALLOC_COLORS = [C_ACCENT, C_GREEN, C_ORANGE, C_PINK, C_PURPLE, C_YELLOW, "#26c6da", "#ff7043"]

class _AllocCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setMinimumHeight(340)
        self.setMouseTracking(True)
        self._rects = {}
        self.note = "allocate and free blocks — watch each strategy pay (or dodge) the fragmentation tax"

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w = self.width()
        pg = self.page
        x0, x1 = 200, w - 150
        uw = (x1 - x0) / 96.0
        self._rects.clear()
        def row(y, title, sub):
            p.setPen(QColor(C_TEXT)); p.setFont(self.font())
            p.drawText(QPointF(16, y + 16), title)
            p.setPen(QColor(C_DIM)); p.setFont(mono(8))
            p.drawText(QPointF(16, y + 30), sub)
        ry = 26
        row(ry, "① Arena / bump allocator", "alloc = advance pointer · free = reset only · O(1), zero metadata")
        p.setPen(QPen(QColor(C_BORDER), 1)); p.setBrush(QColor("#15171b"))
        p.drawRect(QRectF(x0, ry, x1 - x0, 34))
        xa = x0
        for i, size in enumerate(pg.arena):
            r = QRectF(xa, ry + 2, size * uw, 30)
            self._rects[("arena", i)] = r
            p.setBrush(QColor(ALLOC_COLORS[i % len(ALLOC_COLORS)]))
            p.setPen(Qt.NoPen); p.drawRect(r)
            p.setPen(QColor("#10151a")); p.setFont(mono(7))
            p.drawText(r, Qt.AlignCenter, f"{size}")
            xa += size * uw
        p.setPen(QPen(QColor(C_YELLOW), 2))
        p.drawLine(QPointF(xa, ry - 4), QPointF(xa, ry + 38))
        p.setPen(QColor(C_DIM))
        p.drawText(QPointF(x1 + 8, ry + 20), f"{int(96 - (xa - x0) / uw)}/96 free")
        ry = 96
        row(ry, "② Pool (fixed-size slots)", "free list of equal slots · alloc/free O(1), fragmentation impossible")
        slot_w = (x1 - x0) / 14
        for i in range(14):
            r = QRectF(x0 + i * slot_w, ry, slot_w - 3, 34)
            occupied = pg.pool[i] is not None
            self._rects[("pool", i)] = r
            p.setBrush(QColor("#243039") if occupied else QColor("#15171b"))
            p.setPen(QPen(QColor("#3a5f4a" if not occupied else C_BORDER),
                          1, Qt.DashLine if not occupied else Qt.SolidLine))
            p.drawRect(r)
            if occupied:
                p.setPen(QColor(C_TEXT)); p.setFont(mono(7))
                p.drawText(r, Qt.AlignCenter, pg.pool[i])
        if pg.pool_free:
            p.setPen(QColor(C_GREEN)); p.setFont(mono(8))
            p.drawText(QPointF(x0, ry + 48),
                       "free list:  head → " + " → ".join(pg.pool_free) + " → ∅")
        ry = 176
        row(ry, "③ General heap (first-fit)", "any size, any order — pays with fragmentation & search time")
        p.setPen(QPen(QColor(C_BORDER), 1)); p.setBrush(QColor("#15171b"))
        p.drawRect(QRectF(x0, ry, x1 - x0, 34))
        xh = x0
        for i, (start, size, label) in enumerate(pg.heap):
            gx = x0 + start * uw
            if gx > xh:
                p.setBrush(QColor(60, 42, 32)); p.setPen(Qt.NoPen)
                p.drawRect(QRectF(xh, ry + 2, gx - xh, 30))
            r = QRectF(gx, ry + 2, size * uw, 30)
            self._rects[("heap", i)] = r
            p.setBrush(QColor(ALLOC_COLORS[(i + 3) % len(ALLOC_COLORS)]))
            p.setPen(Qt.NoPen); p.drawRect(r)
            p.setPen(QColor("#10151a")); p.setFont(mono(7))
            if size * uw > 20: p.drawText(r, Qt.AlignCenter, label)
            xh = gx + size * uw
        if x1 > xh:
            p.setBrush(QColor(60, 42, 32)); p.setPen(Qt.NoPen)
            p.drawRect(QRectF(xh, ry + 2, x1 - xh, 30))
        for frag, y in ((0.0, ry - 96), (0.0, ry - 26), (pg.heap_frag, ry)):
            p.setPen(QColor(C_DIM)); p.setFont(mono(8))
            p.drawText(QPointF(x1 + 8, y + 26), f"frag {frag*100:4.0f}%")
            p.setPen(QPen(QColor(C_BORDER), 1)); p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(x1 + 8, y + 30, 120, 8))
            p.setBrush(QColor(C_RED if frag > 0.3 else C_GREEN)); p.setPen(Qt.NoPen)
            p.drawRect(QRectF(x1 + 9, y + 31, max(1.0, 118 * frag), 6))
        p.setPen(QColor(C_YELLOW)); p.setFont(mono(9))
        p.drawText(QPointF(16, self.height() - 34), "▶ " + self.note)
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(16, self.height() - 16),
                   "buttons allocate everywhere at once · click a block to free it · arena refuses middle frees (bump allocators free only at the top)")

    def mousePressEvent(self, e):
        for (kind, i), r in self._rects.items():
            if r.contains(e.position()):
                self.page.free_block(kind, i, self)
                break

class AllocatorsDiagram(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.arena = []
        self.pool = [None] * 14
        self.pool_free = [f"P{i}" for i in range(13, -1, -1)]
        self.heap = []
        self.heap_frag = 0.0
        self._frag_armed = True
        self.alloc_n = 0
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)
        v.addWidget(diag_header("Memory allocators — one size does not fit all",
            "General-purpose malloc is the SLOWEST and most fragmenting option, yet games mostly avoid it: per-frame data goes in an arena (reset each frame, zero cost), high-churn objects of one type live in pools (O(1), zero fragmentation), and only genuinely variable data touches the heap. Free the middle heap blocks and watch the red fragmentation meter climb while the pool stays at 0% forever."))
        row = QHBoxLayout()
        for label, size in (("＋ small", 4), ("＋ medium", 8), ("＋ large", 14)):
            b = QPushButton(label); b.clicked.connect(lambda _=False, s=size: self.alloc(s))
            row.addWidget(b)
        rst = QPushButton("🧹 reset all"); rst.clicked.connect(self.reset)
        row.addWidget(rst); row.addStretch(1)
        v.addLayout(row)
        self.canvas = _AllocCanvas(self)
        v.addWidget(self.canvas, 1)

    def alloc(self, size):
        self.alloc_n += 1
        label = f"A{self.alloc_n}"
        self.arena.append(size)
        if self.pool_free:
            lbl = self.pool_free.pop()
            self.pool[int(lbl[1:])] = label
        placed, prev = False, 0
        for i, (start, bsize, _l) in enumerate(self.heap):
            if start - prev >= size:
                self.heap.insert(i, (prev, size, label)); placed = True; break
            prev = start + bsize
        if not placed and 96 - prev >= size:
            self.heap.append((prev, size, label)); placed = True
        self.canvas.note = (f"allocated {label} ({size} units) — arena bumped, pool popped its free list, "
                            + (f"heap placed it at {prev}" if placed else "heap: no contiguous block — FAILED (fragmentation!)"))
        self._metrics()
        self.bus.emit("alloc_event", size=size, ok=placed)
        self.canvas.update()

    def free_block(self, kind, i, canvas):
        if kind == "arena":
            if i == len(self.arena) - 1:
                freed = self.arena.pop()
                canvas.note = f"arena freed top block ({freed} units) — LIFO only; that's why arenas pair with per-frame lifetimes"
            else:
                canvas.note = "arena REFUSED the free — middle blocks can't be freed; use a different allocator for that lifetime"
        elif kind == "pool":
            self.pool[i] = None
            self.pool_free.append(f"P{i}")
            canvas.note = f"pool freed slot {i} in O(1) — fragmentation is structurally impossible"
        else:
            start, size, label = self.heap.pop(i)
            canvas.note = f"heap freed {label} — a hole remains; only a later same-or-smaller alloc can fill it"
        self._metrics()
        canvas.update()

    def _metrics(self):
        used = sum(s for _s0, s, _l in self.heap)
        free_total, largest, prev = 96 - used, 0, 0
        for (start, bsize, _l) in self.heap:
            largest = max(largest, start - prev); prev = start + bsize
        largest = max(largest, 96 - prev)
        self.heap_frag = 1.0 - largest / free_total if free_total > 0 else 0.0
        if self.heap_frag >= 0.30 and self._frag_armed:
            self._frag_armed = False
            self.bus.emit("heap_fragged", frag_pct=int(self.heap_frag * 100))
        if self.heap_frag < 0.15: self._frag_armed = True

    def reset(self):
        self.arena = []; self.heap = []
        self.pool = [None] * 14
        self.pool_free = [f"P{i}" for i in range(13, -1, -1)]
        self.heap_frag = 0.0; self._frag_armed = True
        self.canvas.note = "reset — arena dump is literally one pointer assignment"
        self.canvas.update()

    def start(self): pass
    def stop(self): pass


BT_NODES = {
    "root":   ("SEL", "Selector",        None,     0),
    "combat": ("SEQ", "Sequence: Fight", "root",   1),
    "vis":    ("?",   "Enemy visible?",  "combat", 2),
    "move":   ("▸",   "Move into range", "combat", 2),
    "atk":    ("✸",   "Attack!",         "combat", 2),
    "patrol": ("▸",   "Patrol",          "root",   1),
}

class _BTCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setMinimumHeight(360)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        pg = self.page
        colx = {0: w * 0.10, 1: w * 0.38, 2: w * 0.68}
        rowy = {"root": 40, "combat": 110, "vis": 88, "move": 148, "atk": 208, "patrol": 270}
        nw, nh = 168, 38
        rects = {}
        for key, (kind, label, parent, depth) in BT_NODES.items():
            r = QRectF(colx[depth], rowy[key], nw, nh)
            rects[key] = r
            status = pg.status.get(key)
            hot = pg.highlight == key
            col = {True: C_GREEN, False: C_RED}.get(status, C_DIM) if status is not None else "#4a5568"
            p.setBrush(QColor("#332a15") if hot else QColor("#243039"))
            p.setPen(QPen(QColor(C_YELLOW) if hot else QColor(col), 2 if hot else 1.5))
            p.drawRoundedRect(r, 7, 7)
            p.setPen(QColor(C_TEXT)); p.setFont(self.font())
            p.drawText(r.adjusted(8, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, f"{kind}  {label}")
            if status is not None:
                p.setPen(QColor(C_GREEN if status else C_RED)); p.setFont(mono(9))
                p.drawText(r.adjusted(0, 0, -8, 0), Qt.AlignVCenter | Qt.AlignRight, "✓" if status else "✗")
        for key, (kind, label, parent, depth) in BT_NODES.items():
            if parent:
                a, b = rects[parent], rects[key]
                p.setPen(QPen(QColor("#4a5568"), 1))
                p.drawLine(QPointF(a.right(), a.center().y()), QPointF(b.left(), b.center().y()))
        sy = h - 78
        p.setPen(QPen(QColor(C_BORDER), 1)); p.setBrush(QColor("#0c0d10"))
        p.drawRoundedRect(QRectF(16, sy, w - 32, 62), 8, 8)
        p.setPen(QColor(C_BORDER)); p.drawLine(24, sy + 44, w - 24, sy + 44)
        ax = 56 + pg.agent_x * (w - 80) / 560.0
        px = 56 + pg.player_x * (w - 80) / 560.0
        if abs(pg.agent_x - pg.player_x) < 150:
            p.setPen(QPen(_qc(C_RED, 110), 1, Qt.DashLine))
            p.drawLine(QPointF(ax, sy + 36), QPointF(px, sy + 36))
        p.setBrush(QColor(C_ORANGE)); p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF([QPointF(ax, sy + 30), QPointF(ax - 10, sy + 44), QPointF(ax + 10, sy + 44)]))
        p.setBrush(QColor(C_ACCENT))
        p.drawEllipse(QPointF(px, sy + 30), 7, 7)
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(24, sy + 14),
                   f"world: agent {pg.agent_x:.0f} · player {pg.player_x:.0f} · hp {pg.hp:.0f}% · dist {abs(pg.agent_x - pg.player_x):.0f} (range 150, attack 30)")
        p.setPen(QColor(C_YELLOW)); p.setFont(mono(9))
        p.drawText(QPointF(24, h - 8), pg.last_result)

class BehaviorTreeDiagram(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self.status, self.highlight = {}, None
        self.tick_n, self.agent_x, self.player_x = 0, 40.0, 320.0
        self.hp, self.mode, self.mode_t = 100.0, "patrol", 0.0
        self.last_result = "ticks run top-to-bottom every 0.8 s — selector falls through on ✗"
        self.plan, self.plan_i, self.plan_t = [], 0, 0.0
        self._chase_t = -1e9
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)
        v.addWidget(diag_header("Behavior trees — how AI decides",
            "FSMs tangle as behaviors grow; behavior trees stay composable: selectors try children left-to-right until one SUCCEEDS, sequences run children until one FAILS. Every tick re-evaluates from the root — so a spotted enemy preempts patrolling instantly, with no explicit 'interrupt' code. Watch the highlight flow, then wait for the player to wander close: Fight fires."))
        self.canvas = _BTCanvas(self)
        v.addWidget(self.canvas, 1)
        self.timer = QTimer(self); self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)

    def _eval(self, key):
        dist = abs(self.agent_x - self.player_x)
        if key == "root":
            ok = any(self._eval(c) for c in ("combat", "patrol"))
            self.plan.append((key, ok)); return ok
        if key == "combat":
            ok = True
            for child in ("vis", "move", "atk"):
                if not self._eval(child):
                    ok = False; break
            self.plan.append((key, ok)); return ok
        if key == "vis":
            ok = dist < 150; self.plan.append((key, ok)); return ok
        if key == "move":
            self.plan.append((key, True))
            if dist >= 30: self.mode, self.mode_t = "chase", 0.8
            return True
        if key == "atk":
            ok = dist < 30
            self.plan.append((key, ok))
            if ok:
                self.mode, self.mode_t = "attack", 0.8
                self.hp = max(0.0, self.hp - 15.0)
                now = time.monotonic()
                if now - self._chase_t > 4:
                    self._chase_t = now
                    self.bus.emit("bt_chase", dist=int(dist), hp=int(self.hp))
            return ok
        if key == "patrol":
            self.plan.append((key, True))
            self.mode, self.mode_t = "patrol", 0.8
            return True
        self.plan.append((key, True)); return True

    def _tick(self):
        dt = 0.033
        if self.mode == "chase":
            self.agent_x += (60 if self.player_x > self.agent_x else -60) * dt
        elif self.mode == "attack":
            pass
        else:
            self.agent_x += (40 - self.agent_x) * dt * 0.8
        self.mode_t -= dt
        if self.mode_t <= 0: self.mode = "patrol"
        mt = time.monotonic()
        self.player_x = 300 + 260 * math.sin(mt * 0.21) + 20 * math.sin(mt * 0.9)
        if self.mode != "attack": self.hp = min(100.0, self.hp + 4.0 * dt)
        self.agent_x = max(10.0, min(500.0, self.agent_x))
        self.plan_t += dt
        if self.plan and self.plan_i < len(self.plan) and self.plan_t > 0.09:
            key, ok = self.plan[self.plan_i]
            self.status[key] = ok
            self.highlight = key
            self.last_result = f"tick #{self.tick_n}: {BT_NODES[key][1]} → {'✓' if ok else '✗'}"
            self.plan_i += 1; self.plan_t = 0.0
            if self.plan_i >= len(self.plan):
                self.plan = []; self.plan_i = 0
        elif not self.plan:
            self.tick_n += 1
            self.status = {}
            self._eval("root")
        self.canvas.update()

    def start(self):
        if not self.timer.isActive(): self.timer.start()

    def stop(self): self.timer.stop()


SM_GROUND = 300.0
SM_BOXES = [(60.0, 210.0, 130.0, 300.0, (201, 136, 80)),
            (170.0, 250.0, 240.0, 300.0, (143, 107, 176)),
            (280.0, 230.0, 340.0, 300.0, (90, 160, 106))]
SM_FLOAT = (385.0, 190.0, 445.0, 220.0, (208, 208, 216))
SM_GROUND_RGB = (122, 106, 82)

def _shadow_frame(tilt_deg, texels):
    t = math.radians(max(-55.0, min(55.0, tilt_deg)))
    L = (math.sin(t), math.cos(t))
    P = (math.cos(t), -math.sin(t))
    O0 = (P[0] * -260.0, P[1] * -260.0)
    span = 640.0
    return L, P, O0, span / texels, span

def _ray_aabb_t(px, py, dx, dy, x0, y0, x1, y1):
    tmin, tmax = -1e18, 1e18
    for (o, d, lo, hi) in ((px, dx, x0, x1), (py, dy, y0, y1)):
        if abs(d) < 1e-12:
            if o < lo or o > hi: return None
        else:
            t1, t2 = (lo - o) / d, (hi - o) / d
            if t1 > t2: t1, t2 = t2, t1
            tmin = max(tmin, t1); tmax = min(tmax, t2)
    if tmax < max(tmin, 1e-6): return None
    t = tmin if tmin > 1e-6 else tmax
    return t if t > 1e-6 else None

def _cast_ray(px, py, dx, dy, boxes):
    best = None
    if dy > 1e-9:
        t = (SM_GROUND - py) / dy
        if t > 1e-6: best = (t, (0.0, -1.0), SM_GROUND_RGB)
    for (x0, top, x1, bot, rgb) in boxes:
        hit = _ray_aabb_t(px, py, dx, dy, x0, top, x1, bot)
        if hit is None: continue
        if best is None or hit < best[0]:
            hx, hy = px + dx * hit, py + dy * hit
            faces = [(abs(hx - x0), (-1.0, 0.0)), (abs(hx - x1), (1.0, 0.0)),
                     (abs(hy - top), (0.0, -1.0)), (abs(hy - bot), (0.0, 1.0))]
            _d, n = min(faces, key=lambda z: z[0])
            best = (hit, n, rgb)
    return best

def shadow_depth_map(boxes, tilt_deg, texels):
    L, P, O0, du, _span = _shadow_frame(tilt_deg, texels)
    out = []
    for i in range(texels):
        u = (i + 0.5) * du
        out.append(_cast_ray(O0[0] + P[0] * u, O0[1] + P[1] * u, L[0], L[1], boxes))
    return out

def _shadow_test(p, depth_map, L, P, O0, du, bias):
    rel = (p[0] - O0[0], p[1] - O0[1])
    tp = rel[0] * L[0] + rel[1] * L[1]
    i = int((rel[0] * P[0] + rel[1] * P[1]) / du)
    if i < 0 or i >= len(depth_map) or depth_map[i] is None: return False
    return tp > depth_map[i][0] + bias

class _ShadowCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.k = 1.0
        self.setMinimumHeight(430)
        self.timer = QTimer(self); self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)

    def replay(self): self.k = 0.0

    def _tick(self):
        if self.k < 1.0:
            self.k = min(1.0, self.k + 0.0055); self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        w, h = self.width(), self.height()
        pg = self.page
        tilt = pg.tilt_s.value()
        texels = pg.tex_s.value()
        bias = pg.bias_s.value() / 10.0
        boxes = list(SM_BOXES) + ([SM_FLOAT] if pg.float_cb.isChecked() else [])
        L, P, O0, du, _span = _shadow_frame(tilt, texels)
        dm = shadow_depth_map(boxes, tilt, texels)
        kA = min(1.0, self.k / 0.42)
        kB = max(0.0, min(1.0, (self.k - 0.42) / 0.40))
        SR = QRectF(14, 34, w * 0.47, h * 0.44)
        DR = QRectF(SR.right() + 14, 34, w - SR.right() - 34, 110)
        VR = QRectF(14, SR.bottom() + 58, w - 28, h - SR.bottom() - 82)
        sx_, sy_ = SR.width() / 510.0, SR.height() / 295.0
        def W2S(x, y):
            return QPointF(SR.left() + (x + 10) * sx_, SR.top() + (y - 15) * sy_)
        p.setPen(QPen(QColor(C_BORDER), 1)); p.setBrush(QColor("#0c0d10"))
        p.drawRoundedRect(SR, 8, 8)
        p.setPen(QPen(QColor("#6a5c48"), 2))
        p.drawLine(W2S(0, SM_GROUND), W2S(490, SM_GROUND))
        for (x0, top, x1, bot, rgb) in boxes:
            p.setBrush(QColor(*rgb)); p.setPen(QPen(QColor("#11151a"), 1))
            p.drawRect(QRectF(W2S(x0, top), W2S(x1, bot)))
                        p.setBrush(QColor(min(255, rgb[0] + 40), min(255, rgb[1] + 40), min(255, rgb[2] + 40)))
            p.setPen(Qt.NoPen)
            p.drawRect(QRectF(W2S(x0, top), W2S(x1, top + 5)))
        sun = W2S(245 - L[0] * 320, 160 - L[1] * 320)
        p.setBrush(QColor("#ffe082")); p.setPen(Qt.NoPen)
        p.drawEllipse(sun, 9, 9)
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(20, 26),
                   f"① scene (side view) · light tilt {tilt:+d}° — the sun renders its own tiny z-buffer first")
        if self.k > 0.82:
            for (x0, top, x1, _bot, _rgb) in boxes:
                ts_ = (SM_GROUND - top) / L[1]
                gxa, gxb = x0 + L[0] * ts_, x1 + L[0] * ts_
                a_, b_ = W2S(min(x0, gxa), SM_GROUND), W2S(max(x1, gxb), SM_GROUND)
                p.setBrush(QColor(16, 22, 38, 150)); p.setPen(Qt.NoPen)
                p.drawRect(QRectF(a_, QPointF(b_.x(), a_.y() + 6)))

        p.setPen(QPen(QColor(C_BORDER), 1)); p.setBrush(QColor("#0c0d10"))
        p.drawRoundedRect(DR, 8, 8)
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(DR.left() + 6, DR.top() + 12),
                   f"light's depth map — {texels}×1 texels · bias {bias:.1f}")
        tmax = max((d[0] for d in dm if d), default=1.0) + 1.0
        filled = int(kA * texels)
        bw = DR.width() / texels
        for i in range(filled):
            if dm[i] is None: continue
            bh_ = (dm[i][0] / tmax) * (DR.height() - 34)
            x = DR.left() + i * bw
            p.setBrush(QColor(79, 195, 247, 170)); p.setPen(Qt.NoPen)
            p.drawRect(QRectF(x + 0.5, DR.bottom() - 8 - bh_, max(1.0, bw - 1), bh_))
        p.setPen(QColor(C_ACCENT)); p.setFont(mono(8))
        p.drawText(QPointF(DR.left() + 6, DR.bottom() - 12),
                   f"depth pass {int(kA * 100)}%" if kA < 1 else f"{texels} texels stored")

        p.setPen(QPen(QColor(C_BORDER), 1)); p.setBrush(QColor("#0c0d10"))
        p.drawRoundedRect(VR, 8, 8)
        N = 140
        cam = (468.0, 150.0)
        n_fill = int(kB * N)
        cur_info = None
        for c in range(n_fill):
            vy_ = ((c / (N - 1)) - 0.5) * 1.5
            m = math.hypot(1.0, vy_)
            hit = _cast_ray(cam[0], cam[1], -1.0 / m, vy_ / m, boxes)
            x = VR.left() + c * (VR.width() / N)
            if hit is None:
                p.setBrush(QColor("#0a0c12")); p.setPen(Qt.NoPen)
                p.drawRect(QRectF(x, VR.top() + 1, VR.width() / N + 0.5, VR.height() - 2))
                continue
            t, n, rgb = hit
            hp = (cam[0] - t / m, cam[1] + vy_ / m * t)
            lit_dot = max(0.0, -(n[0] * L[0] + n[1] * L[1]))
            shade = 0.45 + 0.55 * lit_dot
            shadowed = _shadow_test(hp, dm, L, P, O0, du, bias)
            if shadowed:
                r, g, b = int(rgb[0] * 0.22), int(rgb[1] * 0.24), int(rgb[2] * 0.34)
            else:
                r, g, b = int(rgb[0] * shade), int(rgb[1] * shade), int(rgb[2] * shade)
            p.setBrush(QColor(r, g, b)); p.setPen(Qt.NoPen)
            p.drawRect(QRectF(x, VR.top() + 1, VR.width() / N + 0.5, VR.height() - 2))
            if c == n_fill - 1:
                cur_info = (hp, t, n, rgb, shadowed, c)
        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(VR.left() + 6, VR.top() + 14),
                   f"② camera pass — final image {int(kB * 100)}%" +
                   ("  ·  each fragment: is its light-depth deeper than the stored texel? shadow." if kB > 0 else ""))

        if cur_info and self.k < 1.0:
            hp, t, n, rgb, shadowed, c = cur_info
            sp = W2S(*hp)
            cp = W2S(*cam)
            p.setPen(QPen(_qc(C_YELLOW, 170), 1, Qt.DashLine))
            p.drawLine(cp, sp)
            p.setBrush(QColor(C_YELLOW)); p.setPen(Qt.NoPen)
            p.drawEllipse(sp, 4, 4)
            i = int(((hp[0] - O0[0]) * P[0] + (hp[1] - O0[1]) * P[1]) / du)
            if 0 <= i < texels and dm[i]:
                stored = dm[i][0]
                ys_ = DR.bottom() - 8 - (stored / tmax) * (DR.height() - 34)
                yp_ = DR.bottom() - 8 - (t / tmax) * (DR.height() - 34)
                x_ = DR.left() + (i + 0.5) * bw
                p.setPen(QPen(QColor(C_GREEN), 2)); p.drawLine(QPointF(x_ - 4, ys_), QPointF(x_ + 4, ys_))
                p.setPen(QPen(QColor(C_ORANGE), 2)); p.drawLine(QPointF(x_ - 4, yp_), QPointF(x_ + 4, yp_))
                p.setPen(QColor(C_GREEN)); p.setFont(mono(8))
                p.drawText(QPointF(x_ + 7, ys_ + 3), f"stored {stored:.0f}")
                p.setPen(QColor(C_ORANGE))
                p.drawText(QPointF(x_ + 7, yp_ + 3), f"fragment {t:.0f}")
                p.setPen(QColor(C_RED if shadowed else C_GREEN)); p.setFont(mono(9))
                p.drawText(QPointF(min(x_ + 7, DR.right() - 90), DR.top() + 26),
                           f"Δ {t - stored:5.1f} {'>' if shadowed else '≤'} bias → {'SHADOW' if shadowed else 'lit'}")

        p.setPen(QColor(C_DIM)); p.setFont(mono(8))
        p.drawText(QPointF(14, h - 12),
                   "bias too low ⇒ surfaces shadow THEMSELVES within a texel (stripes = acne) · bias too high ⇒ shadows detach "
                   "(peter-panning) · few texels ⇒ jagged edges. PCF & CSMs refine this one comparison.")

    def start(self):
        if not self.timer.isActive(): self.timer.start()

    def stop(self): self.timer.stop()

class ShadowMapDiagram(QWidget):
    def __init__(self, bus):
        super().__init__()
        self.bus = bus
        self._acne_t = self._pp_t = -1e9
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)
        v.addWidget(diag_header("Shadow mapping — shadows are found, not drawn",
            "Pass 1: the LIGHT renders the scene into a tiny depth texture (it only asks 'how far is the nearest thing along this ray?'). "
            "Pass 2: the camera renders normally, and every fragment transforms into light space and compares its own depth against that "
            "texel — deeper means something is in front of the light: shadow. Both famous artifacts fall straight out of this math: "
            "bias too low = shadow acne (a surface fails against its own texel), bias too high = peter-panning (shadows detach), "
            "low resolution = jagged edges. Watch the Δ readout during the sweep."))
        row = QHBoxLayout()
        for label, attr, lo, hi, val in (("light tilt", "tilt_s", -50, 50, 18),
                                         ("texels", "tex_s", 16, 96, 44),
                                         ("bias ×0.1", "bias_s", 0, 80, 20)):
            row.addWidget(QLabel(label))
            s = QSlider(Qt.Horizontal); s.setRange(lo, hi); s.setValue(val)
            s.setMaximumWidth(120)
            setattr(self, attr, s)
            row.addWidget(s)
        self.float_cb = QCheckBox("floating platform (shadow falls on nothing)")
        rep = QPushButton("↻ replay passes"); rep.clicked.connect(lambda: self.canvas.replay())
        row.addWidget(self.float_cb); row.addWidget(rep); row.addStretch(1)
        self.tilt_s.valueChanged.connect(self._changed)
        self.tex_s.valueChanged.connect(lambda _v: (self.canvas.replay(), self._artifact_check(soft=True)))
        self.bias_s.valueChanged.connect(lambda _v: (self.canvas.replay(), self._artifact_check()))
        self.float_cb.toggled.connect(lambda _on: self.canvas.replay())
        v.addLayout(row)
        self.canvas = _ShadowCanvas(self)
        self.canvas.replay()
        v.addWidget(self.canvas, 1)

    def _changed(self, _v):
        self.canvas.replay(); self._artifact_check(soft=True)

    def _artifact_check(self, soft=False):
        now = time.monotonic()
        if not soft and self.bias_s.value() <= 6 and abs(self.tilt_s.value()) >= 12 \
                and now - self._acne_t > 4:
            self._acne_t = now
            self.bus.emit("shadow_acne", bias=self.bias_s.value() / 10)
        if self.bias_s.value() >= 55 and now - self._pp_t > 4:
            self._pp_t = now
            self.bus.emit("peter_panning", bias=self.bias_s.value() / 10)

    def start(self): self.canvas.start()
    def stop(self): self.canvas.stop()


# ----------------------------------------------------------- the gallery ----
class DiagramsPage(QWidget):
    DEFS = [
        ("🥞  Engine layers",         LayersDiagram),
        ("🧵  CPU/GPU pipeline",      CpuGpuDiagram),
        ("⏱  Accumulator",           AccumulatorDiagram),
        ("🧠  Memory: AoS vs SoA",    MemoryLayoutDiagram),
        ("🌳  Quadtree",             QuadtreeDiagram),
        ("🎚  Audio mixer",          AudioMixerDiagram),
        ("🏗  Scene graph vs flat",    SceneGraphDiagram),
        ("⚙️  Job system & stealing", ThreadingDiagram),
        ("🌐  Forward vs deferred",   GBufferDiagram),
        ("🎯  Shader pipeline",       ShaderPipelineDiagram),
        ("👁  Occlusion culling",     OcclusionDiagram),
        ("🌐⏱  Net: snapshots",       NetDiagram),
        ("🪄  Modding & patches",     ModdingDiagram),
        ("📦  Patching & packaging",  PatchingDiagram),
        ("🏭  Asset pipeline",        AssetPipelineDiagram),
        ("🏦  Memory allocators",     AllocatorsDiagram),
        ("🌿  Behavior trees",        BehaviorTreeDiagram),
        ("🌓  Shadow mapping",        ShadowMapDiagram),
    ]

    def __init__(self, bus):
        super().__init__()
        v = QVBoxLayout(self)
        v.addWidget(page_header("Diagram Gallery",
            "Eighteen animated diagrams covering the theory behind the labs. Some publish events — run a layer trace, catch a "
            "work-steal, trip the accumulator guard or meet shadow acne, then open the Event Bus Monitor and watch it arrive."))
        h = QHBoxLayout()
        self.listw = QListWidget(); self.listw.setFixedWidth(230)
        self.stack = QStackedWidget()
        for name, cls in self.DEFS:
            self.stack.addWidget(cls(bus))
            self.listw.addItem(QListWidgetItem(name))
        self.listw.currentRowChanged.connect(self._changed)
        h.addWidget(self.listw); h.addWidget(self.stack, 1)
        v.addLayout(h)
        self.listw.setCurrentRow(0)
        self._cur = 0

    def _changed(self, ix):
        if ix < 0: return
        self.stack.widget(self._cur).stop()
        self._cur = ix
        self.stack.setCurrentIndex(ix)
        if self.isVisible():
            self.stack.widget(ix).start()

    def showEvent(self, e):
        self.stack.widget(self._cur).start()
        super().showEvent(e)

    def hideEvent(self, e):
        for i in range(self.stack.count()):
            self.stack.widget(i).stop()
        super().hideEvent(e)


# ================================================================ MAIN WINDOW
PAGE_DEFS = [
    ("overview",    "🗺  Overview",           OverviewPage),
    ("diagrams",    "📐 Diagram Gallery",     DiagramsPage),
    ("loop",        "🔁 Game Loop Lab",       GameLoopPage),
    ("ecs",         "🧩 ECS Playground",      ECSPage),
    ("anim",        "🕺 Animation Lab",       AnimationPage),
    ("ik",          "🦾 IK Toy",              IKPage),
    ("render",      "🎨 Rendering Lab",       RenderPage),
    ("shader",      "✨ Shader Lab",          ShaderLabPage),
    ("camera",      "📷 Camera & Post",       CameraLabPage),
    ("broad",       "🌲 Broad-Phase Lab",     BroadPhasePage),
    ("physics",     "🧱 Physics Response",    PhysicsResponsePage),
    ("ai",          "🤖 AI & Pathfinding",    AIPathPage),
    ("noise",       "⛰ Noise & Worldgen",     NoisePage),
    ("resources",   "💾 Resource Manager",    ResourcePage),
    ("profiler",    "📈 Profiler",            ProfilerPage),
    ("loc",         "🌍 Localization",        LocalizationPage),
    ("save",        "🧾 Save / Load Lab",     SerializationPage),
    ("determinism", "🎲 Determinism Lab",     DeterminismPage),
    ("netplay",     "🌐 Multiplayer Lab",     NetplayPage),
    ("input",       "🎮 Input Mapper",        InputPage),
    ("bus",         "📡 Event Bus Monitor",   EventBusPage),
    ("quiz",        "🎓 Quiz",                QuizPage),
    ("capstone",    "🚀 Engine Builder",      CapstonePage),
]

TOUR = [
    ("overview",   "Welcome to EngineLab! This is the architecture map — click 2–3 modules to read them, then press Next."),
    ("loop",       "The heartbeat. Drag Target FPS to 15, then switch Timestep to Fixed — stutter vanishes and blue update-blocks stack per frame."),
    ("loop",       "Now set the 🔥 lag injector to ~20 ms: the accumulator can't drain and the spiral guard fires."),
    ("ecs",        "Composition over inheritance. Press ⚡×50, select an entity and untick Velocity — it stops; everything else keeps flowing."),
    ("render",     "Cull → sort → batch. Untick batching to watch draw-calls jump; drag the blue camera rect yourself."),
    ("anim",       "Animation = data + interpolation. Drag speed through the blend zone, then try 'step' interpolation to see raw keyframes snap."),
    ("ik",         "FK is angles→position; IK is position→angles. Drag the crosshair, flip the elbow, then watch the 6-joint chain curl toward its wandering target one CCD sweep at a time."),
    ("camera",     "The last mile of every frame: FOV reshapes the frustum (watch the map), then stack bloom + exposure + warm grade — that's post-processing, the difference between raw and shipped."),
    ("physics",    "Detection ≠ response. Restitution eats energy, correction fights sinking — and the fast ball tunnels unless you add substeps."),
    ("ai",         "Race all four search algorithms on one maze — then paint mud (cost ×5) and watch Dijkstra earn its keep."),
    ("noise",      "Worlds from a seed: same seed, same world. Determinism again — octaves are continents plus detail."),
    ("bus",        "Systems never call each other directly. Emit a few events, then untick a listener — mail is dropped, nothing crashes."),
    ("diagrams",   "Theory corner: open ⏱ Accumulator, drag average frame time to 25 ms, and watch the tank overflow."),
    ("determinism","Record a run (arrows drive ☺), replay it — hashes match. Then arm divergence and watch the ghosts split."),
    ("netplay",    "The final lab: multiplayer. Prediction OFF feels like 1996; ON, and corrections absorb the bot's shoves. The latency slider is your enemy."),
    ("profiler",   "Find the cost. Inject +8 ms into AI, enable AI bursts — the histogram's red tail is the stutter players feel."),
    ("quiz",       "Final boss: twelve questions. 9+ earns Certified Architect. Good luck!"),
]

class _TourBanner(QFrame):
    def __init__(self, win):
        super().__init__(win)
        self.win, self.idx = win, 0
        self.setFixedSize(700, 54)
        self.setStyleSheet("background:#1d2b36; border:1px solid #4fc3f7; border-radius:10px;")
        v = QHBoxLayout(self); v.setContentsMargins(14, 6, 10, 6)
        self.lbl = QLabel(); self.lbl.setWordWrap(True)
        nxt = QPushButton("Next ▸"); nxt.setFixedWidth(84)
        skp = QPushButton("Skip"); skp.setFixedWidth(64)
        nxt.clicked.connect(self.next); skp.clicked.connect(self.hide_stop)
        v.addWidget(self.lbl, 1); v.addWidget(nxt); v.addWidget(skp)
        self.hide()

    def start(self):
        self.idx = 0; self._apply(); self.show(); self.raise_()

    def _apply(self):
        key, text = TOUR[self.idx]
        self.win._nav(key)
        self.lbl.setText(f"<b>Step {self.idx + 1}/{len(TOUR)}</b> — {text}")

    def next(self):
        self.idx += 1
        if self.idx >= len(TOUR):
            self.hide_stop()
            self.win.bus.emit("tour_complete", steps=len(TOUR))
        else:
            self._apply()

    def hide_stop(self): self.hide()

class _PaletteDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Command palette"); self.setFixedWidth(470)
        v = QVBoxLayout(self)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Type a command… (pages, tour, report, achievements)")
        self.listw = QListWidget()
        v.addWidget(self.edit); v.addWidget(self.listw)
        self.actions = [("Go: " + title, lambda _=None, k=key: win._nav(k))
                        for key, title, _ in PAGE_DEFS]
        self.actions += [("🧭 Start guided tour", win.start_tour),
                         ("🧾 Export lab report", win.export_report),
                         ("🏅 Show achievements", win._show_achievements)]
        self.edit.textChanged.connect(self._filter)
        self.edit.returnPressed.connect(self._run)
        self.listw.itemDoubleClicked.connect(self._run)
        self._filter("")
        self.edit.setFocus()

    def _filter(self, text):
        text = text.lower()
        self.listw.clear()
        for name, fn in self.actions:
            if text in name.lower():
                it = QListWidgetItem(name); it.setData(Qt.UserRole, fn)
                self.listw.addItem(it)
        if self.listw.count(): self.listw.setCurrentRow(0)

    def _run(self, *_):
        it = self.listw.currentItem()
        if it:
            self.accept(); it.data(Qt.UserRole)()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Down:
            self.listw.setCurrentRow(min(self.listw.count() - 1, self.listw.currentRow() + 1))
        elif e.key() == Qt.Key_Up:
            self.listw.setCurrentRow(max(0, self.listw.currentRow() - 1))
        else:
            super().keyPressEvent(e)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EngineLab — Game Engine Architecture, Interactive")
        self.resize(1400, 900)
        self.bus = EventBus()
        self.ach = Achievements(self.bus)
        self.session_t0 = time.time()
        self.page_times = defaultdict(float)
        self._page_t0 = time.monotonic()
        self._cur_key = "overview"

        root = QWidget(); self.setCentralWidget(root)
        h = QHBoxLayout(root); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(0)

        side = QWidget(); side.setFixedWidth(215)
        side.setStyleSheet(f"background:{C_PANEL}; border-right:1px solid {C_BORDER};")
        sv = QVBoxLayout(side); sv.setContentsMargins(12, 14, 12, 10); sv.setSpacing(3)
        logo = QLabel("⚙ EngineLab"); logo.setObjectName("h1")
        sub = QLabel("game engine architecture,\ninteractive"); sub.setObjectName("dim")
        sv.addWidget(logo); sv.addWidget(sub); sv.addSpacing(6)

        self.stack = QStackedWidget()
        self.navs, self.page_keys = [], []
        for key, title, cls in PAGE_DEFS:
            self.stack.addWidget(cls(self.bus))
            self.page_keys.append(key)
            b = QPushButton(title); b.setObjectName("nav"); b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self._nav(k))
            sv.addWidget(b); self.navs.append(b)
        sv.addStretch(1)

        self.ach_lbl = QLabel(); self.ach_lbl.setObjectName("dim")
        ach_btn = QPushButton("🏅 View achievements")
        ach_btn.clicked.connect(self._show_achievements)
        tour_btn = QPushButton("🧭 Start guided tour")
        tour_btn.clicked.connect(self.start_tour)
        rep_btn = QPushButton("🧾 Export lab report")
        rep_btn.clicked.connect(self.export_report)
        pal_hint = QLabel("⌨ Ctrl+K — palette"); pal_hint.setObjectName("dim")
        for wdg in (self.ach_lbl, ach_btn, tour_btn, rep_btn, pal_hint):
            sv.addWidget(wdg)
        tip = QLabel("Everything runs on ONE event bus — open the Event Bus Monitor while experimenting.\n"
                     "CI-style: python engine_lab.py --selftest")
        tip.setObjectName("dim"); tip.setWordWrap(True)
        sv.addWidget(tip)

        h.addWidget(side); h.addWidget(self.stack, 1)
        self._nav("overview", first=True)

        self.toast = ToastOverlay(self)
        self.tour = _TourBanner(self)
        self.ach.unlocked_sig.connect(self.toast.pop)
        self.ach.unlocked_sig.connect(lambda *_: self._sync_ach())
        self._sync_ach()
        self.toast.setGeometry(self.rect()); self.toast.raise_()
        self.stack.widget(0).open_requested.connect(self._nav)
        QTimer.singleShot(600, lambda: setattr(self.ach, "armed", True))
        QShortcut(QKeySequence("Ctrl+K"), self, self._open_palette)

    def _flush_time(self):
        self.page_times[self._cur_key] += time.monotonic() - self._page_t0
        self._page_t0 = time.monotonic()

    def _nav(self, key, first=False):
        if key not in self.page_keys: return
        if not first: self._flush_time()
        self._cur_key = key
        ix = self.page_keys.index(key)
        self.stack.setCurrentIndex(ix)
        for i, b in enumerate(self.navs): b.setChecked(i == ix)

    def _sync_ach(self):
        self.ach_lbl.setText(f"🏆 {len(self.ach.unlocked)} / {len(ACH_DEFS)} unlocked")

    def start_tour(self): self.tour.start()

    def _open_palette(self):
        _PaletteDialog(self).exec()

    def export_report(self):
        self._flush_time()
        dur = int(time.time() - self.session_t0)
        lines = ["# EngineLab session report",
                 f"*{time.strftime('%Y-%m-%d %H:%M')} · {dur // 60}m {dur % 60}s*", ""]
        lines += ["## Pages explored", ""]
        for key, secs in sorted(self.page_times.items(), key=lambda kv: -kv[1]):
            if secs < 2: continue
            title = next(t for k, t, _ in PAGE_DEFS if k == key)
            lines.append(f"- **{title}** — {int(secs) // 60}m {int(secs) % 60:02d}s")
        lines += ["", f"## Achievements ({len(self.ach.unlocked)}/{len(ACH_DEFS)})", ""]
        for aid, emoji, title, desc in ACH_DEFS:
            if aid in self.ach.unlocked:
                ts = time.strftime('%H:%M', time.localtime(self.ach.unlocked_at.get(aid, 0)))
                lines.append(f"- {emoji} **{title}** — {desc} _({ts})_")
        lines += ["", "## Event bus traffic", ""]
        total = sum(self.bus.counts.values())
        lines.append(f"- **{total:,} events** published through the bus this session")
        for name, c in sorted(self.bus.counts.items(), key=lambda kv: -kv[1])[:10]:
            lines.append(f"- `{name}` ×{c:,}")
        lines += ["", "*Evidence of experimentation — every number above came from live interaction.*"]
        report = "\n".join(lines)
        path = Path.home() / "enginelab_report.md"
        try: path.write_text(report)
        except Exception: pass
        dlg = QDialog(self); dlg.setWindowTitle("Lab report"); dlg.resize(560, 520)
        v = QVBoxLayout(dlg)
        info = QLabel(f"Saved to <b>{path}</b> — hand this in as your coursework evidence.")
        info.setWordWrap(True)
        txt = QPlainTextEdit(); txt.setReadOnly(True); txt.setFont(mono(9))
        txt.setPlainText(report)
        close = QPushButton("Close"); close.clicked.connect(dlg.accept)
        v.addWidget(info); v.addWidget(txt, 1); v.addWidget(close, alignment=Qt.AlignRight)
        dlg.exec()

    def _show_achievements(self):
        dlg = QDialog(self); dlg.setWindowTitle("Achievements"); dlg.resize(500, 460)
        v = QVBoxLayout(dlg)
        for aid, emoji, title, desc in ACH_DEFS:
            got = aid in self.ach.unlocked
            lab = QLabel(f"{emoji if got else '🔒'}  <b>{title}</b> — {desc}")
            lab.setWordWrap(True)
            if not got: lab.setStyleSheet(f"color:{C_DIM};")
            v.addWidget(lab)
        v.addStretch(1)
        row = QHBoxLayout()
        reset = QPushButton("Reset progress")
        def do_reset():
            self.ach.unlocked.clear(); self.ach.unlocked_at.clear(); self.ach.count.clear()
            try: self.ach.path.unlink(missing_ok=True)
            except Exception: pass
            self._sync_ach(); dlg.close()
        reset.clicked.connect(do_reset)
        close = QPushButton("Close"); close.clicked.connect(dlg.accept)
        row.addWidget(reset); row.addStretch(1); row.addWidget(close)
        v.addLayout(row)
        dlg.exec()

    def resizeEvent(self, e):
        self.toast.setGeometry(self.rect()); self.toast.raise_()
        self.tour.move((self.width() - self.tour.width()) // 2, self.height() - 74)
        self.tour.raise_()
        super().resizeEvent(e)

    def closeEvent(self, e):
        self._flush_time()
        super().closeEvent(e)


# ================================================================= SELFTEST =
def run_selftest():
    """Headless CI: instantiate real pages, drive real logic, assert invariants.
    Usage: python engine_lab.py --selftest   → exit 0 all green, 1 any failure."""
    import os, tempfile, traceback
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([sys.argv[0]])
    bus = EventBus()
    results = []

    def check(name, fn):
        t0 = time.perf_counter()
        try:
            fn()
            results.append((name, True, time.perf_counter() - t0, ""))
        except Exception:
            results.append((name, False, time.perf_counter() - t0,
                            traceback.format_exception_only(type(sys.exc_info()[1]),
                                                            sys.exc_info()[1])[0].strip()[:90]))

    def page(cls):
        pg = cls(bus); pg.resize(1200, 800); return pg

    def t_eventbus():
        got = []
        bus.subscribe("st_test", lambda ev: got.append(ev.payload["x"]))
        bus.emit("st_test", x=42)
        assert got == [42] and bus.counts["st_test"] >= 1

    def t_serializer():
        ents = [SEnt(i, i % 3, 10.0 * i, 5.0, 1.0, 2.0, 80.0, i * 7) for i in range(5)]
        buf, _ = serialize_world(ents, 2)
        back, err, mig = deserialize_world(buf)
        assert err is None and not mig and world_hash(back) == world_hash(ents)
        assert all(b.gold == i * 7 for i, b in enumerate(back))
        buf1, _ = serialize_world(ents, 1)
        back1, err1, mig1 = deserialize_world(buf1)
        assert err1 is None and mig1 and all(b.gold == 0 for b in back1)
        bad = bytearray(buf); bad[9] ^= 0xFF
        _, err2, _ = deserialize_world(bytes(bad))
        assert err2 and "checksum" in err2

    def t_accumulator():
        pg = page(GameLoopPage); pg.canvas.resize(500, 400)
        pg.mode_combo.setCurrentIndex(1)
        for _ in range(40):
            pg.last_real -= 1.0 / 60.0            # pretend 1/60 s elapsed per tick
            pg._tick()
        assert 30 <= pg.updates_total <= 60, f"updates {pg.updates_total}"
        pg.acc = 10.0 / 60.0                      # force a debt the cap can't drain
        pg.last_real -= 1.0 / 60.0
        pg._tick()
        assert bus.counts.get("spiral_guard", 0) >= 1, "guard never tripped"

    def t_broadphase():
        pg = page(BroadPhasePage); pg.canvas.resize(900, 560)
        for en in pg.ents: en.vx = en.vy = 0.0
        pg.grid_cb.setChecked(False); pg._tick()
        off = set(pg.canvas.actual_pairs)
        pg.grid_cb.setChecked(True); pg._tick()
        on = set(pg.canvas.actual_pairs)
        assert off == on, "grid missed collisions brute force found"
        assert pg.last_cand <= pg.last_brute
        assert pg.last_cand < pg.last_brute, "grid saved nothing"

    def t_determinism():
        A, B = _DetWorld(42), _DetWorld(42)
        script = [KEY_R, 0, KEY_D | KEY_R, KEY_U, 0]
        for f in range(240):
            k = script[f % len(script)]
            A.step(1 / 60, k); B.step(1 / 60, k)
            assert det_hash(A.snapshot()) == det_hash(B.snapshot()), f"diverged at {f}"
        B.balls[0][2] += 0.001                    # the butterfly
        diverged = False
        for f in range(240, 480):
            k = script[f % len(script)]
            A.step(1 / 60, k); B.step(1 / 60, k)
            if det_hash(A.snapshot()) != det_hash(B.snapshot()):
                diverged = True; break
        assert diverged, "0.001 perturbation never diverged — suspicious"

    def t_ecs():
        w = World(bus)
        e = w.create(Transform(1, 2), Velocity(3, 4))
        assert w.has(e, Velocity) and w.stats["spawned"] == 1
        w.remove(e, Velocity); assert not w.has(e, Velocity)
        w.destroy(e); assert e not in w.tables[Transform]
        assert w.stats["destroyed"] == 1

    def t_resources():
        pg = page(ResourcePage)
        pg._toggle_level("Forest")
        for _ in range(90): pg._tick()
        assert pg.assets["mesh/tree_low"].state == "loaded"
        pg._toggle_level("Dungeon")
        for _ in range(90): pg._tick()
        assert pg.hits >= 1, "mesh/rock should have been a cache hit"
        pg._toggle_level("Forest")
        pg._toggle_level("City")
        for _ in range(130): pg._tick()
        assert pg.evictions >= 1, "budget overflow must evict"

    def t_profiler():
        pg = page(ProfilerPage)
        pg.canvas._build(); base = pg.canvas.totals[-1]
        pg.inject["AI"] += 8.0
        pg.canvas._build()
        assert pg.canvas.totals[-1] - base > 5.0

    def t_shader():
        for name in ("Plasma", "Rings", "Checker floor", "Vignette"):
            fn, err, gen, n = compile_shader(SH_PRESETS[name])
            assert fn and err is None, f"{name}: {err}"
            a = fn(0.3, 0.7, 1.0, 0.5, 0.5); b = fn(0.3, 0.7, 1.0, 0.5, 0.5)
            assert a == b and all(isinstance(v, float) for v in a)
        fn, err, _g, _n = compile_shader(SH_PRESETS["💥 broken (syntax error)"])
        assert fn is None and err, "broken preset must fail"
        fn, err, _g, _n = compile_shader("float q = nonsense + 1.0;\nreturn vec3(q,q,q);")
        assert fn is None and "undeclared" in err

    def t_netplay():
        pg = page(NetplayPage); pg.canvas.resize(900, 560)
        pg.lat_s.setValue(20); pg.jit_s.setValue(0); pg.loss_s.setValue(0)
        pg.canvas.keys = {Qt.Key_Right}
        for _ in range(200): pg._tick()
        pg.canvas.keys = {Qt.Key_Down}
        for _ in range(220): pg._tick()
        assert pg.snaps_received > 60 and pg.srv_tick_n > 60
        assert 0 <= pg.c_pos[0] <= NET_W and 0 <= pg.c_pos[1] <= NET_H
        pg.pred_cb.setChecked(False)
        for _ in range(100): pg._tick()
        assert pg.err_log, "error log should record samples"

    def t_achievements():
        a = Achievements(bus)
        a.path = Path(tempfile.gettempdir()) / "el_selftest_ach.json"
        a.armed = True
        bus.emit("entity_spawned", entity=1)
        assert "first_spawn" in a.unlocked
        a.path.unlink(missing_ok=True)

    def t_noise_det():
        a = [fbm(x / 17, 0.5, 4242, 4, 0.5, 3.0) for x in range(24)]
        b = [fbm(x / 17, 0.5, 4242, 4, 0.5, 3.0) for x in range(24)]
        c = [fbm(x / 17, 0.5, 4243, 4, 0.5, 3.0) for x in range(24)]
        assert a == b and a != c and all(0.0 <= v <= 1.0 for v in a)

    def t_astar_optimal():
        walls = {(5, r) for r in range(PF_ROWS) if r != 2}
        path, expanded, cost = solve_path(walls, set(), (0, 8), (10, 8), "astar")
        assert path and abs(cost - 22.0) < 1e-6, f"cost {cost} ≠ optimal 22"
        _gp, gexp, gcost = solve_path(walls, set(), (0, 8), (10, 8), "greedy")
        assert gcost >= cost - 1e-6 and expanded < PF_ROWS * PF_COLS

    def t_anim_blend():
        pg = page(AnimationPage)
        pg.speed_s.setValue(52)
        for _ in range(10): pg._tick()
        assert 0.05 < pg.w_run < 0.95 and pg.w_move > 0.9
        assert len(pg.pose) == 8

    def t_ik():
        sol, cl = solve_ik2(0, 0, 60, 80, 60, 60)
        a1, a2 = sol[0], sol[1]
        ex = 60 * math.cos(a1) + 60 * math.cos(a1 + a2)
        ey = 60 * math.sin(a1) + 60 * math.sin(a1 + a2)
        assert abs(ex - 60) < 0.01 and abs(ey - 80) < 0.01, "two-bone IK missed target"
        (_b1, _b2, _cx, _cy), cl2 = solve_ik2(0, 0, 400, 0, 60, 60)
        assert cl2 and abs(_b1) < 1e-6, "unreachable target must clamp to full extension"
        (u1, _u2, _a, _b), _ = solve_ik2(0, 0, 60, 80, 60, 60, elbow_up=True)
        (v1, _v2, _c, _d), _ = solve_ik2(0, 0, 60, 80, 60, 60, elbow_up=False)
        assert abs(u1 - v1) > 1e-6, "elbow solutions must differ"
        ang, lens = [0.0] * 6, [30.0] * 6
        ex2 = ey2 = 0.0
        for _ in range(20):
            ex2, ey2 = ccd_step(ang, lens, 120.0, 40.0)
        assert math.hypot(ex2 - 120, ey2 - 40) < 1.0, "CCD must converge"

    def t_shadowmap():
        boxes = [(90.0, 210.0, 150.0, 300.0, (200, 100, 50))]
        dm = shadow_depth_map(boxes, 0.0, 48)
        L, P, O0, du, _sp = _shadow_frame(0.0, 48)
        assert _shadow_test((120.0, 299.0), dm, L, P, O0, du, 1.0), "under box must shadow"
        assert not _shadow_test((240.0, 299.0), dm, L, P, O0, du, 1.0), "beside box must be lit"
        dmt = shadow_depth_map(boxes, 25.0, 48)
        L2, P2, O02, du2, _sp2 = _shadow_frame(25.0, 48)
        pts = [(94.0 + i * 2.6, 210.0) for i in range(20)]
        acne = sum(1 for pt in pts if _shadow_test(pt, dmt, L2, P2, O02, du2, 0.2))
        fixed = sum(1 for pt in pts if _shadow_test(pt, dmt, L2, P2, O02, du2, 9.0))
        assert acne >= 3, "low bias must self-shadow the tilted top (acne)"
        assert fixed == 0, "high bias must clear acne"

    def t_post():
        w, h = 32, 24
        buf = bytearray(w * h * 4)
        for i in range(w * h):
            buf[i * 4] = buf[i * 4 + 1] = buf[i * 4 + 2] = 100; buf[i * 4 + 3] = 255
        b2 = _post_exposure(bytearray(buf), 1.0)
        assert b2[0] == 200 and buf[0] == 100, "+1 EV must double values"
        b3 = _post_grade(bytearray(buf), "warm sunset")
        assert b3[0] > b3[1] > b3[2], "warm grade must push red over blue"
        b4 = _post_vignette(bytearray(buf), w, h, 1.0)
        assert b4[0] < b4[((h // 2) * w + w // 2) * 4], "vignette must darken corners"

    for name, fn in [("event bus deliver + counts", t_eventbus),
                     ("save/load round-trip, migration, checksum", t_serializer),
                     ("accumulator: 60 Hz + spiral guard", t_accumulator),
                     ("broad phase == brute force, fewer tests", t_broadphase),
                     ("determinism: 240 frames bit-identical", t_determinism),
                     ("ECS create/remove/destroy bookkeeping", t_ecs),
                     ("resources: cache hits + LRU eviction", t_resources),
                     ("profiler: injected cost shows up", t_profiler),
                     ("shader: presets compile, broken rejected", t_shader),
                     ("netplay: snapshots, reconcile, lag mode", t_netplay),
                     ("achievements unlock via bus", t_achievements),
                     ("noise: seeded & deterministic", t_noise_det),
                     ("A* finds the 22-cost detour optimally", t_astar_optimal),
                     ("animation blend weights in range", t_anim_blend),
                     ("IK: solver exact, clamps, CCD converges", t_ik),
                     ("shadow map: shadow, acne, bias fix", t_shadowmap),
                     ("post: exposure, grade, vignette", t_post)]:
        check(name, fn)

    total = sum(bus.counts.values())
    print("\nEngineLab selftest")
    print("═" * 66)
    w = max(len(n) for n, _ in results)
    for name, ok, dt, msg in results:
        mark = "✔" if ok else "✗"
        line = f" {mark} {name:<{w}}  {dt * 1000:6.1f} ms"
        print(line + (f"\n     └─ {msg}" if msg else ""))
    bad = sum(0 if ok else 1 for _, ok, _, _ in results)
    print("═" * 66)
    print(f" {len(results) - bad}/{len(results)} checks passed · {total:,} bus events "
          f"during the run · {'ALL GREEN — ship it' if not bad else 'FAILURES ABOVE'}")
    return 0 if not bad else 1


def main():
    if "--selftest" in sys.argv:
        sys.exit(run_selftest())
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()