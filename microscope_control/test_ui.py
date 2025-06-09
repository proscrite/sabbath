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
import numpy as np
from scipy.stats import kurtosis
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
        self._add_button('Acquisition Settings 🎥⚙️', self.manage_camera_settings)
        self.button_layout.add_widget(Widget(size_hint_y=None, height=20))  # Spacer for layout balance
        self._add_button('Setup Settings 🛠️🧩', self.show_settings_menu)



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
        if self.manager.has_screen('autofocus'):
            self.manager.remove_widget(self.manager.get_screen('autofocus'))

        autofoc = AutofocusWhitelightMock(name='autofocus')
        self.manager.add_widget(autofoc)
        self.manager.current = 'autofocus'

    def manage_camera_settings(self):
        if self.manager.has_screen('camera_settings'):
            self.manager.remove_widget(self.manager.get_screen('camera_settings'))

        cam_set = CameraSettingsScreen(name='camera_settings')
        self.manager.add_widget(cam_set)
        self.manager.current = 'camera_settings'

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


### ========== Camera settings Screen ==========

class CameraSettingsScreen(Screen, PopupMixin):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # self.setup = Setup()
        root = BoxLayout(orientation='vertical')
        root.add_widget(Widget(size_hint_y=1))      # Spacer to push content down

        layout = GridLayout(cols=2, spacing=10, padding=10, size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))

        current_exposure = 0.5
        current_speed = 'fast'
        current_binning = 1
        current_image_size = 2048

        self.button_speed = Button(text=f"Speed: {current_speed}", size_hint=(1, None), height=50)
        self.button_speed.bind(on_press=self.set_readout_speed)
        layout.add_widget(self.button_speed)

        self.button_exposure = Button(text=f"Exposure: {current_exposure} s", size_hint=(1, None), height=50)
        self.button_exposure.bind(on_press=self.manage_exposure)
        layout.add_widget(self.button_exposure)

        self.button_binning = Button(text=f"Binning: {current_binning}", size_hint=(1, None), height=50)
        self.button_binning.bind(on_press=self.set_binning)
        layout.add_widget(self.button_binning)
    
        self.button_image_size = Button(text=f"Image Size: {current_image_size}", size_hint=(1, None), height=50)
        layout.add_widget(self.button_image_size)

        layout.add_widget(Button(text = "Go Back", size_hint=(1, None), height=50,
            on_release=self.go_back, font_name='EmojiFont'))

        root.add_widget(layout)
        root.add_widget(Widget(size_hint_y=1))      # Spacer to push content down
        self.add_widget(root)

    def manage_exposure(self, instance):
        # self.setup.manage_exposure()
        print("Managing exposure...")

    @choice_popup(
        title="Choose Speed",
        get_current=lambda self: f"Current Speed: {self.button_speed.text}",
        choices=[("Fast", "fast"), ("Slow", "slow")],
        on_success=lambda self, v: setattr(self.button_speed, 'text', f"Speed: {v}"),
        flag_popup='Readout Speed'
    )
    def set_readout_speed(self, *_):
        pass

    @choice_popup(
        title="Choose Binning",
        get_current=lambda self: f"Current Binning: {self.button_binning.text}",
        choices=[('1', 1), ('2', 2), ('4', 4)],
        on_success=lambda self, v: ( setattr(self.button_binning, 'text', f"Binning: {v}"),
                                    setattr(self.button_image_size, 'text', f"Image Size: {2048 // v}")),
        flag_popup='Binning'
    )
    def set_binning(self, *_):
        pass

    def go_back(self, *_):
        # Close the popup and return to the main screen
        
        self.manager.current = 'main'
        self.manager.remove_widget(self)

class AutofocusWhitelightMock(Screen):
    """Mockup autofocus screen for prototyping UI without hardware."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.abort = False
        self.init_zpos = 17.0

        # Build UI
        root = BoxLayout(orientation='vertical')
        self.fig, self.ax = plt.subplots(1, 2, figsize=(10, 4), dpi=100, sharey=True)
        self.mlp_canvas = FigureCanvasKivyAgg(self.fig)
        self.mlp_canvas.opacity = 0.0
        root.add_widget(self.mlp_canvas)

        # Continue button: starts fine autofocus after coarse
        self.continue_btn = Button(
            text="Continue to Fine Focus ✔️", font_name='EmojiFont', size_hint=(1, None), height=40,
            disabled=True
        )
        self.continue_btn.bind(on_press=self.call_autofocus_fine)
        root.add_widget(self.continue_btn)

        # Cancel button: always enabled to abort
        self.cancel_btn = Button(
            text="Cancel ✖️", font_name='EmojiFont', size_hint=(1, None), height=40
        )
        self.cancel_btn.bind(on_press=self.cancel_autofocus)
        root.add_widget(self.cancel_btn)

        self.add_widget(root)
        self.init_popup()

    def init_popup(self):
        content = GridLayout(cols=2, rows=3)
        content.add_widget(Label(text="Have you switched ON white light illumination?"))
        content.add_widget(Label())
        btn_yes = Button(text="Yes", size_hint_y=None, height=50)
        btn_yes.bind(on_press=self._start_coarse)
        btn_no = Button(text="Cancel", size_hint_y=None, height=50)
        btn_no.bind(on_press=self.cancel_autofocus)
        content.add_widget(btn_yes)
        content.add_widget(btn_no)

        # Row 3: Skip coarse and go fine
        content.add_widget(Label(text="Skip coarse and go to fine?"))
        btn_fine = Button(text="Fine Only ➡️", font_name='EmojiFont', size_hint_y=None, height=50)
        btn_fine.bind(on_press=self.skip_to_fine)
        content.add_widget(btn_fine)

        self.popup = Popup(
            title="Autofocus Confirmation",
            content=content,
            size_hint=(0.8, 0.5),
            auto_dismiss=False
        )
        self.popup.open()

    def skip_to_fine(self, *_):
        self.popup.dismiss()
        self.zpos_coarse = []
        self.kurt_coarse = []
        self.call_autofocus_pass(
            nsteps=20, step=-0.01,
            z_list_attr='zpos_fine',
            metric_list_attr='kurt_fine',
            ax=self.ax[1],
            title="Fine Autofocus Metric"
        )

    def cancel_autofocus(self, *_):
        self.abort = True
        if hasattr(self, 'popup'):
            self.popup.dismiss()
        self.manager.current = 'main'
        if self.manager.has_screen('autofocus_mock'):
            # Remove the autofocus screen if it exists
            self.manager.remove_widget(self.manager.get_screen('autofocus_mock'))

    def _start_coarse(self, *_):
        self.popup.dismiss()
        self.call_autofocus_pass(
            nsteps=20, step=-0.1,
            z_list_attr='zpos_coarse',
            metric_list_attr='kurt_coarse',
            ax=self.ax[0],
            title="Coarse Autofocus Metric"
        )

    def call_autofocus_fine(self, *_):
        self.continue_btn.disabled = True
        if hasattr(self, 'zpos_coarse') and self.zpos_coarse:
            best = self.zpos_coarse[np.argmax(self.kurt_coarse)]
            # In mock, just use the value, no hardware move
        self.call_autofocus_pass(
            nsteps=20, step=-0.01,
            z_list_attr='zpos_fine',
            metric_list_attr='kurt_fine',
            ax=self.ax[1],
            title="Fine Autofocus Metric"
        )

    def call_autofocus_pass(self, nsteps, step, z_list_attr, metric_list_attr, ax, title):
        setattr(self, z_list_attr, [])
        setattr(self, metric_list_attr, [])
        self.current_ax = ax
        setattr(self, 'nsteps', nsteps)
        setattr(self, 'step', step)
        self.mlp_canvas.opacity = 1.0
        threading.Thread(
            target=self._loop_autofocus,
            args=(nsteps, step, z_list_attr, metric_list_attr, ax, title),
            daemon=True
        ).start()

    def _loop_autofocus(self, nsteps, step, z_attr, k_attr, ax, title):
        img0 = np.random.normal(100, 10, (256, 256)).astype('float64')
        zpos = self.init_zpos
        for i in range(nsteps):
            if self.abort:
                break
            # Simulate a focus curve: kurtosis peaks in the middle
            img = img0 + np.random.normal(0, 5, (256, 256))
            # Add a synthetic focus effect
            focus_factor = np.exp(-((i - nsteps//2)/5)**2)
            img += focus_factor * np.random.normal(50, 10, (256, 256))
            img_bg = img - img0
            z = round(zpos + i * step, 3)
            k = kurtosis(img_bg.flatten(), fisher=True, bias=False)
            getattr(self, z_attr).append(z)
            getattr(self, k_attr).append(k)
            Clock.schedule_once(lambda dt, z=z, k=k: self._update_plot(z, k, ax, title))
        Clock.schedule_once(lambda dt: self._finish_pass(z_attr, k_attr), 0)

    def _update_plot(self, z, k, ax, title):
        ax.clear()
        zlist = getattr(self, 'zpos_' + title.split()[0].lower())
        klist = getattr(self, 'kurt_' + title.split()[0].lower())
        ax.plot(zlist, klist)
        ax.set(title=title, xlabel="Z Position (mm)", ylabel="Kurtosis")
        self.mlp_canvas.draw()

    def _finish_pass(self, z_attr, k_attr):
        zlist = getattr(self, z_attr)
        klist = getattr(self, k_attr)
        if not zlist:
            return  # aborted
        best_i = int(np.argmax(klist))
        best_z = zlist[best_i]
        print(f"Best focus at {best_z} mm for {z_attr}")
        # No hardware move in mock

        if z_attr == 'zpos_fine':
            self.continue_btn.text = 'Return to main menu'
            self.abort = True
            self.continue_btn.bind(on_press=self.closing_popup)
            self.continue_btn.disabled = False
        else:
            self.continue_btn.disabled = False
            self._countdown = 3
            self.continue_btn.text = f"Continue to Fine Focus ✔️ ({self._countdown}s)"
            self._countdown_event = Clock.schedule_interval(self._auto_continue_countdown, 1)

    def _auto_continue_countdown(self, dt):
        self._countdown -= 1
        if self.abort:
            return False
        if self._countdown > 0:
            self.continue_btn.text = f"Continue to Fine Focus ✔️ ({self._countdown}s)"
            return True
        self.continue_btn.text = "Continue to Fine Focus ✔️"
        self._countdown_event.cancel()
        self.call_autofocus_fine()
        return False

    def closing_popup(self, *_):
        content = GridLayout(cols=2, rows=2)
        content.add_widget(Label(text="Have you switched OFF white light illumination?"))
        btn_yes = Button(text="Yes", size_hint_y=None, height=50)
        btn_yes.bind(on_press=self.cancel_autofocus)
        content.add_widget(btn_yes)
        self.popup = Popup(
            title="Light off reminder",
            content=content,
            size_hint=(0.8, 0.5),
            auto_dismiss=False
        )
        self.popup.open()
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
