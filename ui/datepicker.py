import locale
from typing import Callable, Optional
from flet import (
    BorderSide,
    ButtonStyle,
    Container,
    ControlEvent,
    Column,
    IconButton,
    MainAxisAlignment,
    ControlState,
    RoundedRectangleBorder,
    Row,
    Text,
    TextButton,
    Colors,
    Icons,
)
from flet.core.types import DateTimeValue
import flet as ft
import calendar
from datetime import datetime, timedelta
import datetime as dt

locale.setlocale(locale.LC_TIME, "ru_RU.UTF-8")


# WARNING: Incomplete custom DatePicker widget
# TODO: Implement from DATE to DATE
# TODO: Block year/month arrows if end or start is locked
# TODO: Fix UI (Dropdowns, min width)
class DatePicker(Container):
    @property
    def selected_data(self):
        return self.selected

    PREV_MONTH = "PM"
    NEXT_MONTH = "NM"
    PREV_YEAR = "PY"
    NEXT_YEAR = "NY"

    EMPTY = ""
    WHITE_SPACE = " "

    DELTA_MONTH_WEEK = 5
    DELTA_YEAR_WEEK = 52

    WEEKEND_DAYS = [5, 6]

    CELL_SIZE = 38
    LAYOUT_WIDTH = 390
    LAYOUT_MIN_HEIGHT = 280
    LAYOUT_MAX_HEIGHT = 320
    LAYOUT_DT_MIN_HEIGHT = 320
    LAYOUT_DT_MAX_HEIGHT = 360

    def __init__(
        self,
        selected_date: list[datetime] | None = None,
        disable_from: Optional[DateTimeValue] = None,
        disable_to: Optional[DateTimeValue] = None,
        hide_prev_next_month_days: bool = False,
        first_weekday: int = 0,
        on_change: Optional[Callable] = None,
    ):
        self.selected = selected_date if selected_date else []
        self.disable_from = disable_from
        self.disable_to = disable_to
        self.hide_prev_next_month_days = hide_prev_next_month_days
        self.first_weekday = first_weekday
        self.on_change = on_change or (lambda x: None)

        self.now = datetime.now()
        self.yy: int = self.now.year
        self.mm: int = self.now.month
        self.dd: int = self.now.day
        self.cal = calendar.Calendar(first_weekday)

        super().__init__()

        rows = self._create_layout(self.yy, self.mm)

        self.content = Row(alignment=MainAxisAlignment.CENTER, controls=rows)
        self.height = self.LAYOUT_MAX_HEIGHT
        self.padding = 12

    def _on_change(self, e) -> None:
        self.on_change(e)

    def _get_current_month(self, year, month):
        return self.cal.monthdatescalendar(year, month)

    def _create_calendar(self, year, month: int, hide_ymhm=False):
        week_rows_controls = []
        week_rows_days_controls = []
        today = datetime.now()

        days = self._get_current_month(year, month)

        ym = self._year_month_selectors(year, month, hide_ymhm)
        week_rows_controls.append(Column([ym], alignment=MainAxisAlignment.START))

        labels = Row(
            alignment=MainAxisAlignment.CENTER, controls=self._row_labels(), spacing=18
        )
        week_rows_controls.append(Column([labels], alignment=MainAxisAlignment.START))

        weeks_rows_num = len(self._get_current_month(year, month))

        for week in range(0, weeks_rows_num):
            row = []

            for d in days[week]:
                d = datetime(d.year, d.month, d.day)

                month = d.month
                is_main_month = True if month == self.mm else False

                if self.hide_prev_next_month_days and not is_main_month:
                    row.append(
                        Text(
                            "",
                            width=self.CELL_SIZE,
                            height=self.CELL_SIZE,
                        )
                    )
                    continue

                dt_weekday = d.weekday()
                day = d.day
                is_weekend = False
                is_day_disabled = False
                text_color = None
                border_side = None
                bg = None
                # week end bg color
                if dt_weekday in self.WEEKEND_DAYS:
                    text_color = Colors.RED_500
                    is_weekend = True

                # current day bg
                if (
                    is_main_month
                    and day == self.dd
                    and self.dd == today.day
                    and self.mm == today.month
                    and self.yy == today.year
                ):
                    border_side = BorderSide(2, Colors.BLUE)
                elif (is_weekend) and (not is_main_month or is_day_disabled):
                    text_color = Colors.RED_200
                    bg = None
                elif not is_main_month and is_day_disabled:
                    text_color = Colors.BLACK38
                    bg = None
                elif not is_main_month:
                    text_color = Colors.BLUE_200
                    bg = None
                else:
                    bg = None

                # selected days
                selected_numbers = len(self.selected)
                if selected_numbers > 0 and selected_numbers < 3 and d in self.selected:
                    bg = Colors.BLUE_400

                row.append(
                    TextButton(
                        text=str(day),
                        data=d,
                        width=self.CELL_SIZE,
                        height=self.CELL_SIZE,
                        disabled=is_day_disabled,
                        style=ButtonStyle(
                            color=text_color,
                            bgcolor=bg,
                            padding=0,
                            shape={
                                ControlState.DEFAULT: RoundedRectangleBorder(radius=20),
                            },
                            side=border_side,
                        ),
                        on_click=self._select_date,
                    )
                )

            week_rows_days_controls.append(
                Row(alignment=MainAxisAlignment.CENTER, controls=row, spacing=18)
            )

        week_rows_controls.append(
            Column(
                week_rows_days_controls, alignment=MainAxisAlignment.START, spacing=0
            )
        )

        return week_rows_controls

    def _year_month_selectors(self, year, month, hide_ymhm=False):
        prev_year = (
            IconButton(
                icon=Icons.ARROW_BACK,
                data=self.PREV_YEAR,
                on_click=self._adjust_calendar,
            )
            if not hide_ymhm
            else Text(
                self.EMPTY,
                height=self.CELL_SIZE,
            )
        )
        next_year = (
            IconButton(
                icon=Icons.ARROW_FORWARD,
                data=self.NEXT_YEAR,
                on_click=self._adjust_calendar,
            )
            if not hide_ymhm
            else Text(self.EMPTY)
        )
        prev_month = (
            IconButton(
                icon=Icons.ARROW_BACK,
                data=self.PREV_MONTH,
                on_click=self._adjust_calendar,
            )
            if not hide_ymhm
            else Text(self.EMPTY)
        )
        next_month = (
            IconButton(
                icon=Icons.ARROW_FORWARD,
                data=self.NEXT_MONTH,
                on_click=self._adjust_calendar,
            )
            if not hide_ymhm
            else Text(self.EMPTY)
        )

        current_year = dt.date.today().year
        first_date = current_year - 20
        last_date = current_year + 2

        # INFO: UPDATE LOGIC
        def _update_calendar_year(e):
            selected_year = int(e.control.value)

            self.now = self.now.replace(year=selected_year)
            self.yy = selected_year
            self._update_calendar()

        year_options = [
            ft.dropdown.Option(text=str(options))
            for options in range(first_date, last_date)
        ]
        dropdown_years = ft.Dropdown(
            dense=True,
            expand=True,
            menu_height=400,
            text_size=14,
            # border=ft.InputBorder.NONE,
            options=year_options,
            value=year,
            on_change=_update_calendar_year,
        )

        ym_controls_year = Row(
            [
                prev_year,
                ft.Container(content=dropdown_years, width=100, height=35),
                next_year,
            ],
            spacing=0,
        )

        def _update_calendar_month(e):
            selected_month = datetime.strptime(e.control.value, "%B").month
            last_day = calendar.monthrange(self.yy, self.mm)[1]
            day = min(self.now.day, last_day)

            self.now = self.now.replace(month=selected_month, day=day)
            self.mm = selected_month
            self._update_calendar()

        year_options = [
            ft.dropdown.Option(text=options)
            for options in list(calendar.month_name[1:])
        ]
        dropdown_months = ft.Dropdown(
            dense=True,
            expand=True,
            # menu_height=400,
            # border=ft.InputBorder.NONE,
            options=year_options,
            value=calendar.month_name[int(month)],
            on_change=_update_calendar_month,
        )
        ym_controls_month = Row(
            controls=[
                prev_month,
                ft.Container(content=dropdown_months, width=90, height=35),
                next_month,
            ],
            spacing=0,
        )
        ym = Row(
            controls=[
                ym_controls_year,
                ym_controls_month,
            ],
            spacing=0,
            alignment=MainAxisAlignment.SPACE_BETWEEN,
        )

        return ym

    def _row_labels(self):
        label_row = []
        days_label = calendar.weekheader(2).split(self.WHITE_SPACE)

        for _ in range(0, self.first_weekday):
            days_label.append(days_label.pop(0))

        for i in days_label:
            button = TextButton(
                width=self.CELL_SIZE,
                height=self.CELL_SIZE,
                disabled=True,
                text=i,
                style=ButtonStyle(
                    padding=0,
                    shape={
                        ControlState.DEFAULT: RoundedRectangleBorder(radius=20),
                    },
                ),
            )
            label_row.append(button)

        return label_row

    def _create_layout(self, year, month):
        rows = []

        week_rows_controls = self._create_calendar(year, month)
        rows.append(
            Column(
                alignment=MainAxisAlignment.CENTER,
                controls=week_rows_controls,
                width=self.LAYOUT_WIDTH,
                spacing=10,
            )
        )

        return rows

    def _prev_next_month(self, year, month):
        delta = timedelta(weeks=self.DELTA_MONTH_WEEK)
        current = datetime(year, month, 15)
        prev = current - delta
        next = current + delta
        return prev, next

    def _select_date(self, e: ControlEvent):
        date_clicked: datetime = e.control.data

        if len(self.selected) == 1 and date_clicked in self.selected:
            self.selected.remove(date_clicked)
            return

        self.selected[:] = [date_clicked]

        self._on_change(self.selected)
        self._update_calendar()

    def _adjust_calendar(self, e: ControlEvent):
        delta = timedelta(0)
        if e.control.data == self.PREV_MONTH or e.control.data == self.NEXT_MONTH:
            delta = timedelta(weeks=self.DELTA_MONTH_WEEK)
        if e.control.data == self.PREV_YEAR or e.control.data == self.NEXT_YEAR:
            delta = timedelta(weeks=self.DELTA_YEAR_WEEK)

        if e.control.data == self.PREV_MONTH or e.control.data == self.PREV_YEAR:
            self.now = self.now - delta
        if e.control.data == self.NEXT_MONTH or e.control.data == self.NEXT_YEAR:
            self.now = self.now + delta

        self.mm = self.now.month
        self.yy = self.now.year
        self._update_calendar()

    def _update_calendar(self):
        self.content = Row(self._create_layout(self.yy, self.mm))
        self.update()


if __name__ == "__main__":
    year = dt.date.today().year

    from_date = dt.date(year - 20, 1, 1)
    to_date = dt.date(year + 2, 12, 31)

    def main(page: ft.Page):
        def button_clicked(e):
            page.open(dlg_modal)
            page.update()

        dlg_modal = ft.AlertDialog(
            alignment=ft.alignment.center,
            content=DatePicker(
                disable_from=from_date,
                disable_to=to_date,
                on_change=lambda e: print(e),
            ),
            actions=[
                ft.TextButton(
                    "Cancel",
                ),
                ft.TextButton(
                    "Confirm",
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            actions_padding=5,
            content_padding=0,
        )

        page.add(
            ft.Row(
                expand=True,
                controls=[ft.Button(text="Test", expand=True, on_click=button_clicked)],
            ),
        )

    ft.app(main)
