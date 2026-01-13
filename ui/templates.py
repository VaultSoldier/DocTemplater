import calendar
import datetime as dt
from typing import Callable, Iterable, List, Optional, Tuple, Union

import flet as ft
from babel.dates import format_date
from flet import (
    Alignment,
    Blur,
    BorderRadiusValue,
    ColorValue,
    Control,
    ControlEventHandler,
    Icon,
    IconDataOrControl,
    InputFilter,
    MainAxisAlignment,
    Number,
    OutlinedBorder,
    PaddingValue,
    Segment,
)
from flet.controls.alignment import Axis


class Overlay(ft.Container):
    def __init__(
        self,
        text_value: str = "Выберите файл...",
        text_size: Number = 32,
        text_color: Optional[ColorValue] = "",
        content: Optional[Control] = None,
        bgcolor: Optional[ColorValue] = "dark",
        blend_mode=ft.BlendMode.OVERLAY,
        blur: Union[
            None, float, int, Tuple[Union[float, int], Union[float, int]], Blur
        ] = 10,
        visible: bool = False,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        text = ft.Text(
            text_value,
            text_align=ft.TextAlign.CENTER,
            weight=ft.FontWeight.BOLD,
            size=text_size,
            color=text_color,
        )
        self.content = content or text
        self.bgcolor = bgcolor
        self.blend_mode = blend_mode
        self.blur = blur
        self.alignment = Alignment.CENTER
        self.visible = visible


# NOTE: DatePicker write on_change to date_controls_dict
class DateRow(ft.Container):
    date_controls_dict = dict()
    months_ = [
        format_date(dt.date(2025, i, 1), "MMMM", locale="ru")
        for i in range(1, 13)  # "MMMM" = тип падежа
    ]
    dt_format = "%Y,%B,%d,%H,%M"

    def __init__(
        self, page: ft.Page, date_picker: ft.DatePicker, on_select: Callable
    ) -> None:
        self._page = page

        # INFO: Enable for ft.Dropdown()
        # if (ft.Page.height or 0) > 575:
        #     self.menu_height = (ft.Page.height or 0) * 0.45
        # else:
        #     self.menu_height = None

        super().__init__()
        self.border = ft.Border.all(1, color="#7799b8")
        self.border_radius = 1
        self.padding = 0
        self.expand = True
        self.on_select = on_select or (lambda x: None)

        self._years()
        self._months()

        today = dt.date.today()
        init_year = today.year
        init_month = today.month
        self._days(init_year, init_month)

        self.content = ft.Row(
            controls=[
                self.date_controls_dict["years"],
                self.date_controls_dict["months"],
                self.date_controls_dict["days"],
                self._calendar_button(date_picker),
            ],
            spacing=0,
        )

        self.value = {
            "years": str(init_year),
            "months": self.months_[init_month - 1],
            "days": str(today.day),
        }

    # INFO: Enable for ft.Dropdown()
    # def on_resize_change_height(self, height: float):
    #     height = height * 0.45
    #     for dd in self.date_controls_dict.values():
    #         dd.menu_height = height
    #         dd.update()

    def _calendar_button(self, date_picker):
        return ft.IconButton(
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=9),
                bgcolor="",
            ),
            height=38,
            icon=ft.Icons.DATE_RANGE,
            on_click=lambda _: self._page.show_dialog(date_picker),
        )

    def _years(self) -> None:
        year = dt.date.today().year
        years = list(map(str, range(year + 2, year - 21, -1)))
        self._dropdown(
            name="years",
            hint_text="Год",
            elements=years,
            on_change=self._on_change,
            # max_menu_height=self.menu_height,
        )

    def _months(self) -> None:
        self._dropdown(
            name="months",
            hint_text="Месяц",
            elements=self.months_,
            on_change=self._on_change,
            # max_menu_height=self.menu_height,
        )

    def _days(self, year: int, month: int) -> None:
        num_days = calendar.monthrange(year, month)[1]
        days = list(map(str, range(1, num_days + 1)))
        self._dropdown(
            name="days",
            hint_text="День",
            elements=days,
            on_change=self._on_change,
            # max_menu_height=self.menu_height,
        )

    def _dropdown(self, name: str, elements: Iterable, **kwargs) -> None:
        """
        Transform list to "ft.dropdown.Option"
        list and add my components list.
        """
        self.date_controls_dict[name] = ft.DropdownM2(
            options=[ft.dropdownm2.Option(x) for x in elements],
            # menu_style=ft.MenuStyle(visual_density=ft.VisualDensity.COMPACT),
            height=38,
            item_height=36,
            expand=True,
            # dense=True,
            **kwargs,
        )

    def _on_change(self, e) -> None:
        self.on_select(self.value)
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

        self._page.update

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
            self._page.update
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
            self._page.update
            return

        try:
            day_int = int(day_val)
            days_dd.value = str(day_int) if 1 <= day_int <= num_days else None
        except ValueError:
            days_dd.value = None
        self._page.update


class StyledSegmentedButton(ft.SegmentedButton):
    def __init__(
        self,
        selected: List[str],
        show_selected_icon: bool = False,
        segments: List[Segment] = [],
        expand: Union[None, bool, int] = True,
        direction: Optional[Axis] = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            selected=selected,
            show_selected_icon=show_selected_icon,
            segments=segments,
            expand=expand,
            direction=direction,
            *args,
            **kwargs,
        )

        self.style = ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6))


class StyledButton(ft.Button):
    def __init__(
        self,
        text: Optional[str] = None,
        height: Optional[Number] = 36,
        width: Optional[Number] = 160,
        expand: bool | int | None = True,
        icon: Optional[IconDataOrControl] = None,
        on_click: Optional[ControlEventHandler[ft.Button]] = None,
        disabled: bool = False,
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
        label_style: Optional[ft.TextStyle] = None,
        hint_text: Optional[str] = None,
        input_filter: Optional[InputFilter] = None,
        border_color: Optional[ColorValue] = "#7799b8",
        border_radius: Optional[BorderRadiusValue] = 1,
        max_length: Optional[int] = None,
        expand: Optional[bool | int] = None,
        dense: Optional[bool] = None,
        icon: Optional[Icon] = None,
        on_change=None,
        *args,
        **kwargs,
    ):
        super().__init__(
            label=label,
            label_style=label_style,
            hint_text=hint_text,
            input_filter=input_filter,
            border_color=border_color,
            border_radius=border_radius,
            max_length=max_length,
            expand=expand,
            dense=dense,
            icon=icon,
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
        self.margin = ft.Margin.only(bottom=50)
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
            border=ft.Border.all(12, bg_color),
            border_radius=ft.border_radius.all(9),
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
        content_padding=ft.Padding.only(left=14, right=14, top=14, bottom=0),
        actions_padding=ft.Padding.only(left=14, right=14, top=4, bottom=14),
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
