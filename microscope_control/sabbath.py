import kivy
from .main import Setup
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from functools import wraps, partial
import time
from microscope_control.Constants import *

def text_popup(title, hint, get_current, validate, on_success, size_hint=(0.5, 0.5)):
    """
    Decorator to replace a manage_* method with a text-input popup.
    - title: popup window title
    - hint: placeholder text
    - get_current: fn(self) -> str for current value label
    - validate: fn(str) -> typed value or raise
    - on_success: fn(self, value) -> side-effects setting value
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            self._show_input_popup(
                title=title,
                current_text=get_current(self),
                hint=hint,
                validate=validate,
                on_success=lambda v: on_success(self, v),
                size_hint=size_hint
            )
        return wrapper
    return decorator

def choice_popup(title, get_current, choices, on_success, size_hint=(0.6, 0.6)):
    """
    Decorator to replace a manage_* or choose_* method with a choice-button popup.
    - title: popup window title
    - get_current: fn(self) -> str for current value label
    - choices: list of (button_text, value)
    - on_success: fn(self, value) -> side-effects
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            self._show_choice_popup(
                title=title,
                current_text=get_current(self),
                choices=choices,
                on_success=lambda v: on_success(self, v),
                size_hint=size_hint
            )
        return wrapper
    return decorator

def combo_popup(title, get_current, hint, validate, choices, on_success, size_hint=(0.8,0.8)):
    def deco(fn):
        @wraps(fn)
        def wrapped(self, *args, **kwargs):
            self._show_combo_popup(
                title=title,
                current_text=get_current(self),
                hint=hint,
                validate=validate,
                choices=choices,
                on_success=lambda v: on_success(self, v),
                size_hint=size_hint
            )
        return wrapped
    return deco

class Sabbath(App):
    def build(self):
        self.setup = Setup()
        self.setup.init_settings()
        self.setup.open_all_devices()
        self.root_layout = FloatLayout()
        self.status_layout = GridLayout(cols=2, padding=10, spacing=10,
                                        size_hint=(None, None),
                                        size=(600, 100),              # Adjust size of grid manually
                                        pos_hint={"center_x": 0.5, "top": 0.9})
        self.init_status_labels()
        
        # Grid layout for buttons
        self.button_layout = GridLayout(cols=2, padding=10, spacing=10,
                                        size_hint=(None, None),
                                        size=(400, 300),              # Adjust size of grid manually
                                        pos_hint={"center_x": 0.5, "center_y": 0.5})
        
        self.root_layout.add_widget(self.status_layout)

        # Add Buttons for each functionality
        self.add_button('Take Spectra', self.manage_spectra)
        self.add_button('Time Trajectories', self.setup.time_evolution)
        self.add_button('Take Image', self.setup.take_images)
        self.add_button('Power ramp', self.setup.power_ramp)
        self.add_button('Live Camera', self.setup.live_cam)
        self.add_button('Set ROI', self.setup.select_ROI)
        self.add_button('Set Filter', self.choose_filter)
        self.add_button('Set Exposure', self.manage_exposure)
        self.add_button('Move Z Position', self.manage_zpos)
        self.add_button('Refresh Power reading', self.print_power_label)
        self.add_button('Toggle Shutter', self.manage_toggle_shutter)
        self.add_button('Settings', self.show_settings_menu)
        
        self.root_layout.add_widget(self.button_layout)
        return self.root_layout

        
    def add_button(self, text, func):
        button = Button(text=text, size_hint=(None, None), width=200, height=50)
        button.bind(on_press=lambda instance: func())
        self.button_layout.add_widget(button)

    def init_status_labels(self):
        # Shutter label
        self.label_shutter_status = Label(text=f"Shutter: Closed", font_size=18, size_hint=(1, 0.1))
        self.status_layout.add_widget(self.label_shutter_status)

        # Z position label
        zpos = self.setup.read_zpos()
        self.label_status_z = Label(text=f"Z Position: {zpos}", font_size=18, size_hint=(1, 0.1))
        self.status_layout.add_widget(self.label_status_z)
        
        # Power label
        power = self.setup.print_power()
        self.power_label = Label(text=f"P: {power * 1e6:.2f} μW", font_size=18)
        self.status_layout.add_widget(self.power_label)

        # Exposure label
        exposure = self.setup.texp  
        self.label_exposure_status = Label(text=f"Exposure: {exposure:.2f} s", font_size=18)
        self.status_layout.add_widget(self.label_exposure_status)

        # Filter status label
        filter_id = self.setup.filter_id
        self.label_filter_status = Label(text=f"Filter: {filter_id}", font_size=18)
        self.status_layout.add_widget(self.label_filter_status)

        # Sample name label
        try:
            sample_name = self.setup.settings.get('SAMPLE_NAME', 'value')
        except KeyError:
            sample_name = 'Unknown'
        self.label_sample_status = Label(text=f"Sample: {sample_name}", font_size=18)
        self.status_layout.add_widget(self.label_sample_status)

    def print_power_label(self, *_):
        power = self.setup.print_power()
        if hasattr(self, 'power_label'):
            self.power_label.text = f"P: {power * 1e6:.2f} μW"
        else:
            self.status_layout.add_widget(self.power_label)

    # Helper to show a text-input popup
    def _show_input_popup(self, *, title, current_text, hint, validate, on_success, size_hint):
        layout = GridLayout(cols=1, padding=10, spacing=10)
        layout.add_widget(Label(text=current_text))
        ti = TextInput(hint_text=hint, multiline=False)
        btn = Button(text="Set")
        popup = Popup(title=title, content=layout, size_hint=size_hint)

        def _do_set(*_):
            try:
                val = validate(ti.text)
                on_success(val)
                popup.dismiss()
            except Exception:
                ti.text = "❌ invalid"

        ti.bind(on_text_validate=_do_set)
        btn.bind(on_press=_do_set)
        layout.add_widget(ti)
        layout.add_widget(btn)
        popup.open()

    # Helper to show a choice-button popup
    def _show_choice_popup(self, *, title, current_text, choices, on_success, size_hint):
        layout = GridLayout(cols=2, padding=10, spacing=10)
        layout.add_widget(Label(text=current_text))
        layout.add_widget(Widget(size_hint_y=None, height=0))
        popup = Popup(title=title, content=layout, size_hint=size_hint)

        for label, val in choices:
            btn = Button(text=label, size_hint_y=None, height=40)
            btn.bind(on_press=lambda *_ ,v=val: (on_success(v), popup.dismiss()))
            layout.add_widget(btn)

        popup.open()

    def _show_combo_popup(self, *, title, current_text, hint,
                        validate, choices, on_success, size_hint):
        layout = GridLayout(cols=1, padding=10, spacing=10)
        layout.add_widget(Label(text=current_text))

        # 1) Grid of choice-buttons
        grid = GridLayout(cols= 3, spacing=5, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        for label, val in choices:
            btn = Button(text=label, size_hint_y=None, height=40)
            btn.bind(on_press=lambda *_ ,v=val: (on_success(v), popup.dismiss()))
            grid.add_widget(btn)
        layout.add_widget(grid)

        # 2) Text input + Set button
        ti = TextInput(hint_text=hint, multiline=False)
        btn = Button(text="Set")
        def _do_set(*_):
            try:
                v = validate(ti.text)
                on_success(v)
                popup.dismiss()
            except:
                ti.text = "❌ invalid"
        ti.bind(on_text_validate=_do_set)
        btn.bind(on_press=_do_set)
        layout.add_widget(ti)
        layout.add_widget(btn)

        popup = Popup(title=title, content=layout, size_hint=size_hint)
        popup.open()


    @text_popup(
        title="Set Z Position (0 - 22 mm)",
        hint="New Z (mm)",
        get_current=lambda self: f"Current Z: {self.setup.read_zpos():.3f} mm",
        validate=float,
        on_success=lambda self, v: (self.setup.move_zpos(v), setattr(self.label_status_z, 'text', f"Z Position: {v:.3f}"))
    )
    def manage_zpos(self, *_):
        pass

    @text_popup(
        title="Set Exposure Time (0.1 - 7 s)",
        hint="New exposure (s)",
        get_current=lambda self: f"Current Exposure: {self.setup.texp:.3f} s",
        validate=float,
        on_success=lambda self, v: (self.setup.set_exposure(v), setattr(self.label_exposure_status, 'text', f"Exposure: {v:.2f} s"))
    )
    def manage_exposure(self, *_):
        pass

    @choice_popup(
        title=f"Select Filter (1 - 12)",
        get_current= lambda self: f"Current Filter: {self.setup.filter_id}",
        choices=[(str(k) + ' - ' + v.split('_')[0].replace('Center-', ''), k)
                  for k, v in FILTERS.items()],
        on_success=lambda self, v: (self.setup.move_filter(v), setattr(self.label_filter_status, 'text', f"Filter: {v} - {FILTERS[v]}"))
    )
    def choose_filter(self, *_):
        pass

    @combo_popup(
        title="Choose or Enter Sample",
        get_current=lambda self: f"Current: {self.setup.settings.get('SAMPLE_NAME','')}",
        hint="Or type new sample name…",
        validate=lambda s: s if s else (_ for _ in ()).throw(ValueError()),
        choices=[(str(k) + ' - ' + SAMPLES[k], SAMPLES[k]) for k in SAMPLES if k != 'q'],
        on_success=lambda self, v: (
            setattr(self.label_sample_status,'text', f"Sample: {v}"),
            self.setup.settings.__setitem__('SAMPLE_NAME', v)
        )
    )
    def manage_spectra(self, *_):
        pass

    def show_settings_menu(self, *_):
        settings_df = self.setup.settings

        grid = GridLayout(cols=2, spacing=10, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        # Define callback to open the objective selector popup
        def choose_objective(instance):
            def set_objective(value):
                # Update the DataFrame
                idx = settings_df[settings_df['setting'] == 'MICROSCOPE_OBJECTIVE'].index[0]
                settings_df.at[idx, 'value'] = value
                print(f"Objective set to: {value}")
                self.setup.settings = settings_df  # Update the settings in Setup
                select_popup.dismiss()
                main_popup.dismiss()
                self.show_settings_menu()  # Reopen settings to show updated value

            selector_layout = GridLayout(cols=1, padding=10, spacing=10)
            btn_1 = Button(text='Mitutoyo_50x_NA_0.5', on_press=lambda _: set_objective('Mitutoyo_50x_NA_0.5'))
            btn_2 = Button(text='Nikon_60x_NA_0.95', on_press=lambda _: set_objective('Nikon_60x_NA_0.95'))
            selector_layout.add_widget(btn_1)
            selector_layout.add_widget(btn_2)

            select_popup = Popup(title='Select Microscope Objective', content=selector_layout, size_hint=(0.5, 0.3))
            select_popup.open()

        for index, row in settings_df.iterrows():
            grid.add_widget(Label(text=str(row['setting']), size_hint_y=None, height=30))

            if row['setting'] == 'MICROSCOPE_OBJECTIVE':
                btn = Button(text=str(row['value']), size_hint_y=None, height=30)
                btn.bind(on_press=choose_objective)
                grid.add_widget(btn)
            else:
                grid.add_widget(Label(text=str(row['value']), size_hint_y=None, height=30))

        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(grid)

        popup_layout = GridLayout(cols=1, padding=10)
        popup_layout.add_widget(scroll)

        main_popup = Popup(title='Settings', content=popup_layout, size_hint=(0.7, 0.7))
        main_popup.open()

    def manage_toggle_shutter(self, *_):
        shutter_state = self.setup.shutter_status
        if shutter_state:
            print("Shutter is currently open. Closing it...")
            self.setup.toggle_shutter()
        else:
            print("Shutter is currently closed. Opening it...")
            self.setup.toggle_shutter()
        shutter_state = self.setup.shutter_status

        self.label_shutter_status.text = f"Shutter: {'Open' if shutter_state else 'Closed'}"
        self.print_power_label()

if __name__ == '__main__':
    Sabbath().run()
