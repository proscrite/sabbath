from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.core.text import LabelBase
from kivy.core.text import FontContextManager as FCM
from kivy.clock import Clock

import threading
import time
import matplotlib.pyplot as plt
from matplotlib import rcParams
rcParams.update({'errorbar.capsize': 4})
import pandas as pd
from kivy_garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg


import logging
# raise font_manager (and all matplotlib) to WARNING+
logging.getLogger('matplotlib.font_manager').setLevel(logging.WARNING)
logging.getLogger('matplotlib').setLevel(logging.WARNING)
from kivy.logger import Logger
Logger.setLevel(logging.INFO)
from functools import partial, wraps

from microscope_control.saving import save_tif_set
from microscope_control.SetupSettings import write_settings
from microscope_control.Constants import FILTERS, SAMPLES, FILTER_PATH
from .main import Setup  # your actual Setup class

# # 1) Create a shared context:
# FCM.create('emoji_greek')
# # 2) Add seguiemj.ttf (color emoji) and a Greek font:
# FCM.add_font(r'C:\Windows\Fonts\seguiemj.ttf')
# # e.g. Segoe UI Variable (has Greek) or Gentium if you’ve installed it
# FCM.add_font(r'C:\Windows\Fonts\seguisym.ttf')  

LabelBase.register(
    name='EmojiFont',
    fn_regular=r'C:\Windows\Fonts\seguiemj.ttf'
)
### ========== Popup Helpers ==========
def _validate_nonempty_text(s):
    s = s.strip()
    if not s:
        raise ValueError("Input cannot be empty")
    return s

class PopupMixin:
    def _show_input_popup(self, *, title, current_text, hint, validate, on_success, size_hint=(0.5, 0.5)):
        layout = GridLayout(cols=1, padding=10, spacing=10)
        layout.add_widget(Label(text=current_text, font_name ='EmojiFont', ))
        ti = TextInput(hint_text=hint, font_name='EmojiFont', multiline=False)
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

    def _show_choice_popup(self, *, title, current_text, choices, on_success, size_hint=(0.6, 0.9)):
        layout = GridLayout(cols=2, spacing=10, padding=10)
        layout.add_widget(Label(text=current_text, size_hint_y=None, height=40))
        layout.add_widget(Widget(size_hint_y=None, height=0))

        popup = Popup(title=title, content=layout, size_hint=(0.6, 1.0))

        for label, val in choices:
            btn = Button(text=label, size_hint_y=None, height=40)
            btn.bind(on_press=lambda *_ ,v=val: (on_success(v), popup.dismiss()))
            layout.add_widget(btn)

        popup.open()

    def _show_combo_popup(self, *, title, current_text, hint, validate, choices, on_success, size_hint=(0.8, 0.8)):
        
        scroll = ScrollView(size_hint=(1, 1))
        popup = Popup(title=title, content=scroll, size_hint=size_hint)  
        
        grid = GridLayout(cols=2, spacing=5, size_hint_y=None)
        grid.add_widget(Label(text=current_text))
        for label, val in choices:
            btn = Button(text=val, size_hint_y=None, height=40)
            btn.bind(on_press=lambda *_ ,v=val: (on_success(v), popup.dismiss()))
            grid.add_widget(btn)

        ti = TextInput(hint_text=hint, multiline=False, font_name = 'EmojiFont', size_hint_y=None, height=40)  
        def _do_set(*_):
            try:
                v = validate(ti.text)
                on_success(v)
                popup.dismiss()
            except ValueError as e:
                print('Exception: ', e)
                ti.text = "❌ invalid"
        ti.bind(on_text_validate=_do_set)
        grid.add_widget(ti)
        scroll.add_widget(grid)
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
            def _on_choice(v):
                on_success(self, v)
                fn(self, v, *args, **kwargs)
            self._show_combo_popup(
                title=title,
                current_text=get_current(self),
                hint=hint,
                validate=validate,
                choices=choices,
                on_success=_on_choice
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
        filter_id = self.setup.filter_id
        self.label_shutter_status = self._add_label(text=f"Shutter: Closed 🚫")
        self.label_status_z = self._add_label(text=f"Z Position: {zpos} 🕹️")
        self.label_exposure_status = self._add_label(text="Exposure: 0.5 s ⏳")
        self.label_filter_status = self._add_label(text=f"Filter: {filter_id} NA 🚦 - " + FILTERS[self.setup.filter_id].split('_')[0].replace('Center-', ''))
        self.label_sample_status = self._add_label(text=f"Sample: {self.setup.settings.get('SAMPLE_NAME', 'value')} 🧫🦠🧬")
        self.label_power = self._add_label(text=f"Power: {power * 1e6:.2f} uW 🔋⚡")
        
        self.status_layout.add_widget(Label(text=""))  # Empty space for layout balance

    def _init_buttons(self):
        self._add_button('Take Spectra 🎨📊', self.manage_spectra)
        self._add_button('Time Trajectories ⏱️📉', self.setup.time_evolution)
        self._add_button('Take Image 📸', self.manage_take_image)
        self._add_button('Power ramp 🔌', self.setup.power_ramp)
        self._add_button('Live Camera 🎥', self.manage_live_cam)
        self._add_button('Set Sample name 🧫', self.set_sample_name)
        self._add_button('Set ROI 🎯', self.setup.select_ROI)
        self._add_button('Set Filter 🚥', self.choose_filter)
        self._add_button('Set Exposure 💥', self.manage_exposure)
        self._add_button('Move Z Position 🎮 ', self.manage_zpos)
        self._add_button('Refresh Power reading 📟🔋', self.print_power_label)
        self._add_button('Manage Power 🎚️🔋', self.manage_power)
        self._add_button('Toggle Shutter 🎬', self.manage_toggle_shutter)
        self._add_button('Settings ⚙️', self.show_settings_menu)


    def _add_label(self, text):
        lb = Label(text=text, font_name = 'EmojiFont', font_size=18, size_hint=(1, 0.2))
        self.status_layout.add_widget(lb)
        return lb


    def _add_button(self, text, func):
        btn = Button(text=text, font_name = 'EmojiFont', size_hint=(None, None), size=(200, 50))
        btn.bind(on_press=lambda *_: func())
        self.button_layout.add_widget(btn)

    def manage_take_image(self, *_):
        # Check if the camera is open before taking an image
        if self.setup.cam.is_open:
            
            img = self.setup.cam.snap(timeout=15)

        else:
            print("Camera is not open. Please open the camera first.")
            self.setup.cam.open()

    @text_popup(
        title="Set Z Position",
        hint="Z in mm",
        get_current=lambda self: f"Current Z: {self.setup.read_zpos():.3f} 🕹️",
        validate=float,
        on_success=lambda self, z: (
            self.setup.move_zpos(z),
            setattr(self.label_status_z, 'text', f"Z Position: {z:.3f} 🕹️")
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
            setattr(self.label_exposure_status, 'text', f"Exposure: {t:.2f}s ⏳")
        )
    )
    def manage_exposure(self): pass

    @choice_popup(
        title="Choose Filter (1 - 12)",
        get_current=lambda self: f"Current filter: {self.setup.filter_id} - " + FILTERS[self.setup.filter_id].split('_')[0].replace('Center-', ''),
        choices=[(str(k) + ' - ' + v.split('_')[0].replace('Center-', ''), k)
                  for k, v in FILTERS.items()],
        on_success=lambda self, fid: (
            self.setup.move_filter(fid),
            setattr(self.label_filter_status,
                     'text', f"Filter: {fid} - " + FILTERS[fid].split('_')[0].replace('Center-', '') + " 🚦" if fid != 0 else "Filter: None 🚦"),
        )
    )
    def choose_filter(self): pass

    @combo_popup(
        title="Set Sample",
        get_current=lambda self: f"Current: {self.setup.settings.loc['SAMPLE_NAME', 'value']} ",
        hint="Type new sample...",
        validate=_validate_nonempty_text,
        choices=[(key, name) for key, name in SAMPLES.items() if name != 'quit' and name != 'other'],
        on_success=lambda self, val: (
            print(f"Sample set to: {val}"),
            setattr(self.label_sample_status, 'text', f"Sample: {val} 🧫🦠🧬"),
        )
    )
    def manage_spectra(self, val, *_):
        # grab the current sample name
        print('Entering manage_spectra after decorator')
        self.setup.settings.at['SAMPLE_NAME', 'value'] = val
        name = self.setup.settings.loc['SAMPLE_NAME', 'value']
        # if there’s already a SpectrumScreen, remove it:
        if self.manager.has_screen('spectrum'):
            self.manager.remove_widget(self.manager.get_screen('spectrum'))

        # create & add the new screen
        spec = SpectrumScreen(
            name= 'spectrum',
            setup= self.setup,
            sample_name= name
        )
        self.manager.add_widget(spec)
        self.manager.current = 'spectrum'
   
    @choice_popup(
        title="Confirmation",
        get_current=lambda self: f"Current: {self.setup.settings.get('SAMPLE_NAME', 'value')} ",
        choices=[("Yes", True), ("No", False)],
        on_success=lambda self, val: (
            setattr(self.setup.settings.loc['SAMPLE_NAME', 'value'], val),
            setattr(self.label_sample_status, 'text', f"Sample: {val} 🧫🦠🧬"
                     if val else setattr(self.label_sample_status, 'text', f"Sample: None', ")),
        )
    )
    def confirmation_popup(self): pass

    def print_power_label(self, *_):
        power = self.setup.get_power()
        self.label_power.text = f"P: {power * 1e6:.2f} uW 🔋⚡"
        
    def manage_power(self, *_):
        pass

    def show_settings_menu(self, *_):
        settings_df = self.setup.settings

        grid = GridLayout(cols=2, spacing=10, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        # Define callback to open the objective selector popup
        def choose_objective(instance):
            def set_objective(value):
                # Update the DataFrame
                settings_df.at['MICROSCOPE_OBJECTIVE', 'value'] = value
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
            grid.add_widget(Label(text=str(index), size_hint_y=None, height=30))

            if index == 'MICROSCOPE_OBJECTIVE':
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

        self.label_shutter_status.text = f"Shutter: {'Open 🟢' if shutter_state else 'Closed 🚫'}"
        self.print_power_label()

    def manage_live_cam(self, *_):
        threading.Thread(target=self.setup.live_cam, daemon=True).start()

### ========== Spectrum Screen ==========

class SpectrumScreen(Screen):
    def __init__(self, setup, sample_name, **kwargs):
        super().__init__(**kwargs)
        self.setup       = setup
        self.sample_name = sample_name
        self.filt_stats = pd.read_csv(FILTER_PATH)
        self.filt_center = self.filt_stats['central_lambda'].astype(float)[:10]
        self.filt_center = self.filt_center[::-1]
        self.filt_range = self.filt_stats['range_width'].astype(float)[:10] / 2
        self.filt_range = self.filt_range[::-1]

        # 1) Build your UI on the main thread:
        root = BoxLayout(orientation='vertical')
        self.fig, self.ax = plt.subplots()
        self.mpl_canvas = FigureCanvasKivyAgg(self.fig)
        root.add_widget(self.mpl_canvas)

        # Continue button, initially disabled:
        self.continue_btn = Button(
            text="Continue ✔️", font_name='EmojiFont',
            size_hint=(1, None), 
            height=50, 
            disabled=True
        )
        # When pressed, switch back to main screen:
        self.continue_btn.bind(on_press=lambda *_: setattr(self.manager, 'current', 'main'))
        root.add_widget(self.continue_btn)

        self.add_widget(root)

        # storage for the dynamic data
        self.processed_filters = []
        self.processed_sums    = []

        # 2) Launch the hardware loop in a background thread
        threading.Thread(target=self._acquire_loop, daemon=True).start()

    def _acquire_loop(self):
        # Loop over filters 1→12
        images = []
        powers = []
        for fid in range(12, 0, -1):
            # set filter, snap image
            self.setup.wheel.set_filter(fid)
            self.setup.open_shutter()
            power_i = self.setup.get_power() * 1e6  # in uW
            powers.append(power_i)
            img = self.setup.cam.snap(timeout=15)
            self.setup.close_shutter()

            images.append(img)
            # compute sum of pixels
            total = img.sum()

            # schedule a UI update
            Clock.schedule_once(lambda dt, f=fid, s=total: self._update_plot(f, s))

        avg_power = sum(powers) / len(powers)
        save_path = save_tif_set(images, self.sample_name, power=avg_power)

        self.setup.settings.loc['POWER(uW)', 'value'] = round(avg_power, 2)
        write_settings(save_path, self.setup.settings)
        print(f"Images saved to: {save_path}")
        Clock.schedule_once(lambda dt: setattr(self.continue_btn, 'disabled', False))

    def _update_plot(self, filter_id, sum_val):
        # collect
        self.processed_filters.append(filter_id)
        self.processed_sums.append(sum_val)
        x = self.filt_center[:len(self.processed_filters)]
        y = self.processed_sums[:len(self.processed_filters)]
        xerr = self.filt_range[:len(self.processed_filters)]
        # redraw
        if len(self.processed_filters) < 11:
            
            self.ax.clear()
            self.ax.errorbar(x = x, y = y, xerr=xerr,
                        marker='o')
            self.ax.set_xlabel('Wavelength (nm)')
            self.ax.set_ylabel('Sum of pixels')
            self.ax.set_title(f"Spectrum for {self.sample_name}")
            self.mpl_canvas.draw()


### ========== App ==========

class SabbathApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(MainScreen(name='main'))
        return sm

    def on_stop(self):
        # Close all devices when the app is closed
        self.root.get_screen('main').setup.close_all_devices()
        print("All devices closed.")
if __name__ == '__main__':
    SabbathApp().run()
