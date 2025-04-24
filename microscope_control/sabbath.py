from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup

from functools import partial, wraps
from microscope_control.Constants import FILTERS, SAMPLES
from .main import Setup  # your actual Setup class

### ========== Popup Helpers ==========

class PopupMixin:
    def _show_input_popup(self, *, title, current_text, hint, validate, on_success, size_hint=(0.5, 0.5)):
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

    def _show_choice_popup(self, *, title, current_text, choices, on_success, size_hint=(0.6, 0.6)):
        layout = GridLayout(cols=2, spacing=10, padding=10)
        layout.add_widget(Label(text=current_text, size_hint_y=None, height=40))
        layout.add_widget(Widget(size_hint_y=None, height=0))

        popup = Popup(title=title, content=layout, size_hint=size_hint)

        for label, val in choices:
            btn = Button(text=label, size_hint_y=None, height=40)
            btn.bind(on_press=lambda *_ ,v=val: (on_success(v), popup.dismiss()))
            layout.add_widget(btn)

        popup.open()

    def _show_combo_popup(self, *, title, current_text, hint, validate, choices, on_success, size_hint=(0.8, 0.8)):
        layout = GridLayout(cols=1, padding=10, spacing=10)
        layout.add_widget(Label(text=current_text))
        popup = Popup(title=title, content=layout, size_hint=size_hint)

        grid = GridLayout(cols=3, spacing=5, size_hint_y=None)
        for label, val in choices:
            btn = Button(text=label, size_hint_y=None, height=40)
            btn.bind(on_press=lambda *_ ,v=val: (on_success(v), popup.dismiss()))
            grid.add_widget(btn)
        layout.add_widget(grid)

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
        popup.open()

### ========== Decorators ==========

def text_popup(title, hint, get_current, validate, on_success):
    def deco(fn):
        @wraps(fn)
        def wrapped(self, *args, **kwargs):
            self._show_input_popup(
                title=title,
                current_text=get_current(self),
                hint=hint,
                validate=validate,
                on_success=lambda v: on_success(self, v)
            )
        return wrapped
    return deco

def choice_popup(title, get_current, choices, on_success):
    def deco(fn):
        @wraps(fn)
        def wrapped(self, *args, **kwargs):
            self._show_choice_popup(
                title=title,
                current_text=get_current(self),
                choices=choices,
                on_success=lambda v: on_success(self, v)
            )
        return wrapped
    return deco

def combo_popup(title, get_current, hint, validate, choices, on_success):
    def deco(fn):
        @wraps(fn)
        def wrapped(self, *args, **kwargs):
            self._show_combo_popup(
                title=title,
                current_text=get_current(self),
                hint=hint,
                validate=validate,
                choices=choices,
                on_success=lambda v: on_success(self, v)
            )
        return wrapped
    return deco

### ========== Screen ==========

class MainScreen(Screen, PopupMixin):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setup = Setup()
        self.setup.init_settings()
        self.setup.open_all_devices()
        self.layout = FloatLayout()
        self.status_layout = GridLayout(cols=2, padding=10, spacing=10,
                                size_hint=(None, None),
                                size=(600, 200),              # Adjust size of grid manually
                                pos_hint={"center_x": 0.5, "top": 0.9})
        
        self.button_layout = GridLayout(cols=2, padding=10, spacing=10,
                                        size_hint=(None, None),
                                        size=(400, 300),              # Adjust size of grid manually
                                        pos_hint={"center_x": 0.5, "center_y": 0.5})
        self._init_labels()
        self._init_buttons()
        self.layout.add_widget(self.status_layout)
        self.layout.add_widget(self.button_layout)
        self.add_widget(self.layout)

    def _init_labels(self):
        zpos = self.setup.read_zpos()
        power = self.setup.get_power()
        self.label_shutter_status = Label(text=f"Shutter: Closed", font_size=18, size_hint=(1, 0.2))
        self.label_status_z = Label(text=f"Z Position: {zpos}", font_size=18, size_hint=(1, 0.2))
        self.label_exposure_status = Label(text="Exposure: 0.5 s", font_size=18, size_hint=(1, 0.2))
        self.label_filter_status = Label(text="Filter: 1 - NA", font_size=18, size_hint=(1, 0.2))
        self.label_sample_status = Label(text="Sample: ?")
        self.label_power = Label(text=f"Power: {power * 1e6:.2f} μW", font_size=18, size_hint=(1, 0.2))
        
        self.status_layout.add_widget(self.label_shutter_status)
        self.status_layout.add_widget(self.label_status_z)
        self.status_layout.add_widget(self.label_exposure_status)
        self.status_layout.add_widget(self.label_filter_status)
        self.status_layout.add_widget(self.label_sample_status)
        self.status_layout.add_widget(self.label_power)
        self.status_layout.add_widget(Label(text=""))  # Empty space for layout balance

    def _init_buttons(self):
        self._add_button('Take Spectra', self.manage_spectra)
        self._add_button('Time Trajectories', self.setup.time_evolution)
        self._add_button('Take Image', self.setup.take_images)
        self._add_button('Power ramp', self.setup.power_ramp)
        self._add_button('Live Camera', self.setup.live_cam)
        self._add_button('Set ROI', self.setup.select_ROI)
        self._add_button('Set Filter', self.choose_filter)
        self._add_button('Set Exposure', self.manage_exposure)
        self._add_button('Move Z Position', self.manage_zpos)
        self._add_button('Refresh Power reading', self.print_power_label)
        self._add_button('Toggle Shutter', self.manage_toggle_shutter)
        self._add_button('Settings', self.show_settings_menu)

    def _add_button(self, text, func):
        btn = Button(text=text, size_hint=(None, None), size=(200, 50))
        btn.bind(on_press=lambda *_: func())
        self.button_layout.add_widget(btn)

    @text_popup(
        title="Set Z Position",
        hint="Z in mm",
        get_current=lambda self: f"Current Z: {self.setup.read_zpos():.3f}",
        validate=float,
        on_success=lambda self, z: (
            self.setup.move_zpos(z),
            setattr(self.label_status_z, 'text', f"Z Position: {z:.3f}")
        )
    )
    def manage_zpos(self): pass

    @text_popup(
        title="Set Exposure",
        hint="Seconds",
        get_current=lambda self: f"Current Exposure: {self.setup.texp:.2f}s",
        validate=float,
        on_success=lambda self, t: (
            self.setup.set_exposure(t),
            setattr(self.label_exposure_status, 'text', f"Exposure: {t:.2f}s")
        )
    )
    def manage_exposure(self): pass

    @choice_popup(
        title="Choose Filter (1 - 12)",
        get_current=lambda self: f"Current filter: {self.setup.filter_id}",
        choices=[(str(k) + ' - ' + v.split('_')[0].replace('Center-', ''), k)
                  for k, v in FILTERS.items()],
        on_success=lambda self, fid: (
            self.setup.move_filter(fid),
            setattr(self.label_filter_status, 'text', f"Filter: {fid} - " + FILTERS[fid].split('_')[0].replace('Center-', ''))
        )
    )
    def choose_filter(self): pass

    @combo_popup(
        title="Set Sample",
        get_current=lambda self: f"Current: {self.setup.settings.get('SAMPLE_NAME', 'None')}",
        hint="Type new sample...",
        validate=str,
        choices=[(name, name) for name in SAMPLES.values()],
        on_success=lambda self, val: (
            self.setup.settings.__setitem__('SAMPLE_NAME', val),
            setattr(self.label_sample_status, 'text', f"Sample: {val}")
        )
    )
    def manage_spectra(self): pass
   
    def print_power_label(self, *_):
        power = self.setup.get_power()
        self.label_power.text = f"P: {power * 1e6:.2f} μW"
        

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

### ========== App ==========

class SabbathApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(MainScreen(name='main'))
        return sm

if __name__ == '__main__':
    SabbathApp().run()
