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
from kivy.uix.progressbar import ProgressBar
from kivy.metrics import dp
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
from skimage import io

from kivy_garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg


import logging
# raise font_manager (and all matplotlib) to WARNING+
logging.getLogger('matplotlib.font_manager').setLevel(logging.WARNING)
logging.getLogger('matplotlib').setLevel(logging.WARNING)
from kivy.logger import Logger
Logger.setLevel(logging.INFO)
from functools import partial, wraps

from microscope_control.saving import *
from microscope_control.SetupSettings import write_settings
from microscope_control.Constants import *
from .main import Setup  # your actual Setup class
from .autofocus_whitelight import autofocus_whitelight
from microscope_control.screen_roi_selection import ROI_selection_screen, draw_roi

ROOT_DIR = r'C:\Users\owner\Documents\sabbath\microscope_control'
TEST_IMAGE = ROOT_DIR + '\\test_image-Center-575nm_Width-35nm__P_378.4uW_frame_000.tif'

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

        popup = Popup(title=title, content=layout, size_hint=(0.6, 0.85))

        for label, val in choices:
            btn = Button(text=label, size_hint_y=None, height=40)
            btn.bind(on_press=lambda *_ ,v=val: (on_success(v), popup.dismiss()))
            layout.add_widget(btn)

        popup.open()

    def _show_combo_popup(self, *, title, current_text, hint, validate, choices, on_success, size_hint=(0.8, 0.8)):
        
        scroll = ScrollView(size_hint=(1, 1))
        popup = Popup(title=title, content=scroll, size_hint=size_hint)  
        
        grid = GridLayout(cols=2, spacing=5, size_hint_y=None)
        grid.add_widget(Label(text=current_text, size_hint_y=None, height=40))
        grid.add_widget(Widget(size_hint_y=None, height=40))     # empty space for layout balance
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

def choice_popup(title, get_current, choices, on_success, flag_popup: str = None):
    def deco(fn):
        @wraps(fn)
        def wrapped(self, *args, **kwargs):
            if flag_popup and getattr(self, flag_popup, False):
                return fn(self, *args, **kwargs)
            def _on_choice(v):
                on_success(self, v)
                fn(self, v, *args, **kwargs)
            self._show_choice_popup(
                title=title,
                current_text=get_current(self),
                choices=choices,
                on_success=_on_choice
            )
        return wrapped
    return deco

def combo_popup(title, get_current, hint, validate, choices, on_success, flag_popup: str = None):
    def deco(fn):
        @wraps(fn)
        def wrapped(self, *args, **kwargs):
            if flag_popup and getattr(self, flag_popup, False):
                return fn(self, *args, **kwargs)
            # else, show the combo popup
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
        # self.setup = Setup()
        # self.setup.init_settings()
        # self.setup.open_all_devices()
        self.layout = FloatLayout()
        self.status_layout = GridLayout(cols=4, padding=10, spacing=15,
                                size_hint=(None, None),
                                size=(600, 200),              # Adjust size of grid manually
                                pos_hint={"center_x": 0.5, "top": 0.9})
        
        self.button_layout = GridLayout(cols=3, padding=10, spacing=10,
                                        size_hint=(None, None),
                                        size=(400, 300),              # Adjust size of grid manually
                                        pos_hint={"center_x": 0.35, "center_y": 0.4})
        self._init_labels()
        self._init_buttons()
        self.layout.add_widget(self.status_layout)
        self.layout.add_widget(self.button_layout)
        self.filter_chosen = False
        self.sample_chosen = False
        
        self.add_widget(self.layout)

    def _init_labels(self):
        zpos = 12
        power = 5e-6
        filter_id = 1
        # zpos = self.setup.read_zpos()
        # power = self.setup.get_power()
        # filter_id = self.setup.filter_id

        proportions = [40, 300]
        self.icon_shutter_status = self._add_label(text="🚫", font_size=30, x_proportion=proportions[0])
        self.label_shutter_status = self._add_label(text=f"Shutter: Closed ", x_proportion=proportions[1])
        self._add_label(text="🕹️", font_size=30, x_proportion=proportions[0])
        self.label_status_z = self._add_label(text=f"Z Position: {zpos} mm ", x_proportion=proportions[1])
        self._add_label(text="⏳", font_size=30, x_proportion=proportions[0])
        self.label_exposure_status = self._add_label(text="Exposure: 0.5 s ", x_proportion=proportions[1])
        self._add_label(text="🚦", font_size=30, x_proportion=proportions[0])
        self.label_filter_status = self._add_label(text=f"Filter: {filter_id} - 575 nm", x_proportion=proportions[1])
        self._add_label(text="🧬", font_size=30, x_proportion=proportions[0])
        self.label_sample_status = self._add_label(text=f"Sample: Rhodamine-B 50 nM 140525", x_proportion=proportions[1])
        self._add_label(text="🔋", font_size=30, x_proportion=proportions[0])
        self.label_power = self._add_label(text=f"Power: {power * 1e6:.2f} uW ", x_proportion=proportions[1])

        
        self.status_layout.add_widget(Label(text=""))  # Empty space for layout balance

    def _init_buttons(self):
        self._add_button('Take Spectra 🎨📊', self.manage_spectra)
        self._add_button('Time Trajectories ⏱️📉', self.manage_time_evolution)
        self._add_button('Power ramp 🔌', self.power_ramp)
        self._add_button('Take Image 📸', self.manage_take_image)
        self._add_button('Live Camera 🎥', self.manage_live_cam)
        self._add_button('Autofocus 🔍', self.call_autofocus)
        self._add_button('Set Sample name 🧫', self.set_sample_name)
        self._add_button('Set ROI 🎯', self.manage_ROI)
        self._add_button('Set Filter 🚥', self.choose_filter)
        self._add_button('Set Exposure 💥', self.manage_exposure)
        self._add_button('Move Z Position 🎮 ', self.manage_zpos)
        self._add_button('Refresh Power reading 📟🔋', self.print_power_label)
        self._add_button('Manage Power 🎚️🔋', self.manage_power)
        self._add_button('Toggle Shutter 🎬', self.manage_toggle_shutter)
        self._add_button('Settings ⚙️', self.show_settings_menu)


    def _add_label(self, text, font_size=18, x_proportion = 0.2):
        lb = Label(text=text, font_name = 'EmojiFont', font_size=font_size, size_hint_x=None, width = x_proportion,
                    halign='left', valign='middle', text_size=(None, None))
        lb.bind(size=lambda l, s: setattr(l, 'text_size', (s[0], None)))
        self.status_layout.add_widget(lb)
        return lb

    def _add_button(self, text, func):
        btn = Button(text=text, font_name = 'EmojiFont', size_hint=(None, None), size=(200, 50))
        btn.bind(on_press=lambda *_: func())
        self.button_layout.add_widget(btn)

    def manage_spectra(self):
        # self.setup.take_spectra()
        print("Taking spectra...")
    
    def manage_time_evolution(self):
        # self.setup.take_time_evolution()
        print("Taking time evolution...")

    def manage_take_image(self, *_):
        name = 'New Rhodamine-B sample'
        if self.manager.has_screen('single_image'):
            self.manager.remove_widget(self.manager.get_screen('single_image'))

        # create & add the new screen
        spec = ImageScreen(
            name= 'single_image',
            sample_name= name
        )
        self.manager.add_widget(spec)
        self.manager.current = 'single_image'

    def manage_live_cam(self):
        # self.setup.manage_live_cam()
        print("Managing live camera...")

    def call_autofocus(self):
        # self.setup.call_autofocus()
        print("Calling autofocus...")

    def set_sample_name(self):
        pass

    def manage_ROI(self):
        # self.setup.manage_ROI()
        print("Managing ROI...")

    def choose_filter(self):
        # self.setup.choose_filter()
        print("Choosing filter...")

    def manage_exposure(self):
        # self.setup.manage_exposure()
        print("Managing exposure...")

    def manage_zpos(self):
        # self.setup.manage_zpos()
        print("Managing Z position...")

    def print_power_label(self):
        # self.setup.print_power_label()
        print("Power label printed...")

    def manage_power(self):
        # self.setup.manage_power()
        print("Managing power...")

    def manage_toggle_shutter(self):
        # self.setup.manage_toggle_shutter()
        print("Toggling shutter...")

    def show_settings_menu(self):
        # self.setup.show_settings_menu()
        print("Showing settings menu...")

    def power_ramp(self):
        # self.setup.power_ramp()
        print("Power ramping...")

### ========== Single image Screen ==========


class ImageScreen(Screen):
    def __init__(self, sample_name, **kwargs):
        super().__init__(**kwargs)
        self.sample_name = sample_name
        self.roi = [750, 1500, 500, 1250]

        root = BoxLayout(orientation='vertical')
        self.fig, self.ax = plt.subplots()
        self.mpl_canvas = FigureCanvasKivyAgg(self.fig)
        root.add_widget(self.mpl_canvas)

        # Continue button,
        self.continue_btn = Button(text="Continue ✔️", font_name='EmojiFont',
            size_hint=(1, None), height=50, disabled=False)
        # When pressed, switch back to main screen:
        self.continue_btn.bind(on_press=lambda *_: setattr(self.manager, 'current', 'main'))
        root.add_widget(self.continue_btn)

        self.save_btn = Button(text="Save Image 💾", font_name='EmojiFont',
            size_hint=(1, None), height=50, disabled=False)
        # When pressed, save image:
        self.save_btn.bind(on_press=lambda *_: self.save_image(img))
        root.add_widget(self.save_btn)
        self.add_widget(root)

        img = io.imread(TEST_IMAGE).astype(np.int64)
        self.display_image(img)

    def get_cutoff(self, img, threshold=8):
        n, bins = np.histogram(img.flatten(), bins=int(img.shape[0]/2) )
        cbins = (bins[:-1] + bins[1:]) / 2
        return cbins[n>threshold].max()
    
    def display_image(self, img):
        # Display the image using matplotlib

        if self.roi is not None:
            # Draw the ROI on the image
            draw_roi(self.ax, self.roi)
        
        cutoff = self.get_cutoff(img, threshold=8)
        axob = self.ax.imshow(img, clim = (100, cutoff))
        plt.colorbar(axob, ax=self.ax)
        self.ax.set_title(f"Image for {self.sample_name}")
        self.mpl_canvas.draw()
        
    def save_image(self, img):
        # Save the image using the save_tif_set function
        rootpath = IMAGE_SINGLE_SAVE_LOCATION
        save_path = check_path_save(rootpath, self.sample_name, filters=None)
        
        self.save_btn.text = f"Image saved! 💾✅️"
        print(f"Image saved to: {save_path}")

### ========== App ==========

class SabbathApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(MainScreen(name='main'))
        return sm

    def on_stop(self):
        # Close all devices when the app is closed
        print("All devices closed.")
if __name__ == '__main__':
    SabbathApp().run()
