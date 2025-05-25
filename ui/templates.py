from typing import Callable, Iterable, List, Optional, Set, Tuple, Union
import flet as ft
from flet import Blur, Control, InputFilter, OptionalNumber
import datetime as dt
import locale
import calendar
from flet.core.buttons import OutlinedBorder
from flet.core.segmented_button import Segment
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

        super().__init__()
        self.border = ft.border.all(1)
        self.border_radius = 2
        self.expand = True
        self.page: ft.Page = page
        self.on_change = on_change or (lambda x: None)
        self.padding = 0

        self._years(self.menu_height)
        self._months(self.menu_height)

        today = dt.date.today()
        init_year = today.year
        init_month = today.month
        self._days(self.menu_height, init_year, init_month)

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

        self.value = {
            "years": str(init_year),
            "months": self.months_[init_month - 1],
            "days": str(today.day),
        }

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

    def _days(self, menu_height, year: int, month: int) -> None:
        num_days = calendar.monthrange(year, month)[1]
        days = list(map(str, range(1, num_days + 1)))
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
        year = int(self.date_controls_dict["years"].value)
        month = self.months_.index(self.date_controls_dict["months"].value) + 1
        max_day = calendar.monthrange(year, month)[1]
        days_dd = self.date_controls_dict["days"]
        days_dd.options = [ft.dropdown.Option(str(d)) for d in range(1, max_day + 1)]
        prev = days_dd.value

        try:
            prev_int = int(prev) if prev is not None else max_day
        except ValueError:
            prev_int = max_day
        days_dd.value = str(min(prev_int, max_day))

        self.page.update()

    @property
    def value(self) -> list:
        return [c.value for c in self.date_controls_dict.values()]

    @value.setter
    def value(self, values: list | dict):
        if isinstance(values, list):
            year_val, month_val, day_val = values
        else:
            year_val = values.get("years")
            month_val = values.get("months")
            day_val = values.get("days")

        years_dd = self.date_controls_dict["years"]
        months_dd = self.date_controls_dict["months"]
        days_dd = self.date_controls_dict["days"]

        years_dd.value = year_val
        months_dd.value = month_val

        if not year_val or not month_val:
            days_dd.options = []
            days_dd.value = None
            self.page.update()
            return

        try:
            year = int(year_val)
            month = self.months_.index(month_val) + 1
        except ValueError:
            days_dd.options = []
            days_dd.value = None
            self.page.update()
            return

        num_days = calendar.monthrange(year, month)[1]
        opts = [ft.dropdown.Option(str(d)) for d in range(1, num_days + 1)]
        days_dd.options = opts

        if day_val is None:
            days_dd.value = None
            self.page.update()
            return

        try:
            day_int = int(day_val)
            days_dd.value = str(day_int) if 1 <= day_int <= num_days else None
        except ValueError:
            days_dd.value = None
        self.page.update()


class StyledSegmentedButton(ft.SegmentedButton):
    def __init__(
        self,
        segments: List[Segment] = [],
        selected: Optional[Set] = None,
        show_selected_icon: Optional[bool] = False,
        expand: Union[None, bool, int] = True,
        *args,
        **kwargs,
    ):
        super().__init__(
            segments=segments,
            selected=selected,
            show_selected_icon=show_selected_icon,
            expand=expand,
            *args,
            **kwargs,
        )

        self.style = ft.ButtonStyle(shape=ft.RoundedRectangleBorder(6))
        # selected_icon=ft.Icon(ft.Icons.CHECK_BOX_OUTLINED)


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
        super().__init__(
            text,
            icon,
            on_click=on_click,
            disabled=disabled,
            height=height,
            width=width,
            expand=expand,
            *args,
            **kwargs,
        )

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
        super().__init__(
            label=label,
            hint_text=hint_text,
            input_filter=input_filter,
            border_color=border_color,
            border_radius=border_radius,
            max_length=max_length,
            expand=expand,
            suffix_icon=suffix_icon,
            on_change=on_change,
            *args,
            **kwargs,
        )


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
        shape: Optional[OutlinedBorder] = ft.RoundedRectangleBorder(radius=9),
        content_padding=ft.padding.only(left=14, right=14, top=14, bottom=0),
        actions_padding=ft.padding.only(left=14, right=14, top=4, bottom=14),
        action_button_padding: Optional[PaddingValue] = 10,
        actions_alignment: Optional[MainAxisAlignment] = MainAxisAlignment.CENTER,
        *args,
        **kwargs,
    ):
        super().__init__(
            shape=shape,
            content_padding=content_padding,
            actions_padding=actions_padding,
            action_button_padding=action_button_padding,
            actions_alignment=actions_alignment,
            *args,
            **kwargs,
        )
