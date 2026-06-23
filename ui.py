import flet as ft
import time
import subprocess
import threading

import logging
import platform

import hardware_V2 as hardware

from version import __version__

logging.getLogger("flet").setLevel(logging.WARNING)
logging.getLogger("flet_web").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

def start_GUI(settings, toml, localization, flink, nfc, errors, errors_lock, background_tasks):
    ft.app(target=UI(settings, toml, localization, flink, nfc, errors, errors_lock, background_tasks))

class DigitButton(ft.Button):
    def __init__(self, text, button_clicked, ui):
        super().__init__()
        self.content = ft.Text(text)
        self.data = text
        self.on_click = ui.btn_dec(button_clicked)
        self.expand = 1
        self.padding = 0
        self.style=ft.ButtonStyle(text_style=ft.TextStyle(size=70, weight=ft.FontWeight.BOLD, font_family="Fira Mono"), shape=ft.RoundedRectangleBorder(radius=30))
        self.bgcolor = ft.Colors.WHITE


class NumberPad(ft.Container):
    def __init__(self, ui, callback):
        super().__init__()
        self.number = ""
        self.callback = callback
        self.content = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        DigitButton("1", self.button_clicked, ui),
                        DigitButton("2", self.button_clicked, ui),
                        DigitButton("3", self.button_clicked, ui),
                    ]
                ),
                ft.Row(
                    controls=[
                        DigitButton("4", self.button_clicked, ui),
                        DigitButton("5", self.button_clicked, ui),
                        DigitButton("6", self.button_clicked, ui),
                    ]
                ),
                ft.Row(
                    controls=[
                        DigitButton("7", self.button_clicked, ui),
                        DigitButton("8", self.button_clicked, ui),
                        DigitButton("9", self.button_clicked, ui),
                    ]
                ),
                ft.Row(
                    controls=[
                        ft.Button(content=ft.Icon(ft.Icons.CLOSE, color=ft.Colors.RED, size=78),
                            bgcolor = ft.Colors.WHITE, 
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=30)), 
                            on_click=ui.btn_dec(self.button_clicked), 
                            data="x",
                            expand=1),
                        DigitButton("0", self.button_clicked, ui),
                        ft.Button(content=ft.Icon(ft.Icons.CHECK, color=ft.Colors.GREEN, size=78),
                            bgcolor = ft.Colors.WHITE, 
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=30)), 
                            on_click=ui.btn_dec(self.button_clicked), 
                            data="ok",
                            expand=1),
                    ]
                ),
            ]
        )

    def button_clicked(self, e):
        data = e.control.data
        self.callback(data)


class UI():
    def __init__(self, settings, toml, localization, flink, nfc, errors, errors_lock, background_tasks):
        self.__page = None
        self.main_color = settings["UI_color"]
        self.settings = settings
        self.localization = localization
        self.language = settings["UI_language"]
        self.text = localization[self.language]
        self.toml = toml
        self.flink = flink
        self.nfc = nfc
        self.errors = errors
        self.errors_lock = errors_lock
        self.background_tasks = background_tasks
        
    def __call__(self, flet_page: ft.Page):
        self.page = flet_page
        self.page.title = "Schlüsselkasten V2"
        self.page.window.height = 800
        self.page.window.width = 480
        self.page.window.frameless = True
        self.page.window.full_screen = True
        self.page.bgcolor = ft.Colors.GREY_200
        self.page.theme = ft.Theme(color_scheme_seed=self.main_color)
        self.page.fonts = {"Fira Mono": "/fonts/FiraMono-Regular.ttf"}
        self.radio_label_style = ft.TextStyle(color=self.main_color, weight=ft.FontWeight.BOLD, size=24)
        # build the UI
        self.build_ui()
        threading.Thread(
            target=self.background_tasks,
            args=(self,),
            daemon=True,
            name="background_tasks",
        ).start()

    def build_ui(self):
        # Remove all controls before rebuilding
        self.page.controls.clear()
        # all the different page setups
        # welcome page
        self.welcome = ft.Column(
            controls=[
                ft.Card(ft.Container(ft.Image(src="/images/logo.png", width=800, height=100, fit=ft.BoxFit.CONTAIN,), padding=10), bgcolor=ft.Colors.WHITE, margin=0),
                ft.Card(content=ft.Container(content=ft.Text(value=self.text["welcome_title"], color=self.main_color, text_align=ft.TextAlign.LEFT, size=35, style=ft.TextStyle(weight=ft.FontWeight.BOLD)), padding=15), bgcolor=ft.Colors.WHITE, margin=0),
                ft.Button(on_click=self.btn_dec(lambda _: self.page_reconfigure(self.booking)), icon=ft.Icons.EVENT, icon_color=ft.Colors.WHITE, content=f" {self.text['booking']}", color = ft.Colors.WHITE, bgcolor = self.main_color, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=30), padding=25, icon_size=45, text_style=ft.TextStyle(size=35))),
                ft.Button(on_click=self.btn_dec(lambda _: self.page_reconfigure(self.borrowing)), icon=ft.Icons.OUTPUT,icon_color=ft.Colors.WHITE, content=f" {self.text['borrowing']}", color = ft.Colors.WHITE, bgcolor = self.main_color, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=30), padding=25, icon_size=45, text_style=ft.TextStyle(size=35))),
                ft.Button(on_click=self.btn_dec(lambda _: self.page_reconfigure(self.returning)), icon=ft.Icons.EXIT_TO_APP,icon_color=ft.Colors.WHITE, content=f" {self.text['returning']}", color = ft.Colors.WHITE, bgcolor = self.main_color, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=30), padding=25, icon_size=45, text_style=ft.TextStyle(size=35))),
            ],
            spacing=30
        )
        # user help page
        self.help = ft.Column(
            controls=[
                ft.Card(content=ft.Container(content=ft.Text(value=self.text["help_title"], color=self.main_color, text_align=ft.TextAlign.LEFT, size=35, style=ft.TextStyle(weight=ft.FontWeight.BOLD)), padding=10), bgcolor=ft.Colors.WHITE, margin=0),
                ft.Card(content=ft.Container(content=ft.Text(value=self.text["help_intro"], color=self.main_color, text_align=ft.TextAlign.LEFT, size=19, style=ft.TextStyle(weight=ft.FontWeight.BOLD)), padding=10, margin=0, expand=True), bgcolor=ft.Colors.WHITE, margin=0),
                ft.Card(content=ft.Row([
                    ft.Container(ft.Icon(ft.Icons.EVENT, color=self.main_color, size=45), padding=10),
                    ft.Container(content=ft.Text(value=self.text["help_step1"], color=self.main_color, text_align=ft.TextAlign.LEFT, size=19, style=ft.TextStyle(weight=ft.FontWeight.BOLD)), padding=10, margin=0, expand=True)
                    ], spacing=0), bgcolor=ft.Colors.WHITE, margin=0),
                ft.Card(content=ft.Row([
                    ft.Container(ft.Icon(ft.Icons.OUTPUT, color=self.main_color, size=45), padding=10),
                    ft.Container(content=ft.Text(value=self.text["help_step2"], color=self.main_color, text_align=ft.TextAlign.LEFT, size=19, style=ft.TextStyle(weight=ft.FontWeight.BOLD)), padding=10, margin=0, expand=True)
                    ], spacing=0), bgcolor=ft.Colors.WHITE, margin=0),
                ft.Card(content=ft.Row([
                    ft.Container(ft.Icon(ft.Icons.EXIT_TO_APP, color=self.main_color, size=45), padding=10),
                    ft.Container(content=ft.Text(value=self.text["help_step3"], color=self.main_color, text_align=ft.TextAlign.LEFT, size=19, style=ft.TextStyle(weight=ft.FontWeight.BOLD)), padding=10, margin=0, expand=True)
                    ], spacing=0), bgcolor=ft.Colors.WHITE, margin=0),
                ft.Card(content=ft.Row([
                    ft.Container(ft.Icon(ft.Icons.WARNING, color=self.main_color, size=45), padding=10),
                    ft.Container(content=ft.Text(value=self.text["help_step4"], color=self.main_color, text_align=ft.TextAlign.LEFT, size=19, style=ft.TextStyle(weight=ft.FontWeight.BOLD)), padding=10, margin=0, expand=True)
                    ], spacing=0), bgcolor=ft.Colors.WHITE, margin=0),
            ],
            spacing=10
        )
        
        # service page
        self.compartment  = ""  
        self.service_mode = ft.RadioGroup(content=ft.Column([
            ft.Radio(value="open", label=self.text["service_open"], label_style=self.radio_label_style, active_color=self.main_color),
            ft.Radio(value="program", label=self.text["service_program"], label_style=self.radio_label_style, active_color=self.main_color),
            ft.Radio(value="reset", label=self.text["service_reset"], label_style=self.radio_label_style, active_color=self.main_color)]))
        self.service_mode.value = "open"                        
        self.service = ft.Column(
            controls=[
                ft.Card(content=ft.Container(content=ft.Text(value=self.text["service_menu"], color=self.main_color, text_align=ft.TextAlign.LEFT, size=35, style=ft.TextStyle(weight=ft.FontWeight.BOLD)), padding=10), bgcolor=ft.Colors.WHITE, margin=0),
                ft.Row([
                    ft.Button(content=self.text["close_app"],on_click=self.btn_dec(lambda _: subprocess.call("./stop.sh")), color = ft.Colors.WHITE, bgcolor = self.main_color, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=30), padding=15, text_style=ft.TextStyle(size=24, weight=ft.FontWeight.BOLD)), expand=True),
                    ft.Button(content=self.text["restart_app"], on_click=self.btn_dec(lambda _: subprocess.call(["systemctl", "--user", "restart", "schluesselkasten.service"])), color = ft.Colors.WHITE, bgcolor = self.main_color, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=30), padding=15, text_style=ft.TextStyle(size=24, weight=ft.FontWeight.BOLD)), expand=True),
                ]),
                ft.Row([
                    ft.Button(content=self.text["open_all"],on_click=self.btn_dec(self.open_all_clicked), color = ft.Colors.WHITE, bgcolor = self.main_color, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=30), padding=15, text_style=ft.TextStyle(size=24, weight=ft.FontWeight.BOLD)), expand=True),
                    ft.Button(content=self.text["settings"], on_click=self.btn_dec(lambda _: self.page_reconfigure(self.settings_page)), color = ft.Colors.WHITE, bgcolor = self.main_color, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=30), padding=15, text_style=ft.TextStyle(size=24, weight=ft.FontWeight.BOLD)), expand=True),
                ]),
                ft.Card(ft.Container(self.service_mode, padding = 10), bgcolor=ft.Colors.WHITE, margin=0), NumberPad(self, self.service_callback)
            ],
            spacing=10
        )
        # settings page
        self.settings_sound_switch = ft.Switch(label=self.text["settings_sound"], label_text_style=self.radio_label_style, value=self.settings["UI_sound"], on_change=self.btn_dec(self.toggle_sound), active_color=self.main_color)
        self.settings_haptic_switch = ft.Switch(label=self.text["settings_haptic"], label_text_style=self.radio_label_style, value=self.settings["UI_haptic"], on_change=self.btn_dec(self.toggle_haptic), active_color=self.main_color)
        self.settings_charging_switch = ft.Switch(label=self.text["settings_charging"], label_text_style=self.radio_label_style, value=True, on_change=self.btn_dec(self.toggle_charging), active_color=self.main_color)
        self.settings_accel_alarm_switch = ft.Switch(label=self.text["settings_accel_alarm"], label_text_style=self.radio_label_style, value=self.settings["UI_haptic"], on_change=self.btn_dec(self.toggle_charging), active_color=self.main_color, disabled=True)
        self.settings_brightness_slider = ft.Slider(value=self.settings["brightness_adjustment"], on_change=self.brightness_slider_changed, active_color=self.main_color)
        self.settings_page = ft.Column(
            controls=[
                ft.Card(content=ft.Container(content=ft.Text(value=self.text["settings"], color=self.main_color, text_align=ft.TextAlign.LEFT, size=35, style=ft.TextStyle(weight=ft.FontWeight.BOLD)), padding=10), bgcolor=ft.Colors.WHITE, margin=0),
                self.settings_sound_switch,
                self.settings_haptic_switch,
                self.settings_charging_switch,
                self.settings_accel_alarm_switch,
                ft.Text("Brightness adjustment:", color=self.main_color, size=24, style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
                self.settings_brightness_slider, 
                ft.Button(content=self.text["mounting_mode"], on_click=self.btn_dec(self.mounting_clicked), color = ft.Colors.WHITE, bgcolor = self.main_color, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=30), padding=15, text_style=ft.TextStyle(size=24, weight=ft.FontWeight.BOLD)), expand=True),
                ],
            spacing=20
        )
        # info page
        self.open_comps_text = ft.Text(value="", color=self.main_color, text_align=ft.TextAlign.LEFT, size=16, style=ft.TextStyle(weight=ft.FontWeight.BOLD))
        self.network_text = ft.Text(value="", color=self.main_color, text_align=ft.TextAlign.LEFT, size=16, style=ft.TextStyle(weight=ft.FontWeight.BOLD))
        self.temp_text = ft.Text(value="", color=self.main_color, text_align=ft.TextAlign.LEFT, size=16, style=ft.TextStyle(weight=ft.FontWeight.BOLD))
        self.memory_text = ft.Text(value="", color=self.main_color, text_align=ft.TextAlign.LEFT, 
                              size=16, style=ft.TextStyle(weight=ft.FontWeight.BOLD))
        self.uptime_text = ft.Text(value="", color=self.main_color, text_align=ft.TextAlign.LEFT, size=16, style=ft.TextStyle(weight=ft.FontWeight.BOLD))
        self.error_text = ft.Text(value="", color=self.main_color, text_align=ft.TextAlign.LEFT, size=16, style=ft.TextStyle(weight=ft.FontWeight.BOLD))
        self.brightness_text = ft.Text(value="", color=self.main_color, text_align=ft.TextAlign.LEFT, size=16, style=ft.TextStyle(weight=ft.FontWeight.BOLD))
        self.power_text = ft.Text(value="", color=self.main_color, text_align=ft.TextAlign.LEFT, size=16, style=ft.TextStyle(weight=ft.FontWeight.BOLD))
        self.battery_text = ft.Text(value="", color=self.main_color, text_align=ft.TextAlign.LEFT, size=16, style=ft.TextStyle(weight=ft.FontWeight.BOLD))
        self.update_info()
        self.info = ft.Column([
            ft.Card(ft.Container(ft.Text(value="Info", color=self.main_color, text_align=ft.TextAlign.LEFT, size=35, style=ft.TextStyle(weight=ft.FontWeight.BOLD)), padding=10), bgcolor=ft.Colors.WHITE, margin=0),
            ft.Card(ft.Container(ft.Column([
                ft.Text(value=f"ID String: {self.settings['ID']}", color=self.main_color, text_align=ft.TextAlign.LEFT, size=16, style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
                ft.Text(value=f"Serial number: {self.settings['SN']}", color=self.main_color, text_align=ft.TextAlign.LEFT, size=16, style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
                ft.Text(value=f"Software version: {__version__}", color=self.main_color, text_align=ft.TextAlign.LEFT, size=16, style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
                ft.Text(value=f"Hardware revision: {self.settings['HW_revision']}", color=self.main_color, text_align=ft.TextAlign.LEFT, size=16, style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
                ft.Text(value=f"Hardware platform: {hardware.get_cpu_model()}", color=self.main_color, text_align=ft.TextAlign.LEFT, size=16, style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
                ft.Text(value=f"Hardware serial: {hardware.get_cpu_serial()}", color=self.main_color, text_align=ft.TextAlign.LEFT, size=16, style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
                ft.Text(value=f"Python: {platform.python_version()}", color=self.main_color, text_align=ft.TextAlign.LEFT, size=16, style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
                ft.Text(value=f"OS: {platform.platform()}", color=self.main_color, text_align=ft.TextAlign.LEFT, size=16, style=ft.TextStyle(weight=ft.FontWeight.BOLD)),                                 
                ft.Text(value=f"Compartments: {self.settings['SMALL_COMPARTMENTS']} small, {self.settings['LARGE_COMPARTMENTS']} large.", color=self.main_color, text_align=ft.TextAlign.LEFT, 
                                size=16, style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
                self.open_comps_text,
                self.network_text,
                self.temp_text,
                self.memory_text,
                self.uptime_text,
                self.brightness_text,
                self.power_text,
                self.battery_text,
                self.error_text,
                ],scroll=ft.ScrollMode.ALWAYS, spacing=2),
            padding=10), bgcolor=ft.Colors.WHITE, margin=0, expand=True),
        ],
        spacing=20, expand=True
                    )
        # booking page
        self.booking = ft.Column(
            controls=[
                ft.Card(content=ft.Container(content=ft.Text(value=self.text["booking_title"], color=self.main_color, text_align=ft.TextAlign.LEFT, size=35, style=ft.TextStyle(weight=ft.FontWeight.BOLD)), padding=10), bgcolor=ft.Colors.WHITE, margin=0),
                ft.Card(content=ft.Container(content=ft.Text(value=self.text["booking_text"], color=self.main_color, text_align=ft.TextAlign.LEFT, size=24, style=ft.TextStyle(weight=ft.FontWeight.BOLD)), padding=15, margin=0, expand=True), bgcolor=ft.Colors.WHITE, margin=0),
                ft.Card(ft.Container(ft.Image(src="/images/qrcode.png", width=450, height=430, fit=ft.BoxFit.CONTAIN,), padding=15), bgcolor=ft.Colors.WHITE, margin=0, expand=1),
            ],
            spacing=20
        )
        # borrowing page
        self.code  = ""  
        self.code_display = ft.Text(value=self.code, size=178, color=self.main_color, width=460, max_lines=1, font_family="Fira Mono", style=ft.TextStyle(height=0.9))
        self.borrowing = ft.Column(
            controls=[
                ft.Card(content=ft.Container(content=ft.Text(value=self.text["borrowing_title"], color=self.main_color, text_align=ft.TextAlign.LEFT, size=35, style=ft.TextStyle(weight=ft.FontWeight.BOLD)), padding=10), bgcolor=ft.Colors.WHITE, margin=0),
                ft.Card(ft.Container(ft.Text(value=self.text["borrowing_text"], size=24, color=self.main_color, style=ft.TextStyle(weight=ft.FontWeight.BOLD)), padding=10), bgcolor=ft.Colors.WHITE),
                ft.Card(ft.Container(self.code_display, padding=10), bgcolor=ft.Colors.WHITE), 
                NumberPad(self, self.borrowing_callback)
            ],
            #spacing=20
        )
        # returning page
        self.tag=ft.Image(src="/images/tag.png", width=100, height=70, fit=ft.BoxFit.CONTAIN, left=50, top=170, animate_position=ft.Animation(duration=2000, curve="ease"))
        self.returning = ft.Column(
            controls=[
                ft.Card(content=ft.Container(content=ft.Text(value=self.text["returning_title"], color=self.main_color, text_align=ft.TextAlign.LEFT, size=35, style=ft.TextStyle(weight=ft.FontWeight.BOLD)), padding=10), bgcolor=ft.Colors.WHITE, margin=0),
                ft.Card(content=ft.Row([
                    ft.Container(content=ft.Text(value=self.text["returning_text"], color=self.main_color, text_align=ft.TextAlign.LEFT, size=24, style=ft.TextStyle(weight=ft.FontWeight.BOLD)), padding=10, margin=10, expand=True), 
                    ft.Icon(ft.Icons.ARROW_FORWARD, color=self.main_color, size=100)]), bgcolor=ft.Colors.WHITE, margin=0),
                ft.Stack([
                    ft.Card(ft.Container(ft.Image(src="/images/nfc.png", width=430, height=390, fit=ft.BoxFit.CONTAIN,), padding=15), bgcolor=ft.Colors.WHITE, margin=0),
                    self.tag
                ]),
            ],
            spacing=20
        )
        # app / info bar
        self.info_bar_row = ft.Row(controls=[ft.Text(value=self.text["status"], size=24)], alignment=ft.MainAxisAlignment.CENTER)
        self.info_bar = ft.Container(content=self.info_bar_row)
        self.titletext = ft.Text("ZE Schlüsselkasten", size=24, color=ft.Colors.WHITE)
        self.language_fab = ft.FloatingActionButton(
            content=ft.Icon(ft.Icons.LANGUAGE, size=45, color=ft.Colors.WHITE),
            on_click=self.btn_dec(lambda _: self.change_language()),
            bgcolor=self.main_color,
            foreground_color=ft.Colors.WHITE,
            width=100,
            height=100,
            shape=ft.RoundedRectangleBorder(radius=30),
        )
        self.page.appbar = ft.AppBar(
            leading_width=60,
            toolbar_height=65,
            leading=ft.IconButton(on_click=self.btn_dec(lambda _: self.page_reconfigure(self.welcome)), icon=ft.Icons.ARROW_BACK, icon_color=ft.Colors.WHITE, icon_size=50),
            title=self.titletext,
            center_title=True,
            actions=[
                ft.IconButton(on_click=self.btn_dec(lambda _: self.page_reconfigure(self.help)), on_long_press=self.btn_dec(lambda _: self.page_reconfigure(self.info)), icon=ft.Icons.HELP_OUTLINE, icon_color=ft.Colors.WHITE, icon_size=45),
            ],
            bgcolor=self.main_color,   
        )     
        # initially load the welcome page  
        self.page.add(self.welcome)        
        self.page.floating_action_button = self.language_fab
        self.page.update()
        
    def run_animation(self):
        #self.tag.animate_position=ft.Animation(duration=2000, curve="ease")
        self.tag.left = 50
        self.page.update()
        time.sleep(0.5)
        self.tag.left = 250
        self.page.update()
        
    # switch between welcome (initial), booking, borrowing, returning and service pages
    def page_reconfigure(self, destination):
        if len(self.page.controls) > 0:
           self.page.remove_at(0)
        self.page.add(destination)
        # show the language button only on the welcome page
        self.page.floating_action_button = self.language_fab if destination == self.welcome else None
        # reset entries
        self.code = ""
        self.code_display.value = self.code
        self.compartment = ""
        # run update
        self.page.update()
        if destination == self.returning:
            self.run_animation()
        
    def borrowing_callback(self, data):
        if data == "x":
            if self.code == "":
                self.page_reconfigure(self.welcome)
            else:
                self.code = ""
        elif data == "ok":
            code = self.code # local copy to allow logging after variable is cleared
            comp, status = self.flink.check_code(code)
            if status == "valid":
                self.open_compartment(comp, "borrow")
                logger.info(f"Code '{code}' was entered, valid for compartment {comp}, content status: {hardware.compartments[comp].content_status}, door status: {hardware.compartments[comp].door_status}.")
            else:
                if status=="invalid":
                    title = self.text["code_invalid_title"]
                    announcement = self.text["code_invalid_announcement"]
                else:
                    title = self.text["code_error_title"]
                    announcement = self.text["code_error_announcement"]
                dlg = ft.AlertDialog(
                    modal=True,
                    title=ft.Text(title),
                    content=ft.Text(announcement, style=ft.TextStyle(size=24)),
                    on_dismiss=None,
                    #barrier_color="#66660000"
                    )
                self.page.show_dialog(dlg)
                self.beep_warning()
                time.sleep(3)
                self.page.pop_dialog()
                logger.info(f"Code '{code}' was entered, but the code check returned: {status}.")
                #self.page_reconfigure(self.welcome)
            self.code = ""
        else:
            self.code = self.code + data

        self.code_display.value = self.code
        self.page.update()
        
    def service_callback(self, data):
        if data == "x":
            if self.compartment == "":
                self.page_reconfigure(self.welcome)
            else:
                self.compartment = ""
        elif data == "ok":
            if not self.compartment:
                return
            comp = self.compartment # local copy to allow logging after variable is cleared
            if self.service_mode.value == "open":
                success = self.open_compartment(comp, "service")
                if success:
                    logger.info(f"Compartment {comp} was opened from service mode, content status: {hardware.compartments[comp].content_status}, door status: {hardware.compartments[comp].door_status}.")
            elif self.service_mode.value == "program": 
                # nfc_personalize, write dict, save to toml
                if self.compartment == "0000":
                    self.compartment = "service"
                dlg_modal = ft.AlertDialog(
                    modal=True,
                    title=ft.Text(self.text["nfc_program_title"]),
                    content=ft.Text(self.text["nfc_program_text"].format(comp=comp), style=ft.TextStyle(size=24)),
                    actions=[ft.TextButton(self.text["cancel"], on_click=lambda e: self.page.pop_dialog(), style=ft.ButtonStyle(text_style=ft.TextStyle(size=24, weight=ft.FontWeight.BOLD)))],
                    on_dismiss=None)
                self.page.show_dialog(dlg_modal)
                if self.compartment in self.settings["NFC-tags"]:
                    if self.nfc is not None:
                        uid = None
                        retries = 0
                        while uid is None and retries < 10 and dlg_modal.open: 
                            uid = self.nfc.personalize() # 1 s timeout
                            retries += 1
                    if uid is not None:
                        self.settings["NFC-tags"][comp].append(uid)
                        dlg_modal.content=ft.Text(self.text["nfc_assigning"].format(comp=comp), style=ft.TextStyle(size=24))
                        self.toml.write(self.settings)
                        logger.info(f"NFC tag with UID {uid} assigned to compartment {comp}.")
                        self.beep_success()
                    elif dlg_modal.open: # user already closed dialog / canceled
                        dlg_modal.content=ft.Text(self.text["nfc_not_found"], style=ft.TextStyle(size=24))
                        logger.warning("Tag assignment failed, no NFC tag found.")
                else:
                    dlg_modal.content=ft.Text(self.text["nfc_invalid_comp"].format(comp=comp), style=ft.TextStyle(size=24))
                    logger.info(f"Compartment {comp} is not valid, NFC-tag not saved.")
                dlg_modal.update()
                time.sleep(2)
                self.page.pop_dialog()
            elif self.service_mode.value == "reset":
                # write dict, save to toml
                dlg_modal = ft.AlertDialog(
                    modal=True,
                    title=ft.Text(self.text["reset_title"]),
                    content=ft.Text(self.text["reset_text"].format(comp=self.compartment), style=ft.TextStyle(size=24)),
                    on_dismiss=None)
                self.page.show_dialog(dlg_modal)
                self.settings["NFC-tags"][self.compartment] = []
                self.toml.write(self.settings)
                logger.info(f"NFC assignment reset for compartment {self.compartment}.")
                self.beep_success()
                time.sleep(2)
                self.page.pop_dialog()
            self.compartment = ""            
        else:
            self.compartment = self.compartment + data
            
    def open_compartment(self, compartment, reason):
        if compartment not in hardware.compartments:
            dlg = ft.AlertDialog(
                modal=False,
                title=ft.Text(self.text["invalid_compartment_title"]),
                content=ft.Text(self.text["invalid_compartment_text"].format(compartment=compartment),  style=ft.TextStyle(size=24)),
                on_dismiss=None)
            self.page.show_dialog(dlg)
            self.beep_warning()
            time.sleep(3)
            self.page.pop_dialog()
            return False
        dlg = ft.AlertDialog(
            modal=False,
            title=ft.Text(self.text["open_compartment_title"]),
            content=ft.Text(self.text["open_compartment_text"].format(compartment=compartment),  style=ft.TextStyle(size=24)),
            on_dismiss=None)
        self.page.show_dialog(dlg)
        hardware.compartments[compartment].set_LEDs("white")
        self.beep_success()
        success = hardware.compartments[compartment].open()
        time.sleep(1)
        if success:
           announcement = self.text["compartment_opened_announcement"].format(compartment=compartment)
           if reason == "borrow":
               question = self.text["compartment_opened_question_borrow"]
               destination_yes = self.welcome
               destination_no = self.borrowing
           elif reason == "return":
               question = self.text["compartment_opened_question_return"]
               destination_yes = self.welcome
               destination_no = self.returning
           elif reason == "service":
               question = self.text["compartment_opened_question_service"]
               destination_yes = self.service
               destination_no = self.welcome
        else:
           announcement = self.text["compartment_not_opened"].format(compartment=compartment)
           question = self.text["try_again"]
           if reason == "borrow":
               destination_yes = self.borrowing
               destination_no = self.welcome
           elif reason == "return":
               destination_yes = self.returning
               destination_no = self.welcome
           elif reason == "service":
               destination_yes = self.service
               destination_no = self.welcome
        dlg_modal = ft.AlertDialog(
                    modal=True,
                    title=ft.Text(self.text["compartment_opened_title"]),
                    content=ft.Text(f"{announcement} {question}",  style=ft.TextStyle(size=24)),
                    actions=[ft.TextButton(self.text["no"], on_click=lambda e: self.answer_no(dlg_modal, destination_no, reason, compartment), style=ft.ButtonStyle(text_style=ft.TextStyle(size=24, weight=ft.FontWeight.BOLD))), 
                             ft.TextButton(self.text["yes"], on_click=lambda e: self.answer_yes(dlg_modal, destination_yes, reason, compartment), style=ft.ButtonStyle(text_style=ft.TextStyle(size=24, weight=ft.FontWeight.BOLD)))],
                    on_dismiss=None)
        # close the "opening compartment" dialog before showing the result modal
        self.page.pop_dialog()
        self.page.show_dialog(dlg_modal)
        # close dialog if no user reaction
        close_time = time.time() + 20
        was_closed = False
        while time.time() < close_time and dlg_modal.open:
            if not hardware.compartments[compartment].is_open() and not was_closed:
                self.beep_success()
                was_closed = True
            time.sleep(0.1)
        repetitions = 0
        while hardware.compartments[compartment].is_open() and repetitions < 3:
            # blink red LEDs
            hardware.compartments[compartment].set_LEDs((255,0,0))
            self.beep_warning()
            hardware.compartments[compartment].set_LEDs("off")
            time.sleep(1)
            repetitions += 1      
        if hardware.compartments[compartment].is_open():
            logger.warning(f"Compartment {compartment} was not closed by user.")
        if dlg_modal.open:
            self.answer_yes(dlg_modal, self.welcome, reason, compartment)
        hardware.compartments[compartment].set_LEDs("off")
        return True

    def answer_no(self, dlg_modal, destination, reason, compartment):
        self.close_modal(dlg_modal, destination)
        if reason == "borrow": # not taken
            hardware.compartments[compartment].content_status = "present"
        elif reason == "return": # not returned
            hardware.compartments[compartment].content_status = "empty"

    def answer_yes(self, dlg_modal, destination, reason, compartment):
        self.close_modal(dlg_modal, destination)
        if reason == "borrow": # taken
            hardware.compartments[compartment].content_status = "empty"
        elif reason == "return": # returned
            hardware.compartments[compartment].content_status = "present"

    def close_modal(self, dialog, destination):
        self.page.pop_dialog()
        self.page_reconfigure(destination)
        
    def open_all_clicked(self, e):
        logger.info("All compartments opened from service mode.")
        hardware.open_all()
        
    def mounting_clicked(self, e):
        logger.info("Mounting compartments opened from service mode.")
        hardware.open_mounting()
        
    def reconfigure_appbar(self):
        with self.errors_lock:
            has_errors = len(self.errors) > 0
            flink_err   = "flink"       in self.errors
            ping_err    = "ping"        in self.errors
            power_err   = "power"       in self.errors
            battery_err = "battery"     in self.errors
            misc_err    = bool({i for i in {"NFC", "compartments", "lux", "MQTT", "rpi"} if i in self.errors})
        if has_errors and self.page.appbar.title == self.titletext:
            self.page.appbar.title = self.info_bar
            self.info_bar_row.controls = self.info_bar_row.controls[0:1]
            if flink_err:
                self.info_bar_row.controls.append(ft.Icon(ft.Icons.CLOUD_OFF))
            if ping_err:
                self.info_bar_row.controls.append(ft.Icon(ft.Icons.WIFI_OFF))
            if power_err:
                self.info_bar_row.controls.append(ft.Icon(ft.Icons.POWER_OFF))
            if battery_err:
                self.info_bar_row.controls.append(ft.Icon(ft.Icons.BATTERY_0_BAR))
            if misc_err:
                self.info_bar_row.controls.append(ft.Icon(ft.Icons.ENGINEERING))
        else:
            self.page.appbar.title = self.titletext
        self.page.update()
        
    def update_info(self):
        self.open_comps_text.value = f"Open compartments: {hardware.check_all()}"
        self.network_text.value = f"Network: {hardware.get_ESSID()}, Signal: {hardware.get_RSSI()}"
        self.temp_text.value = f"CPU temperature: {hardware.get_temp()} °C"
        self.memory_text.value = f"Memory available: {hardware.get_memory_info()}"
        self.uptime_text.value = f"Uptime: {hardware.uptime()}"
        with self.errors_lock:
            self.error_text.value = f"Errors: {dict(self.errors)}"
        # Add new lines for backlight and brightness
        if hardware.light_sensor is not None:
            self.brightness_text.value = f"Ambient brightness: {hardware.light_sensor.lux:.2f} lux, Display brightness: {hardware.backlight._duty_cycle}%"
        else:
            self.brightness_text.value = f"Ambient brightness: N/A, Display brightness: {hardware.backlight._duty_cycle}%"
        if hardware.battery_monitor is not None:
            self.battery_text.value = f"Input: {hardware.battery_monitor.VBUS:.0f} mV, {hardware.battery_monitor.IBUS:.0f} mA"
            self.power_text.value = f"Battery: {hardware.battery_monitor.VBAT:.0f} mV, {hardware.battery_monitor.IBAT:.0f} mA"

    def change_language(self):
        # Get list of available languages
        available_langs = list(self.localization.keys())        
        # Find current language index
        try:
            current_index = available_langs.index(self.language)
            # Get next language, wrapping around to start if at end
            next_index = (current_index + 1) % len(available_langs)
            self.language = available_langs[next_index]
        except ValueError:
            # If current language not found, reset to first available
            self.language = self.settings["UI_language"]
            
        self.text = self.localization[self.language]
        self.build_ui()

    def reset_inactivity_timer(self):
        if hasattr(self, 'inactivity_timer') and self.inactivity_timer:
            self.inactivity_timer.cancel()
        self.inactivity_timer = threading.Timer(60, self.return_to_welcome)
        self.inactivity_timer.daemon = True
        self.inactivity_timer.start()

    def return_to_welcome(self):
        # Only return if not already on welcome page
        if not (len(self.page.controls) == 1 and self.page.controls[0] == self.welcome):
            self.page_reconfigure(self.welcome)
        # back to default language
        if self.language != self.settings["UI_language"]:
            self.language = self.settings["UI_language"]
            self.text = self.localization[self.language]
            self.build_ui()
        
    def beep_success(self):
        if self.settings["UI_sound"]:
            hardware.beep(duration=0.06, frequency=4000)
            time.sleep(0.04)
            hardware.beep(duration=0.06, frequency=4000)

    def beep_warning(self):
        if self.settings["UI_sound"]:
            hardware.beep(duration=0.75, frequency=2000)
        
    def btn_dec(self, func):
        def wrapper(*args, **kwargs):
            self.reset_inactivity_timer()
            try:
                if hardware.haptic is not None and self.settings["UI_haptic"]:
                    hardware.trigger_haptic()
            except Exception:
                pass
            # Run the handler off the event loop. Flet 0.85 executes sync event
            # handlers directly on the asyncio loop, so blocking work (time.sleep,
            # hardware access) would stall UI updates and dialogs would only appear
            # after the handler returns. run_thread keeps the loop free so queued
            # updates (e.g. show_dialog) are transmitted immediately.
            self.page.run_thread(func, *args, **kwargs)
        return wrapper

    def toggle_sound(self, e):
        self.settings["UI_sound"] = e.control.value
        self.toml.write(self.settings)
        self.page.update()

    def toggle_haptic(self, e):
        self.settings["UI_haptic"] = e.control.value
        self.toml.write(self.settings)
        self.page.update()

    def toggle_charging(self, e):
        self.settings["charging"] = e.control.value
        if hardware.battery_monitor is not None:
            hardware.battery_monitor.enable_charging(e.control.value)
        self.toml.write(self.settings)
        self.page.update()

    def brightness_slider_changed(self, e):
        adjustment = e.control.value
        self.settings["brightness_adjustment"] = adjustment
        if hardware.light_sensor is not None:
            hardware.backlight.change_duty_cycle(self.settings["brightness_adjustment"]*100*hardware.light_sensor.lux/(self.settings["max_brightness"]))
        else:
            hardware.backlight.change_duty_cycle(self.settings["brightness_adjustment"]*80)
        self.toml.write(self.settings)




