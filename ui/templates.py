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
    Dropdown,
    Icon,
    IconDataOrControl,
    InputFilter,
    MainAxisAlignment,
    MenuStyle,
    Number,
    OutlinedBorder,
    PaddingValue,
    Segment,
    StrOrControl,
)
from flet.controls.alignment import Axis
from flet.controls.material.dropdown import DropdownOption


class Overlay(ft.Container):
    def __init__(
        self,
        text_value: str,
        text_size: Number = 32,
        text_color: Optional[ColorValue] = None,
        content: Optional[Control] = None,
        bgcolor: Optional[ColorValue] = None,
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

        if (ft.Page.height or 0) > 575:
            self.menu_height = (ft.Page.height or 0) * 0.45
        else:
            self.menu_height = None

        super().__init__()
        self.border = None
        self.border_radius = 0
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

    def on_resize_change_height(self, height: float):
        for i in self.date_controls_dict.values():
            i.menu_height = height
            i.update()

    def _calendar_button(self, date_picker):
        button_style = ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(
                side=ft.BorderSide(color="#7799b8"),
                radius=0,
            ),
            bgcolor="",
        )
        button = ft.IconButton(
            icon=ft.Icons.DATE_RANGE,
            height=38,
            style=button_style,
            on_click=lambda: self._page.show_dialog(date_picker),
        )
        return button

    def _years(self) -> None:
        year = dt.date.today().year
        years = list(map(str, range(year + 2, year - 21, -1)))
        self._dropdown(
            name="years",
            hint_text="Год",
            elements=years,
            on_select=self._on_select,
            menu_height=self.menu_height,
        )

    def _months(self) -> None:
        self._dropdown(
            name="months",
            hint_text="Месяц",
            elements=self.months_,
            on_select=self._on_select,
            menu_height=self.menu_height,
        )

    def _days(self, year: int, month: int) -> None:
        num_days = calendar.monthrange(year, month)[1]
        days = list(map(str, range(1, num_days + 1)))
        self._dropdown(
            name="days",
            hint_text="День",
            elements=days,
            on_select=self._on_select,
            menu_height=self.menu_height,
        )

    def _dropdown(self, name: str, elements: Iterable, **kwargs) -> None:
        """
        Transform list to "ft.dropdown.Option"
        list and add my components list.
        """
        self.date_controls_dict[name] = ft.Dropdown(
            options=[ft.dropdown.Option(x) for x in elements],
            border_radius=ft.BorderRadius.all(0),
            border_color="#7799b8",
            menu_style=ft.MenuStyle(padding=0, visual_density=ft.VisualDensity.COMPACT),
            height=38,
            expand=True,
            dense=True,
            **kwargs,
        )

    def _on_select(self, e) -> None:
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
        content: Optional[ft.StrOrControl] = None,
        tooltip: ft.TooltipValue | None = None,
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
            content=content,
            tooltip=tooltip,
            icon=icon,
            on_click=on_click,
            disabled=disabled,
            height=height,
            width=width,
            expand=expand,
            *args,
            **kwargs,
        )

        self.style = ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6))


class StyledIconButton(ft.IconButton):
    def __init__(
        self,
        icon: Optional[IconDataOrControl] = None,
        tooltip: ft.TooltipValue | None = None,
        height: Optional[Number] = 36,
        width: Optional[Number] = 160,
        expand: bool | int | None = True,
        on_click: Optional[ControlEventHandler[ft.IconButton]] = None,
        disabled: bool = False,
        *args,
        **kwargs,
    ):
        super().__init__(
            icon=icon,
            tooltip=tooltip,
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
        dense: Optional[bool] = True,
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


class StyledDropdown(ft.Dropdown):
    def __init__(
        self,
        value: str | None = None,
        text: str | None = None,
        options: list[DropdownOption] | None = None,
        enable_filter: bool = False,
        enable_search: bool = True,
        editable: bool = True,
        menu_height: Number | None = 10,
        menu_width: Number | None = None,
        menu_style: MenuStyle | None = ft.MenuStyle(
            padding=ft.Padding.all(0),
            visual_density=ft.VisualDensity.COMPACT,
        ),
        input_filter: InputFilter | None = None,
        trailing_icon: IconDataOrControl | None = None,
        leading_icon: IconDataOrControl | None = None,
        on_select: ControlEventHandler[Dropdown] | None = None,
        on_text_change: ControlEventHandler[Dropdown] | None = None,
        on_focus: ControlEventHandler[Dropdown] | None = None,
        label: StrOrControl | None = None,
        border_width: Number = 1,
        border_color: ColorValue | None = "#7799b8",
        border_radius: BorderRadiusValue | None = 1,
        dense: bool = True,
        filled: bool = False,
        helper_text: str | None = None,
        expand: bool | int | None = True,
        height: Number | None = 40,
    ):
        super().__init__(
            value=value,
            text=text,
            options=options or [],
            enable_filter=enable_filter,
            enable_search=enable_search,
            editable=editable,
            menu_height=menu_height,
            menu_width=menu_width,
            menu_style=menu_style,
            input_filter=input_filter,
            trailing_icon=trailing_icon,
            leading_icon=leading_icon,
            on_select=on_select,
            on_text_change=on_text_change,
            on_focus=on_focus,
            label=label,
            border_width=border_width,
            border_color=border_color,
            border_radius=border_radius,
            dense=dense,
            filled=filled,
            helper_text=helper_text,
            expand=expand,
            height=height,
        )


class WarnPopup(ft.SnackBar):
    def __init__(self, text):
        self.text = text
        super().__init__(content=self.warn_content(self.text))

        self.elevation = 0
        self.duration = 2600
        self.margin = ft.Margin.only(bottom=50)
        self.bgcolor = ft.Colors.TRANSPARENT
        self.behavior = ft.SnackBarBehavior.FLOATING

    def warn_content(self, text):
        bg_color = "#384759"
        container = ft.Container(
            border=ft.Border.all(12, bg_color),
            border_radius=ft.BorderRadius.all(9),
            bgcolor=bg_color,
            content=ft.Text(
                value=text,
                color=ft.Colors.WHITE,
                text_align=ft.TextAlign.CENTER,
            ),
        )
        return ft.Row([container], alignment=ft.MainAxisAlignment.CENTER)


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
