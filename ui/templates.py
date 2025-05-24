from typing import Callable, Iterable, Optional, Tuple, Union
import flet as ft
from flet import Blur, Control, InputFilter, OptionalNumber
import datetime as dt
import locale
import calendar
from flet.core.buttons import OutlinedBorder
from flet.core.types import (
    BorderRadiusValue,
    ColorValue,
    IconValue,
    IconValueOrControl,
    OptionalControlEventCallable,
    MainAxisAlignment,
    PaddingValue,
)


class Overlay(ft.Container):
    def __init__(
        self,
        text_value: Optional[str] = "Выберите файл...",
        text_size: OptionalNumber = 32,
        text_color: Optional[ColorValue] = "white",
        content: Optional[Control] = None,
        bgcolor: Optional[ColorValue] = "dark",
        blend_mode=ft.BlendMode.OVERLAY,
        blur: Union[
            None, float, int, Tuple[Union[float, int], Union[float, int]], Blur
        ] = 10,
        visible: Optional[bool] = False,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        text = ft.Text(
            text_value, size=text_size, color=text_color, weight=ft.FontWeight.BOLD
        )
        self.content = content or text
        self.bgcolor = bgcolor
        self.blend_mode = blend_mode
        self.blur = blur
        self.alignment = ft.alignment.center
        self.visible = visible


# NOTE: DatePicker write on_change to date_controls_dict
class DateRow(ft.Container):
    locale.setlocale(category=locale.LC_TIME, locale="ru_RU.UTF-8")

    date_controls_dict = dict()
    months_ = list(calendar.month_name)[1:]
    dt_format = "%Y,%B,%d,%H,%M"

    def __init__(
        self, date_picker: ft.DatePicker, page: ft.Page, on_change: Callable
    ) -> None:
        if (page.height or 0) > 575:
            self.menu_height = (page.height or 0) * 0.45
        else:
            pass
        self.dropdown_width = (page.width or 0) * 0.16

        super().__init__()
        self.border = ft.border.all(1)
        self.border_radius = 2
        self.expand = True
        self.page: ft.Page = page
        self.on_change = on_change or (lambda x: None)
        self.padding = 0

        for attr in ["_years", "_months", "_days"]:
            getattr(self, attr)(self.menu_height)

        self.content = ft.Row(
            controls=[
                ft.Container(
                    content=self.date_controls_dict["years"], height=46, expand=True
                ),
                ft.Container(
                    content=self.date_controls_dict["months"], height=46, expand=True
                ),
                ft.Container(
                    content=self.date_controls_dict["days"], height=46, expand=True
                ),
                self._calendar_button(date_picker, page),
            ],
            spacing=0,
            expand=True,
        )

    def on_resize_change_height(self, height: float):
        height = height * 0.45

        for dd in self.date_controls_dict.values():
            dd.menu_height = height
            dd.update()

    def _calendar_button(self, date_picker, page):
        return ft.Container(
            margin=ft.margin.only(left=3, right=3),
            content=ft.IconButton(
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=9),
                    bgcolor="#2c323e",
                ),
                icon=ft.Icons.DATE_RANGE,
                on_click=lambda _: page.open(date_picker),
            ),
        )

    def _years(self, menu_height) -> None:
        year = dt.date.today().year
        years = list(map(str, range(year + 2, year - 21, -1)))
        self._dropdown(
            name="years",
            elements=years,
            on_change=self._on_change,
            hint_text="Год",
            menu_height=menu_height,
        )

    def _months(self, menu_height) -> None:
        self._dropdown(
            name="months",
            elements=self.months_,
            on_change=self._on_change,
            hint_text="Месяц",
            menu_height=menu_height,
        )

    def _days(
        self, menu_height, year: int = dt.date.today().year, month: int = 1
    ) -> None:
        day = calendar.monthrange(year, month)[1]
        days = range(1, day + 1)
        self._dropdown(
            name="days",
            elements=days,
            on_change=self._on_change_wrapper,
            hint_text="День",
            menu_height=menu_height,
        )

    def _dropdown(self, name: str, elements: Iterable, **kwargs) -> None:
        """
        Transform list to "ft.dropdown.Option"
        list and add my components list.
        """
        self.date_controls_dict[name] = ft.Dropdown(
            options=[ft.dropdown.Option(x) for x in elements],
            expand_loose=False,
            filled=True,
            expand=True,
            **kwargs,
        )

    def _on_change_wrapper(self, e):
        self.on_change(self.value)

    def _on_change(self, e) -> None:
        self.on_change(self.value)
        year = self.date_controls_dict["years"].value
        month = self.date_controls_dict["months"].value

        if year and month:
            year = int(year)
            month = self.months_.index(month) + 1
            days = range(1, calendar.monthrange(year, month)[1] + 1)

            self.date_controls_dict["days"].options = [
                ft.dropdown.Option(str(d)) for d in days
            ]
            self.page.update()

    @property
    def value(self) -> list:
        return [c.value for c in self.date_controls_dict.values()]

    @value.setter
    def value(self, values: list | dict):
        if isinstance(values, list):
            for control, val in zip(self.date_controls_dict.values(), values):
                control.value = val
        elif isinstance(values, dict):
            for key, val in values.items():
                self.date_controls_dict[key].value = val
        self.page.update()


class StyledButton(ft.Button):
    def __init__(
        self,
        text: Optional[str] = None,
        height: OptionalNumber = 38,
        width: OptionalNumber = 160,
        expand: (bool | int | None) = True,
        icon: Optional[IconValue] = None,
        on_click: OptionalControlEventCallable = None,
        disabled: Optional[bool] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.text = text
        self.icon = icon
        self.on_click = on_click
        self.disabled = disabled
        self.height = height
        self.width = width
        self.expand = expand
        self.style = ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6))


class StyledTextField(ft.TextField):
    def __init__(
        self,
        label: Optional[str | Control] = None,
        hint_text: Optional[str] = None,
        input_filter: Optional[InputFilter] = None,
        border_color: Optional[ColorValue] = "#7799b8",
        border_radius: Optional[BorderRadiusValue] = 1,
        max_length: Optional[int] = None,
        expand: Optional[bool | int] = None,
        suffix_icon: Optional[IconValueOrControl] = None,
        on_change: OptionalControlEventCallable = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.label = label
        self.hint_text = hint_text
        self.input_filter = input_filter
        self.border_color = border_color
        self.border_radius = border_radius
        self.max_length = max_length
        self.expand = expand
        self.suffix_icon = suffix_icon
        self.on_change = on_change


class WarnPopup(ft.SnackBar):
    def __init__(self, text):
        self.text = text
        super().__init__(content=self.row())

        self.elevation = 0
        self.duration = 2500
        self.margin = ft.margin.only(bottom=50)
        self.bgcolor = ft.Colors.TRANSPARENT
        self.behavior = ft.SnackBarBehavior.FLOATING

    def row(self):
        return ft.Row(
            alignment=MainAxisAlignment.CENTER,
            controls=[self.warn_content(self.text)],
        )

    def warn_content(self, text):
        bg_color = "#384759"
        return ft.Container(
            border=ft.border.all(12, bg_color),
            border_radius=ft.border_radius.all(8),
            bgcolor=bg_color,
            content=ft.Text(
                color=ft.Colors.WHITE,
                text_align=ft.TextAlign.CENTER,
                value=text,
            ),
        )


class StyledAlertDialog(ft.AlertDialog):
    def __init__(
        self,
        # custom values
        shape: Optional[OutlinedBorder] = ft.RoundedRectangleBorder(radius=9),
        content_padding=ft.padding.only(left=14, right=14, top=14, bottom=0),
        actions_padding=ft.padding.only(left=14, right=14, top=4, bottom=14),
        action_button_padding: Optional[PaddingValue] = 10,
        actions_alignment: Optional[MainAxisAlignment] = MainAxisAlignment.CENTER,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.content_padding = content_padding
        self.actions_padding = actions_padding
        self.actions_alignment = actions_alignment
        self.shape = shape
        self.action_button_padding = action_button_padding
