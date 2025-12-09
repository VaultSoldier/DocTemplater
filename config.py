import flet as ft
from dataclasses import dataclass


@dataclass
class Config:
    fontsize: int
    fontweight: ft.FontWeight


config = Config(fontsize=16, fontweight=ft.FontWeight.BOLD)
