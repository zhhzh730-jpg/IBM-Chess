# -*- coding: utf-8 -*-
"""TCT5 Chess - Kivy + python-chess
Author: محمد مدين / Modine Mohamade / TCT5
2026

This version intentionally does NOT use Polygon, Mesh, or Unicode chess pieces.
Chess pieces are drawn with Kivy Canvas primitives only.
"""

import random
import threading
import math
import struct
import wave
import tempfile
from pathlib import Path

import chess

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.audio import SoundLoader
from kivy.graphics import Color, Rectangle, Ellipse, Line
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.widget import Widget


# ------------------------------------------------------------
# Window / theme
# ------------------------------------------------------------
CURRENT_THEME = "dark"

THEMES = {
    "dark": {
        "window": (0.045, 0.045, 0.06, 1),
        "button": (0.12, 0.12, 0.17, 1),
        "button_down": (0.18, 0.18, 0.25, 1),
        "text": (1, 1, 1, 1),
        "subtext": (0.78, 0.78, 0.82, 1),
        "light_square": (0.90, 0.82, 0.68, 1),
        "dark_square": (0.35, 0.22, 0.14, 1),
    },
    "light": {
        "window": (0.92, 0.93, 0.96, 1),
        "button": (0.80, 0.82, 0.87, 1),
        "button_down": (0.70, 0.73, 0.80, 1),
        "text": (0.08, 0.09, 0.12, 1),
        "subtext": (0.25, 0.27, 0.32, 1),
        "light_square": (0.93, 0.88, 0.76, 1),
        "dark_square": (0.48, 0.34, 0.23, 1),
    },
}

LIGHT_SQUARE = THEMES["dark"]["light_square"]
DARK_SQUARE = THEMES["dark"]["dark_square"]

WHITE_MAIN = (0.95, 0.93, 0.86, 1)
WHITE_LIGHT = (1.0, 0.99, 0.95, 1)
WHITE_SHADOW = (0.62, 0.59, 0.52, 1)
WHITE_DARK = (0.25, 0.24, 0.21, 1)
WHITE_OUTLINE = (0.10, 0.10, 0.10, 1)

BLACK_MAIN = (0.11, 0.12, 0.15, 1)
BLACK_LIGHT = (0.27, 0.28, 0.32, 1)
BLACK_SHADOW = (0.035, 0.04, 0.055, 1)
BLACK_DARK = (0.015, 0.017, 0.025, 1)
BLACK_OUTLINE = (0.005, 0.005, 0.008, 1)

MOVE_DOT = (0.12, 0.82, 0.30, 0.95)
CAPTURE_RING = (0.95, 0.25, 0.16, 0.95)
SELECT_COLOR = (1.0, 0.78, 0.08, 0.95)


# ------------------------------------------------------------
# Simple UI button
# ------------------------------------------------------------
class MenuButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = 58
        self.font_size = "20sp"
        self.bold = True
        self.background_normal = ""
        self.background_down = ""
        self.refresh_theme()

        self.bind(on_release=self._button_sound)

    def _button_sound(self, *_args):
        app = App.get_running_app()
        if app is not None:
            app.play_sound("click")

    def refresh_theme(self):
        theme = THEMES[CURRENT_THEME]
        self.background_color = theme["button"]
        self.color = theme["text"]


# ------------------------------------------------------------
# Audio
# ------------------------------------------------------------
class AudioManager:
    """
    Generates all game sounds at runtime.

    No WAV/MP3 files are required in the project. Five tiny WAV files are
    created automatically in the operating system's temporary directory
    only so Kivy's audio provider can play them.
    """

    def __init__(self):
        self.enabled = True
        self.sounds = {}
        self.temp_dir = Path(tempfile.mkdtemp(prefix="tct5_chess_audio_"))
        self.load()

    @staticmethod
    def _tone(frequency, duration, volume=0.28, sample_rate=44100):
        count = max(1, int(duration * sample_rate))
        frames = bytearray()

        for i in range(count):
            t = i / sample_rate

            # Short attack/release envelope to avoid clicks.
            attack = min(1.0, i / max(1, int(sample_rate * 0.008)))
            release_start = int(count * 0.82)
            release = 1.0 if i < release_start else max(0.0, (count - i) / max(1, count - release_start))
            envelope = attack * release

            value = math.sin(2.0 * math.pi * frequency * t)
            sample = int(32767 * volume * envelope * value)
            frames.extend(struct.pack("<h", sample))

        return bytes(frames)

    @staticmethod
    def _silence(duration, sample_rate=44100):
        count = max(0, int(duration * sample_rate))
        return b"\x00\x00" * count

    def _write_wav(self, name, raw_pcm, sample_rate=44100):
        path = self.temp_dir / f"{name}.wav"

        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(raw_pcm)

        return path

    def generate_sounds(self):
        sr = 44100

        # 1. Button click: very soft, short and clean.
        click = (
            self._tone(720, 0.032, 0.075, sr)
            + self._silence(0.008, sr)
            + self._tone(980, 0.028, 0.045, sr)
        )

        # 2. Normal move: subtle wooden/board-like two-note confirmation.
        move = (
            self._tone(430, 0.045, 0.105, sr)
            + self._silence(0.012, sr)
            + self._tone(620, 0.060, 0.075, sr)
        )

        # 3. Capture: clearly different, slightly deeper double impact.
        capture = (
            self._tone(245, 0.055, 0.16, sr)
            + self._silence(0.012, sr)
            + self._tone(155, 0.085, 0.12, sr)
            + self._silence(0.008, sr)
            + self._tone(300, 0.035, 0.07, sr)
        )

        # 4. Check: unmistakable short warning.
        check = (
            self._tone(660, 0.075, 0.16, sr)
            + self._silence(0.018, sr)
            + self._tone(1040, 0.105, 0.17, sr)
        )

        # 5. Checkmate: distinctive three-stage ending signal.
        checkmate = (
            self._tone(440, 0.105, 0.16, sr)
            + self._silence(0.025, sr)
            + self._tone(660, 0.105, 0.18, sr)
            + self._silence(0.025, sr)
            + self._tone(880, 0.105, 0.18, sr)
            + self._silence(0.035, sr)
            + self._tone(1175, 0.22, 0.20, sr)
        )

        generated = {
            "click": click,
            "move": move,
            "capture": capture,
            "check": check,
            "checkmate": checkmate,
        }

        for name, pcm in generated.items():
            try:
                path = self._write_wav(name, pcm, sr)
                sound = SoundLoader.load(str(path))
                if sound is not None:
                    self.sounds[name] = sound
            except Exception:
                pass

    def load(self):
        self.generate_sounds()

    def play(self, name):
        if not self.enabled:
            return

        sound = self.sounds.get(name)
        if sound is None:
            return

        try:
            sound.stop()
            sound.play()
        except Exception:
            pass


# ------------------------------------------------------------
# Chess piece renderer
# ------------------------------------------------------------
class PieceDrawer:
    @staticmethod
    def palette(piece):
        if piece.color == chess.WHITE:
            return {
                "main": WHITE_MAIN,
                "light": WHITE_LIGHT,
                "shadow": WHITE_SHADOW,
                "dark": WHITE_DARK,
                "outline": WHITE_OUTLINE,
            }
        return {
            "main": BLACK_MAIN,
            "light": BLACK_LIGHT,
            "shadow": BLACK_SHADOW,
            "dark": BLACK_DARK,
            "outline": BLACK_OUTLINE,
        }

    @staticmethod
    def base(canvas, cx, y, s, c):
        Color(*c["dark"])
        Ellipse(pos=(cx - s * .36, y + s * .07), size=(s * .72, s * .14))

        Color(*c["main"])
        Rectangle(pos=(cx - s * .34, y + s * .14), size=(s * .68, s * .12))
        Ellipse(pos=(cx - s * .34, y + s * .20), size=(s * .68, s * .15))

        Color(*c["shadow"])
        Line(points=[cx - s * .28, y + s * .27, cx + s * .28, y + s * .27], width=1.3)

    @staticmethod
    def pawn(canvas, cx, y, s, c):
        PieceDrawer.base(canvas, cx, y, s, c)

        Color(*c["main"])
        Ellipse(pos=(cx - s * .22, y + s * .29), size=(s * .44, s * .37))
        Ellipse(pos=(cx - s * .16, y + s * .60), size=(s * .32, s * .27))

        Color(*c["shadow"])
        Ellipse(pos=(cx - s * .20, y + s * .30), size=(s * .40, s * .14))

        Color(*c["light"])
        Ellipse(pos=(cx - s * .105, y + s * .70), size=(s * .10, s * .07))

        Color(*c["outline"])
        Line(points=[cx - s * .16, y + s * .59, cx + s * .16, y + s * .59], width=1.0)

    @staticmethod
    def rook(canvas, cx, y, s, c):
        PieceDrawer.base(canvas, cx, y, s, c)

        Color(*c["main"])
        Rectangle(pos=(cx - s * .24, y + s * .30), size=(s * .48, s * .47))
        Rectangle(pos=(cx - s * .31, y + s * .73), size=(s * .62, s * .12))

        for i in range(3):
            xx = cx - s * .29 + i * s * .19
            Rectangle(pos=(xx, y + s * .83), size=(s * .12, s * .11))

        Color(*c["shadow"])
        Rectangle(pos=(cx - s * .24, y + s * .30), size=(s * .08, s * .47))
        Color(*c["outline"])
        Line(rectangle=(cx - s * .24, y + s * .30, s * .48, s * .47), width=1.1)

    @staticmethod
    def bishop(canvas, cx, y, s, c):
        PieceDrawer.base(canvas, cx, y, s, c)

        Color(*c["main"])
        Ellipse(pos=(cx - s * .25, y + s * .29), size=(s * .50, s * .48))
        Ellipse(pos=(cx - s * .17, y + s * .64), size=(s * .34, s * .25))

        Color(*c["shadow"])
        Ellipse(pos=(cx - s * .23, y + s * .29), size=(s * .15, s * .44))

        Color(*c["light"])
        Ellipse(pos=(cx - s * .09, y + s * .73), size=(s * .10, s * .07))

        Color(*c["outline"])
        Line(points=[cx - s * .08, y + s * .68, cx + s * .09, y + s * .81], width=2.2)

    @staticmethod
    def knight(canvas, cx, y, s, c):
        PieceDrawer.base(canvas, cx, y, s, c)

        Color(*c["main"])
        Ellipse(pos=(cx - s * .28, y + s * .28), size=(s * .54, s * .45))
        Rectangle(pos=(cx - s * .14, y + s * .47), size=(s * .28, s * .28))
        Ellipse(pos=(cx - s * .15, y + s * .65), size=(s * .38, s * .24))

        Color(*c["shadow"])
        Line(
            points=[
                cx - s * .13, y + s * .79,
                cx - s * .20, y + s * .70,
                cx - s * .15, y + s * .54,
            ],
            width=3.0,
        )
        Line(
            points=[
                cx + s * .01, y + s * .84,
                cx + s * .18, y + s * .78,
                cx + s * .22, y + s * .69,
            ],
            width=3.0,
        )

        Color(*c["outline"])
        Ellipse(pos=(cx + s * .075, y + s * .735), size=(s * .045, s * .045))
        Line(
            points=[cx - s * .02, y + s * .83, cx + s * .09, y + s * .86, cx + s * .17, y + s * .81],
            width=1.4,
        )

    @staticmethod
    def queen(canvas, cx, y, s, c):
        PieceDrawer.base(canvas, cx, y, s, c)

        Color(*c["main"])
        Ellipse(pos=(cx - s * .28, y + s * .28), size=(s * .56, s * .49))
        Rectangle(pos=(cx - s * .18, y + s * .54), size=(s * .36, s * .17))

        crown_y = y + s * .75
        for i in range(5):
            xx = cx - s * .30 + i * s * .15
            Ellipse(pos=(xx, crown_y), size=(s * .12, s * .12))

        Color(*c["shadow"])
        Line(
            points=[
                cx - s * .29, y + s * .77,
                cx - s * .17, y + s * .88,
                cx, y + s * .77,
                cx + s * .17, y + s * .88,
                cx + s * .29, y + s * .77,
            ],
            width=1.8,
        )

        Color(*c["light"])
        Ellipse(pos=(cx - s * .045, y + s * .81), size=(s * .09, s * .08))

    @staticmethod
    def king(canvas, cx, y, s, c):
        PieceDrawer.base(canvas, cx, y, s, c)

        Color(*c["main"])
        Ellipse(pos=(cx - s * .28, y + s * .28), size=(s * .56, s * .50))
        Rectangle(pos=(cx - s * .19, y + s * .57), size=(s * .38, s * .18))

        # Cross
        Rectangle(pos=(cx - s * .055, y + s * .73), size=(s * .11, s * .18))
        Rectangle(pos=(cx - s * .14, y + s * .78), size=(s * .28, s * .09))

        Color(*c["shadow"])
        Line(points=[cx - s * .20, y + s * .50, cx + s * .20, y + s * .50], width=1.8)

        Color(*c["light"])
        Line(points=[cx - s * .03, y + s * .81, cx + s * .04, y + s * .81], width=1.8)

    @staticmethod
    def draw(canvas, piece, x, y, w, h):
        if piece is None:
            return

        s = min(w, h)
        cx = x + w / 2.0
        c = PieceDrawer.palette(piece)

        # Soft ground shadow
        Color(0, 0, 0, .18)
        Ellipse(pos=(cx - s * .32, y + s * .09), size=(s * .64, s * .08))

        if piece.piece_type == chess.PAWN:
            PieceDrawer.pawn(canvas, cx, y, s, c)
        elif piece.piece_type == chess.ROOK:
            PieceDrawer.rook(canvas, cx, y, s, c)
        elif piece.piece_type == chess.KNIGHT:
            PieceDrawer.knight(canvas, cx, y, s, c)
        elif piece.piece_type == chess.BISHOP:
            PieceDrawer.bishop(canvas, cx, y, s, c)
        elif piece.piece_type == chess.QUEEN:
            PieceDrawer.queen(canvas, cx, y, s, c)
        elif piece.piece_type == chess.KING:
            PieceDrawer.king(canvas, cx, y, s, c)


# ------------------------------------------------------------
# Chess square
# ------------------------------------------------------------
class ChessSquare(Widget):
    def __init__(self, game, square, **kwargs):
        super().__init__(**kwargs)
        self.game = game
        self.square = square
        self.bind(pos=self.redraw, size=self.redraw)
        Clock.schedule_once(lambda _dt: self.redraw(), 0)

    def redraw(self, *_args):
        self.canvas.clear()
        board = self.game.board
        file_index = chess.square_file(self.square)
        rank_index = chess.square_rank(self.square)

        square_color = LIGHT_SQUARE if (file_index + rank_index) % 2 == 0 else DARK_SQUARE

        with self.canvas:
            Color(*square_color)
            Rectangle(pos=self.pos, size=self.size)

            # Selected square border
            if self.game.selected_square == self.square:
                Color(*SELECT_COLOR)
                Line(
                    rectangle=(self.x, self.y, self.width, self.height),
                    width=3,
                )

            # Legal destinations
            for move in self.game.selected_moves:
                if move.to_square != self.square:
                    continue

                if board.piece_at(self.square) is not None:
                    Color(*CAPTURE_RING)
                    Line(
                        circle=(self.center_x, self.center_y, min(self.width, self.height) * .30),
                        width=3,
                    )
                else:
                    Color(*MOVE_DOT)
                    r = min(self.width, self.height) * .075
                    Ellipse(
                        pos=(self.center_x - r, self.center_y - r),
                        size=(r * 2, r * 2),
                    )

            PieceDrawer.draw(
                self.canvas,
                board.piece_at(self.square),
                self.x,
                self.y,
                self.width,
                self.height,
            )

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.game.handle_square_click(self.square)
            return True
        return super().on_touch_down(touch)


# ------------------------------------------------------------
# Square board container
# ------------------------------------------------------------
class ChessBoard(Widget):
    def __init__(self, game, **kwargs):
        super().__init__(**kwargs)
        self.game = game
        self.squares = {}

        for square in chess.SQUARES:
            widget = ChessSquare(game, square)
            self.squares[square] = widget
            self.add_widget(widget)

        self.bind(pos=self.layout_board, size=self.layout_board)
        Clock.schedule_once(lambda _dt: self.layout_board(), 0)

    def layout_board(self, *_args):
        side = min(self.width, self.height)
        if side <= 0:
            return

        board_x = self.x + (self.width - side) / 2.0
        board_y = self.y + (self.height - side) / 2.0
        cell = side / 8.0

        for square, widget in self.squares.items():
            file_index = chess.square_file(square)
            rank_index = chess.square_rank(square)
            widget.size = (cell, cell)
            widget.pos = (
                board_x + file_index * cell,
                board_y + rank_index * cell,
            )


# ------------------------------------------------------------
# AI
# ------------------------------------------------------------
class ChessAI:
    VALUES = {
        chess.PAWN: 100,
        chess.KNIGHT: 320,
        chess.BISHOP: 330,
        chess.ROOK: 500,
        chess.QUEEN: 900,
        chess.KING: 20000,
    }

    def __init__(self, depth=2):
        self.depth = max(0, int(depth))

    def evaluate(self, board):
        if board.is_checkmate():
            # Positive means White is better.
            return -999999 if board.turn == chess.WHITE else 999999

        if board.is_game_over(claim_draw=True):
            return 0

        score = 0
        for piece_type, value in self.VALUES.items():
            score += len(board.pieces(piece_type, chess.WHITE)) * value
            score -= len(board.pieces(piece_type, chess.BLACK)) * value
        return score

    def minimax(self, board, depth, alpha, beta, maximizing):
        if depth == 0 or board.is_game_over(claim_draw=True):
            return self.evaluate(board), None

        moves = list(board.legal_moves)
        moves.sort(key=lambda m: board.is_capture(m), reverse=True)
        best_move = None

        if maximizing:
            best_value = -float("inf")
            for move in moves:
                board.push(move)
                value, _ = self.minimax(board, depth - 1, alpha, beta, False)
                board.pop()
                if value > best_value:
                    best_value = value
                    best_move = move
                alpha = max(alpha, value)
                if beta <= alpha:
                    break
            return best_value, best_move

        best_value = float("inf")
        for move in moves:
            board.push(move)
            value, _ = self.minimax(board, depth - 1, alpha, beta, True)
            board.pop()
            if value < best_value:
                best_value = value
                best_move = move
            beta = min(beta, value)
            if beta <= alpha:
                break
        return best_value, best_move

    def get_move(self, board):
        moves = list(board.legal_moves)
        if not moves:
            return None

        if self.depth == 0:
            captures = [m for m in moves if board.is_capture(m)]
            if captures and random.random() < 0.65:
                return random.choice(captures)
            return random.choice(moves)

        # AI is Black in this app.
        _, move = self.minimax(
            board,
            self.depth,
            -float("inf"),
            float("inf"),
            board.turn == chess.WHITE,
        )
        return move


# ------------------------------------------------------------
# Home screen
# ------------------------------------------------------------
class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=30, spacing=18)

        title = Label(text="CHESS", font_size="48sp", bold=True, size_hint_y=None, height=90)
        credit = Label(
            text="IBM INNOVATORS",
            font_size="14sp",
            size_hint_y=None,
            height=40,
        )

        layout.add_widget(title)
        layout.add_widget(credit)

        play = MenuButton(text="PLAY")
        settings = MenuButton(text="SETTINGS")
        exit_button = MenuButton(text="EXIT")

        play.bind(on_release=lambda *_: setattr(self.manager, "current", "play_menu"))
        settings.bind(on_release=lambda *_: setattr(self.manager, "current", "settings"))
        exit_button.bind(on_release=lambda *_: App.get_running_app().stop())

        layout.add_widget(play)
        layout.add_widget(settings)
        layout.add_widget(exit_button)
        layout.add_widget(Widget())
        layout.add_widget(Label(text="© 2026 - TCT5", size_hint_y=None, height=35))

        self.add_widget(layout)


# ------------------------------------------------------------
# Play menu
# ------------------------------------------------------------
class PlayMenuScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=30, spacing=18)
        layout.add_widget(Label(text="CHOOSE GAME MODE", font_size="28sp", size_hint_y=None, height=70))

        friend = MenuButton(text="PLAY WITH FRIEND")
        ai = MenuButton(text="PLAY AGAINST AI")
        back = MenuButton(text="BACK")

        friend.bind(on_release=self.start_friend)
        ai.bind(on_release=lambda *_: setattr(self.manager, "current", "ai_menu"))
        back.bind(on_release=lambda *_: setattr(self.manager, "current", "home"))

        layout.add_widget(friend)
        layout.add_widget(ai)
        layout.add_widget(Widget())
        layout.add_widget(back)
        self.add_widget(layout)

    def start_friend(self, *_args):
        game = self.manager.get_screen("game")
        game.start_game("friend", 0)
        self.manager.current = "game"


# ------------------------------------------------------------
# AI difficulty menu
# ------------------------------------------------------------
class AIScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=30, spacing=15)
        layout.add_widget(Label(text="AI DIFFICULTY", font_size="30sp", size_hint_y=None, height=70))

        easy = MenuButton(text="EASY")
        medium = MenuButton(text="MEDIUM")
        hard = MenuButton(text="HARD")
        back = MenuButton(text="BACK")

        easy.bind(on_release=lambda *_: self.start_ai(0))
        medium.bind(on_release=lambda *_: self.start_ai(1))
        hard.bind(on_release=lambda *_: self.start_ai(3))
        back.bind(on_release=lambda *_: setattr(self.manager, "current", "play_menu"))

        layout.add_widget(easy)
        layout.add_widget(medium)
        layout.add_widget(hard)
        layout.add_widget(Widget())
        layout.add_widget(back)
        self.add_widget(layout)

    def start_ai(self, depth):
        game = self.manager.get_screen("game")
        game.start_game("ai", depth)
        self.manager.current = "game"


# ------------------------------------------------------------
# Settings
# ------------------------------------------------------------
class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        layout = BoxLayout(
            orientation="vertical",
            padding=30,
            spacing=18
        )

        layout.add_widget(
            Label(
                text="SETTINGS",
                font_size="32sp",
                size_hint_y=None,
                height=70
            )
        )

        self.sound_button = MenuButton()
        self.theme_button = MenuButton()

        self.update_setting_text()

        self.sound_button.bind(on_release=self.toggle_sound)
        self.theme_button.bind(on_release=self.toggle_theme)

        layout.add_widget(self.sound_button)
        layout.add_widget(self.theme_button)

        layout.add_widget(Widget())

        back = MenuButton(text="BACK")
        back.bind(
            on_release=lambda *_:
            setattr(self.manager, "current", "home")
        )

        layout.add_widget(back)

        self.add_widget(layout)

    def update_setting_text(self):
        app = App.get_running_app()

        if app is None:
            return

        sound_state = "ON" if app.sound_enabled else "OFF"
        theme_state = "DARK" if app.dark_mode else "LIGHT"

        self.sound_button.text = f"SOUND: {sound_state}"
        self.theme_button.text = f"THEME: {theme_state}"

    def toggle_sound(self, *_args):
        app = App.get_running_app()
        app.sound_enabled = not app.sound_enabled
        app.audio.enabled = app.sound_enabled
        self.update_setting_text()

        if app.sound_enabled:
            app.play_sound("click")

    def toggle_theme(self, *_args):
        app = App.get_running_app()
        app.dark_mode = not app.dark_mode
        app.apply_theme()
        self.update_setting_text()

# ------------------------------------------------------------
class GameScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.board = chess.Board()
        self.mode = "friend"
        self.difficulty = 0
        self.selected_square = None
        self.selected_moves = []
        self.ai_thinking = False

        root = BoxLayout(orientation="vertical", spacing=4)

        top = BoxLayout(orientation="horizontal", size_hint_y=None, height=55, padding=5, spacing=5)
        self.status_label = Label(text="", font_size="16sp")
        menu = MenuButton(text="MENU")
        menu.size_hint_x = None
        menu.width = 105
        menu.bind(on_release=self.back_to_menu)
        top.add_widget(self.status_label)
        top.add_widget(menu)
        root.add_widget(top)

        self.chess_board = ChessBoard(self)
        root.add_widget(self.chess_board)

        bottom = BoxLayout(orientation="horizontal", size_hint_y=None, height=55, padding=5, spacing=5)
        restart = MenuButton(text="RESTART")
        restart.bind(on_release=lambda *_: self.start_game(self.mode, self.difficulty))
        bottom.add_widget(restart)
        root.add_widget(bottom)

        self.add_widget(root)

    def start_game(self, mode="friend", difficulty=0):
        self.mode = mode
        self.difficulty = int(difficulty)
        self.board = chess.Board()
        self.selected_square = None
        self.selected_moves = []
        self.ai_thinking = False
        self.update_board()
        self.update_status()

    def update_board(self):
        for widget in self.chess_board.squares.values():
            widget.redraw()

    def update_status(self):
        if self.board.is_checkmate():
            winner = "WHITE WINS" if self.board.turn == chess.BLACK else "BLACK WINS"
            self.status_label.text = f"CHECKMATE!  {winner}"
            return
        if self.board.is_stalemate() or self.board.is_insufficient_material():
            self.status_label.text = "DRAW"
            return
        turn = "WHITE" if self.board.turn == chess.WHITE else "BLACK"
        check = " - CHECK" if self.board.is_check() else ""
        self.status_label.text = f"TURN: {turn}{check}"

    def play_move_result_sound(self, was_capture, was_check, was_checkmate):
        app = App.get_running_app()
        if app is None or not app.sound_enabled:
            return

        if was_checkmate:
            app.play_sound("checkmate")
        elif was_capture:
            app.play_sound("capture")
            if was_check:
                Clock.schedule_once(
                    lambda _dt: app.play_sound("check"),
                    0.16
                )
        elif was_check:
            app.play_sound("check")
        else:
            app.play_sound("move")

    def handle_square_click(self, square):
        if self.ai_thinking or self.board.is_game_over():
            return

        # Human controls White when playing AI.
        if self.mode == "ai" and self.board.turn == chess.BLACK:
            return

        if self.selected_square is None:
            piece = self.board.piece_at(square)
            if piece is None or piece.color != self.board.turn:
                return
            self.selected_square = square
            self.selected_moves = [m for m in self.board.legal_moves if m.from_square == square]
            self.update_board()
            return

        # Clicking another own piece selects it.
        piece = self.board.piece_at(square)
        if piece is not None and piece.color == self.board.turn:
            self.selected_square = square
            self.selected_moves = [m for m in self.board.legal_moves if m.from_square == square]
            self.update_board()
            return

        move = next(
            (
                m
                for m in self.selected_moves
                if m.to_square == square
            ),
            None,
        )

        if move is None:
            self.selected_square = None
            self.selected_moves = []
            self.update_board()
            return

        # Auto-promote pawn to queen.
        moving_piece = self.board.piece_at(move.from_square)
        if moving_piece is not None and moving_piece.piece_type == chess.PAWN:
            target_rank = chess.square_rank(move.to_square)
            if target_rank in (0, 7) and move.promotion is None:
                move = chess.Move(move.from_square, move.to_square, promotion=chess.QUEEN)

        was_capture = self.board.is_capture(move)

        self.board.push(move)

        was_checkmate = self.board.is_checkmate()
        was_check = self.board.is_check()

        self.play_move_result_sound(
            was_capture,
            was_check,
            was_checkmate
        )

        self.selected_square = None
        self.selected_moves = []
        self.update_board()
        self.update_status()

        if self.mode == "ai" and not self.board.is_game_over() and self.board.turn == chess.BLACK:
            self.start_ai_turn()

    def start_ai_turn(self):
        if self.ai_thinking:
            return

        self.ai_thinking = True
        self.status_label.text = "AI THINKING..."
        board_copy = self.board.copy()
        depth = self.difficulty

        worker = threading.Thread(
            target=self.calculate_ai_move,
            args=(board_copy, depth),
            daemon=True,
        )
        worker.start()

    def calculate_ai_move(self, board_copy, depth):
        try:
            move = ChessAI(depth).get_move(board_copy)
        except Exception:
            move = None
        Clock.schedule_once(lambda _dt: self.apply_ai_move(move), 0)

    def apply_ai_move(self, move):
        self.ai_thinking = False
        if move is not None and move in self.board.legal_moves:
            was_capture = self.board.is_capture(move)
            self.board.push(move)

            was_checkmate = self.board.is_checkmate()
            was_check = self.board.is_check()

            self.play_move_result_sound(
                was_capture,
                was_check,
                was_checkmate
            )

        self.selected_square = None
        self.selected_moves = []
        self.update_board()
        self.update_status()

    def back_to_menu(self, *_args):
        self.ai_thinking = False
        self.selected_square = None
        self.selected_moves = []
        self.manager.current = "home"


# ------------------------------------------------------------
# App
# ------------------------------------------------------------
class ChessApp(App):
    def build(self):
        self.title = "TCT5 Chess"

        self.sound_enabled = True
        self.dark_mode = True
        self.audio = AudioManager()

        manager = ScreenManager()
        manager.add_widget(HomeScreen(name="home"))
        manager.add_widget(PlayMenuScreen(name="play_menu"))
        manager.add_widget(AIScreen(name="ai_menu"))
        manager.add_widget(SettingsScreen(name="settings"))
        manager.add_widget(GameScreen(name="game"))
        manager.current = "home"

        self.root = manager
        self.apply_theme()

        return manager

    def play_sound(self, name):
        self.audio.play(name)

    def apply_theme(self):
        global CURRENT_THEME, LIGHT_SQUARE, DARK_SQUARE

        CURRENT_THEME = "dark" if self.dark_mode else "light"

        theme = THEMES[CURRENT_THEME]

        Window.clearcolor = theme["window"]
        LIGHT_SQUARE = theme["light_square"]
        DARK_SQUARE = theme["dark_square"]

        if self.root is not None:
            self.refresh_widget_tree(self.root)

            game = self.root.get_screen("game")
            game.update_board()

            settings = self.root.get_screen("settings")
            settings.update_setting_text()

    def refresh_widget_tree(self, widget):
        if isinstance(widget, MenuButton):
            widget.refresh_theme()
        elif isinstance(widget, Label):
            widget.color = THEMES[CURRENT_THEME]["text"]

        for child in widget.children:
            self.refresh_widget_tree(child)


if __name__ == "__main__":
    ChessApp().run()
