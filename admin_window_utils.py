"""Utilitários visuais compartilhados pelas janelas do Gerador Admin."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes


def _windows_work_area(window):
    """Retorna a área útil do monitor que contém a janela, sem a barra de tarefas."""
    if sys.platform != "win32":
        return None

    class MonitorInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetAncestor(window.winfo_id(), 2) or window.winfo_id()
        monitor = user32.MonitorFromWindow(hwnd, 2)
        info = MonitorInfo()
        info.cbSize = ctypes.sizeof(MonitorInfo)
        if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            work = info.rcWork
            return work.left, work.top, work.right, work.bottom
    except (AttributeError, OSError, TypeError):
        pass
    return None


def center_window(
    window,
    width: int,
    height: int,
    parent=None,
    max_width_fraction: float = 0.94,
    max_height_fraction: float = 0.94,
):
    """Centraliza sem deixar a escala do CustomTkinter ultrapassar o monitor."""
    window.update_idletasks()

    if parent is not None and parent.winfo_exists() and parent.winfo_viewable():
        left = parent.winfo_rootx()
        top = parent.winfo_rooty()
        right = left + parent.winfo_width()
        bottom = top + parent.winfo_height()
    else:
        work_area = _windows_work_area(window)
        if work_area:
            left, top, right, bottom = work_area
        else:
            left = window.winfo_vrootx()
            top = window.winfo_vrooty()
            right = left + window.winfo_vrootwidth()
            bottom = top + window.winfo_vrootheight()

    available_width = max(1, right - left)
    available_height = max(1, bottom - top)
    try:
        window_scaling = max(1.0, float(window._get_window_scaling()))
    except (AttributeError, TypeError, ValueError):
        window_scaling = 1.0

    # CTk aplica o DPI somente ao tamanho informado em geometry(); as posições
    # continuam em pixels físicos. Por isso, o limite precisa voltar para a
    # escala lógica antes de ser entregue ao widget.
    logical_limit_width = int(available_width * max_width_fraction / window_scaling)
    logical_limit_height = int(available_height * max_height_fraction / window_scaling)
    final_width = max(1, min(int(width), logical_limit_width))
    final_height = max(1, min(int(height), logical_limit_height))
    physical_width = round(final_width * window_scaling)
    physical_height = round(final_height * window_scaling)
    x = left + max(0, (available_width - physical_width) // 2)
    y = top + max(0, (available_height - physical_height) // 2)
    window.geometry(f"{final_width}x{final_height}+{x}+{y}")
