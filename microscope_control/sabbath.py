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
<<<<<<< Updated upstream

from microscope_control.screen_roi_selection import ROI_selection_screen, draw_roi
=======
from .autofocus_whitelight import autofocus_whitelight
from microscope_control.screen_roi_selection import ROI_selection_screen, draw_roi, get_cutoff
>>>>>>> Stashed changes

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
        self.setup = Setup()
        self.setup.init_settings()
        self.setup.open_all_devices()
        self.layout = FloatLayout()
        self.status_layout = GridLayout(cols=4, padding=10, spacing=15,
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
        self.filter_chosen = False
        self.sample_chosen = False
        
        self.add_widget(self.layout)

    def _init_labels(self):
        zpos = self.setup.read_zpos()
        power = self.setup.get_power()
        filter_id = self.setup.filter_id
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
        self._add_button('Take Image 📸', self.manage_take_image)
        self._add_button('Power ramp 🔌', self.setup.power_ramp)
        self._add_button('Live Camera 🎥', self.manage_live_cam)
        self._add_button('Set Sample name 🧫', self.set_sample_name)
        self._add_button('Set ROI 🎯', self.manage_ROI)
        self._add_button('Set Filter 🚥', self.choose_filter)
        self._add_button('Set Exposure 💥', self.manage_exposure)
        self._add_button('Move Z Position 🎮 ', self.manage_zpos)
        self._add_button('Refresh Power reading 📟🔋', self.print_power_label)
        self._add_button('Manage Power 🎚️🔋', self.manage_power)
        self._add_button('Toggle Shutter 🎬', self.manage_toggle_shutter)
        self._add_button('Settings ⚙️', self.show_settings_menu)


    def _add_label(self, text, font_size=18, x_proportion = 200):
        lb = Label(text=text, font_name = 'EmojiFont', font_size=font_size, size_hint_x=None, width = x_proportion,
                    halign='left', valign='middle', text_size=(None, None))
        lb.bind(size=lambda l, s: setattr(l, 'text_size', (s[0], None)))
        self.status_layout.add_widget(lb)
        return lb
    def _add_button(self, text, func):
        btn = Button(text=text, font_name = 'EmojiFont', size_hint=(None, None), size=(200, 50))
        btn.bind(on_press=lambda *_: func())
        self.button_layout.add_widget(btn)

    def manage_take_image(self, *_):
        name = self.setup.settings.loc['SAMPLE_NAME', 'value']
        if self.manager.has_screen('single_image'):
            self.manager.remove_widget(self.manager.get_screen('single_image'))

        # create & add the new screen
        spec = ImageScreen(
            name= 'single_image',
            setup= self.setup,
            sample_name= name
        )
        self.manager.add_widget(spec)
        self.manager.current = 'single_image'

    def manage_zpos(self):
        # Popup to adjust Z position with step buttons and direct-input until "Continue" is pressed
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        # Current position label
        self.zpos_label = Label(text=f"Z Position: {self.setup.read_zpos():.3f} mm 🕹️",
                      font_name='EmojiFont', size_hint_y=None, height=40)
        layout.add_widget(self.zpos_label)

        # TextInput for direct jump to position
        self.ti_select_position = TextInput(hint_text='Enter position in mm',
                                           font_name='EmojiFont', multiline=False,
                                           size_hint_y=None, height=40)
        # bind enter key to validate and move
        self.ti_select_position.bind(on_text_validate=lambda instance: self._validate_ztext_input())
        layout.add_widget(self.ti_select_position)

        # Container for step buttons
        self.btn_layout = GridLayout(cols=4, spacing=10, size_hint_y=None, height=200)
        
        # helper to add +/- buttons
        def add_step_buttons(val):
            for sign in (+1, -1):
                btn = Button(text=f"{sign*val:+.2f} mm", font_name='EmojiFont',
                             size_hint_y=None, height=40)
                # wrap move to disable/enable
                def _on_press(step, button):
                    # disable all buttons while moving
                    for child in self.btn_layout.children:
                        child.disabled = True
                    self.ti_select_position.disabled = True
                    # perform move
                    self.setup.move_zpos_step(step)
                    # update labels
                    pos = self.setup.read_zpos()
                    self.zpos_label.text = f"Z Position: {pos:.3f} mm 🕹️"
                    self.label_status_z.text = f"Z Position: {pos:.3f}"
                    # re-enable
                    for child in self.btn_layout.children:
                        child.disabled = False
                    self.ti_select_position.disabled = False
                btn.bind(on_press=lambda inst, s=sign*val, b=btn: _on_press(s, b))
                self.btn_layout.add_widget(btn)
        
        # default steps
        for step in [0.05, 0.1, 0.5, 1, 5]:
            add_step_buttons(step)
        layout.add_widget(self.btn_layout)

        # TextInput to add custom step size
        self.ti_step_size = TextInput(hint_text='Custom step (0.001–5 mm)',
                                      font_name='EmojiFont', multiline=False,
                                      size_hint_y=None, height=40, width=250)
        def _validate_step_size(instance):
            try:
                v = float(self.ti_step_size.text)
                if not 0.001 <= v <= 5:
                    raise ValueError
                add_step_buttons(v)
                self.ti_step_size.text = ''
            except Exception:
                self.ti_step_size.text = '❌ invalid'
        self.ti_step_size.bind(on_text_validate=lambda inst: _validate_step_size(inst))
        self.btn_layout.add_widget(self.ti_step_size)

        # Continue button to close
        btn_continue = Button(text='Continue ✔️', font_name='EmojiFont',
                              size_hint_y=None, height=40)
        btn_continue.bind(on_press=lambda *_: popup.dismiss())
        layout.add_widget(btn_continue)

        # create and open popup
        popup = Popup(title='Move Z Position', content=layout,
                      size_hint=(0.7, 0.7))
        popup.open()

    def _validate_ztext_input(self):
        try:
            val = float(self.ti_select_position.text)
            # move and update
            self.setup.move_zpos(val)
            pos = self.setup.read_zpos()
            self.zpos_label.text = f"Z Position: {pos:.3f} mm 🕹️"
            self.label_status_z.text = f"Z Position: {pos:.3f} 🕹️"
            self.ti_select_position.text = ''
        except Exception:
            self.ti_select_position.text = '❌ invalid'

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
        get_current=lambda self: f"Current filter: {self.setup.filter_id} - " + FILTERS[self.setup.filter_id].split('_')[0].replace('Center-', ''),
        choices=[(str(k) + ' - ' + v.split('_')[0].replace('Center-', ''), k)
                  for k, v in FILTERS.items()],
        on_success=lambda self, fid: (
            self.setup.move_filter(fid),
            setattr(self.label_filter_status,
                    'text', f"Filter: {fid} - " + FILTERS[fid].split('_')[0].replace('Center-', '') if fid != 0 else "Filter: None"),
            )
    )
    def choose_filter(self, *_): 
        self.filter_chosen = True
        pass

    @combo_popup(
        title="Set Sample",
        get_current=lambda self: f"Current: {self.setup.settings.loc['SAMPLE_NAME', 'value']} ",
        hint="Type new sample...",
        validate=_validate_nonempty_text,
        choices=[(key, name) for key, name in SAMPLES.items() if name != 'quit' and name != 'other'],
        on_success=lambda self, val: (
            print(f"Sample set to: {val}"),
            setattr(self.label_sample_status, 'text', f"Sample: {val}"),
        )
    )
    def set_sample_name(self, val, *_):
        self.setup.settings.at['SAMPLE_NAME', 'value'] = val
        self.sample_chosen = True
        pass
    
    @combo_popup(
        title="Set Sample",
        get_current=lambda self: f"Current: {self.setup.settings.loc['SAMPLE_NAME', 'value']} ",
        hint="Type new sample...",
        validate=_validate_nonempty_text,
        choices=[(key, name) for key, name in SAMPLES.items() if name != 'quit' and name != 'other'],
        on_success=lambda self, val: (
            print(f"Sample set to: {val}"),
            setattr(self.label_sample_status, 'text', f"Sample: {val}"),
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
        title="Choose Filter (1 - 12)",
        get_current=lambda self: f"Current filter: {self.setup.filter_id} - " + FILTERS[self.setup.filter_id].split('_')[0].replace('Center-', ''),
        choices=[(str(k) + ' - ' + v.split('_')[0].replace('Center-', ''), k)
                  for k, v in FILTERS.items()],
        on_success=lambda self, fid: (
            self.setup.move_filter(fid),
            setattr(self.label_filter_status,
                     'text', f"Filter: {fid} - " + FILTERS[fid].split('_')[0].replace('Center-', '') if fid != 0 else "Filter: None"),
        ),
        flag_popup='filter_chosen',
    )   
    @combo_popup(
        title="Set Sample",
        get_current=lambda self: f"Current: {self.setup.settings.loc['SAMPLE_NAME', 'value']} ",
        hint="Type new sample...",
        validate=_validate_nonempty_text,
        choices=[(key, name) for key, name in SAMPLES.items() if name != 'quit' and name != 'other'],
        on_success=lambda self, val: (
            print(f"Sample set to: {val}"),
            setattr(self.label_sample_status, 'text', f"{val}"),
        ),
        flag_popup='sample_chosen',
    )
    @combo_popup(
        title="Select number of frames",
        get_current=lambda self: f"Number of frames: (1 - 400)",
        hint="Type exact number...",
        validate=_validate_nonempty_text,
        choices=[(str(key), str(key)) for key in NFRAMES],
        on_success=lambda self, val: (
            print(f"Selected {val} frames"),
        )
    )
    def manage_time_evolution(self, n_frames, *_):
        # grab the current sample name
        print('Entering manage_time_evolution after decorator')
        sample_name = self.label_sample_status.text
        self.setup.settings.at['SAMPLE_NAME', 'value'] = sample_name
        setattr(self.label_sample_status, 'text', f"Sample: {sample_name}"),
        n_frames = int(n_frames)
        print('Sample name: ', sample_name)
        print('Number of frames: ', n_frames)
        # if there’s already a TrajectoryScreen, remove it:
        if self.manager.has_screen('trajectories'):
            self.manager.remove_widget(self.manager.get_screen('trajectories'))

        # create & add the new screen
        spec = TrajectoryScreen(
            name= 'trajectories',
            setup= self.setup,
            sample_name= sample_name,
            filter_id= self.setup.filter_id,
            n_frames = n_frames,
        )
        self.manager.add_widget(spec)
        self.manager.current = 'trajectories'
    

    def manage_ROI_type(self, *_):
        grid = GridLayout(cols=1, spacing=10, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        btn_hardware = Button(text='Hardware ROI', size_hint_y=None, height=30)
        btn_hardware.bind(on_press=lambda *_: self.set_ROI_hardware())
        grid.add_widget(btn_hardware)

        btn_software = Button(text='Analysis ROI', size_hint_y=None, height=30)
        btn_software.bind(on_press=lambda *_: self.set_ROI_analysis())
        grid.add_widget(btn_software)

        popup = Popup(title='Select ROI type', content=grid, size_hint=(0.3, 0.3))
        popup.open()

    def manage_ROI(self, *_):
    # If it already exists, drop the old screen
        if self.manager.has_screen('roi_analysis'):
            self.manager.remove_widget(
                self.manager.get_screen('roi_analysis')
            )
        # Push our new ROI‐drawing screen
        screen = ROI_selection_screen(
            name='roi_analysis',
            setup=self.setup
        )
        self.manager.add_widget(screen)
        self.manager.current = 'roi_analysis'

    def print_power_label(self, *_):
        power = self.setup.get_power()
        self.label_power.text = f"P: {power * 1e6:.2f} uW"
        
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

        self.label_shutter_status.text = f"Shutter: {'Open' if shutter_state else 'Closed'}"
        self.icon_shutter_status.text = '🟢' if shutter_state else '🚫'
        self.print_power_label()

    def manage_live_cam(self, *_):
        threading.Thread(target=self.setup.live_cam, daemon=True).start()

### ========== Spectrum Screen ==========

class SpectrumScreen(Screen):
    def __init__(self, setup, sample_name, **kwargs):
        super().__init__(**kwargs)
        self.setup       = setup
        self.sample_name = sample_name
        self.save_path = check_path_save(IMAGE_SET_SAVE_LOCATION, self.sample_name, filters=None)
        
        self.abort = False
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

        self.button_grid = GridLayout(cols=2, size_hint=(1, None), height=100)
        self._init_buttons()
        root.add_widget(self.button_grid)

        self.add_widget(root)

        # storage for the dynamic data
        self.processed_filters = []
        self.processed_sums    = []

        # 2) Launch the hardware loop in a background thread
        threading.Thread(target=self._acquire_loop, daemon=True).start()

    def _init_buttons(self, *_):
        # Continue button, initially disabled:
    
        self.continue_btn = Button(text="Continue ✔️", font_name='EmojiFont',
            size_hint=(1, None), height=50, disabled=True)
        # When pressed, switch back to main screen:
        self.continue_btn.bind(on_press=lambda *_: setattr(self.manager, 'current', 'main'))
        
        self.cancel_btn = Button(text="Cancel ❌", font_name='EmojiFont',
                size_hint=(1, None), height=50, disabled=False)
        # When pressed, switch back to main screen:
        self.cancel_btn.bind(on_press=lambda *_: self.cancel_spectrum())

        self.btn_save_plot = Button(text="Save Figure 💾📉", font_name='EmojiFont',
                                    size_hint=(1, None), height=50, disabled=True)
        self.btn_save_plot.bind(on_press=lambda *_: self.save_plot())

        self.btn_save_images = Button(text="Save Images 💾📸", font_name='EmojiFont',
                                    size_hint=(1, None), height=50, disabled=True)
        self.btn_save_images.bind(on_press=lambda *_: self.save_images())
        
        # Add buttons to the grid layout
        self.button_grid.add_widget(self.continue_btn)
        self.button_grid.add_widget(self.cancel_btn)
        self.button_grid.add_widget(self.btn_save_plot)
        self.button_grid.add_widget(self.btn_save_images)
    
    def _acquire_loop(self):
        # Loop over filters 1→12
        self.images = []
        self.daq_times = []
        powers = []
        print("Starting spectrum acquisition...")
        print("Current ROI: ", self.setup.roi)
        for fid in range(12, 0, -1):
            if self.abort:
                print("Spectrum acquisition aborted.")
                break

            # set filter, snap image
            self.setup.wheel.set_filter(fid)
            self.setup.open_shutter()
            power_i = self.setup.get_power() * 1e6  # in uW
            powers.append(power_i)
            img = self.setup.cam.snap(timeout=15)
            t = time.strftime('_%H-%M-%S', time.localtime())
            self.daq_times.append(t)
            self.setup.close_shutter()

            self.images.append(img)
            imroi = img[self.setup.roi[0]:self.setup.roi[1], self.setup.roi[2]:self.setup.roi[3]]
            # compute sum of pixels
            total = imroi.sum()

            # schedule a UI update
            Clock.schedule_once(lambda dt, f=fid, s=total: self._update_plot(f, s))

        self.avg_power = sum(powers) / len(powers)
        Clock.schedule_once(lambda dt: setattr(self.continue_btn, 'disabled', False))
        self.btn_save_plot.disabled = False
        self.btn_save_images.disabled = False

    def save_plot(self, *_):
        """Save the figure to the specified path."""        
        fname = self.save_path + f"\\{self.sample_name}_spectrum.png"
        self.fig.savefig(fname, dpi=300, bbox_inches='tight')
        print(f"Figure saved to: {self.save_path}")
        self.btn_save_plot.text = f"Figure saved! 💾📉✅️"
        # Save the data to a CSV file
        pd.DataFrame([self.processed_filters, self.processed_sums]).T.to_csv(fname.replace('.png', '_data.csv'), index=False, header=['Filter ID', 'Sum of pixels'])

        write_settings(self.save_path, self.setup.settings)
        self.btn_save_plot.disabled = True

    def save_images(self, *_):
        self.setup.settings.loc['POWER(uW)', 'value'] = round(self.avg_power, 2)
        write_settings(self.save_path, self.setup.settings)
        filter_ids = range(12, 0, -1)
        for fid, img, time_daq in zip(filter_ids, self.images, self.daq_times):
            file_savepath = self.save_path + '\\' + str(FILTERS[fid]) + time_daq + '.tif'
            io.imsave(file_savepath, img)
        print(f"Images saved to: {self.save_path}")
        self.btn_save_images.text = f"Images saved! 💾📸✅️"
        self.btn_save_images.disabled = True

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

    def cancel_spectrum(self, *_): 
        # remove the screen and go back to main
        self.abort = True
        self.setup.cam._wait_for_next_frame()
        # self.setup.cam.close()
        self.setup.close_shutter()
        self.setup.move_filter(1)
        Clock.schedule_once(lambda dt: setattr(self.continue_btn, 'disabled', False))
        self.manager.current = 'main'
        self.manager.remove_widget(self.manager.get_screen('spectrum'))

### ========== Single image Screen ==========

class ImageScreen(Screen):
    def __init__(self, setup, sample_name, **kwargs):
        super().__init__(**kwargs)
        self.setup       = setup
        self.sample_name = sample_name

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

        # Check if the camera is open before taking an image
        if self.setup.cam.is_opened():
            self.setup.open_shutter()
            img = self.setup.cam.snap(timeout=15)
            self.setup.close_shutter()
        else:
            print("Camera is not open. Please open the camera first.")
            self.setup.cam.open()

        self.display_image(img)

    def display_image(self, img):
        # Display the image using matplotlib

        if self.setup.roi is not None:
            # Draw the ROI on the image
            draw_roi(self.ax, self.setup.roi)

        cutoff = get_cutoff(img, threshold=8)
        axob = self.ax.imshow(img, clim = (100, cutoff))
        plt.colorbar(axob, ax=self.ax)
        self.ax.set_title(f"Image for {self.sample_name}")
        self.mpl_canvas.draw()
        
    def save_image(self, img):
        # Save the image using the save_tif_set function
        power = self.setup.get_power()
        rootpath = IMAGE_SINGLE_SAVE_LOCATION
        save_path = check_path_save(rootpath, self.sample_name, filters=None)
        self.setup.settings.loc['POWER(uW)', 'value'] = round(power, 2)
        write_settings(save_path, self.setup.settings)
        
        single_tif_save(img, save_path, self.sample_name, power, self.setup.filter_id)
        self.save_btn.text = f"Image saved! 💾✅️"
        print(f"Image saved to: {save_path}")


class TrajectoryScreen(Screen):
    def __init__(self, setup, sample_name, filter_id, n_frames=10, **kwargs):
        super().__init__(**kwargs)
        self.setup       = setup
        self.sample_name = sample_name
        self.filter_id   = filter_id
        self.n_frames    = n_frames

        # Estimate total time
        self.total_time = self.setup.texp * self.n_frames    # seconds
        self.step_time  = self.total_time / 100               # update every 1%
        self.save_path = check_path_save(IMAGE_TIMERUN_SAVE_LOCATION, self.sample_name, filters=self.filter_id)
        self.measurement_nr = self.save_path.split('\\')[-1]
        # container
        root = BoxLayout(orientation='vertical', spacing=10, padding=10)

        # 1) Loading labels and progress bar
        self._init_labels(root)

        # 2) Matplotlib canvas, hidden until data ready
        self.fig, self.ax = plt.subplots(1, 2, figsize=(8, 4), dpi=100)
        self.mpl_canvas   = FigureCanvasKivyAgg(self.fig)
        self.mpl_canvas.opacity = 0.0
        root.add_widget(self.mpl_canvas)

        # 3) Buttons, disabled until data ready
        self.button_grid = GridLayout(rows=3, size_hint=(1, None), height=150)
        self._init_buttons()
        root.add_widget(self.button_grid)    
        self.add_widget(root)

        # 4) Kick off two tasks:
        #  A) time‐based progress updater every step_time seconds
        self._time_event = Clock.schedule_interval(self._update_time_progress, self.step_time)

        #  B) background thread to do the actual grab
        threading.Thread(target=self._acquire_loop, daemon=True).start()

    def _init_labels(self, root: BoxLayout):
        # ensure vertical stacking
        root.orientation = 'vertical'
        root.spacing     = dp(10)
        root.padding     = dp(10)

        # common style for labels
        label_kwargs = dict(font_name='EmojiFont', size_hint=(1, None),height=dp(40),)
        
        self.measurement_label = Label(text=f"Measurement #{self.measurement_nr}: {self.sample_name} · filter: {self.filter_id} · exposure: {self.setup.texp:.2f} s",
            **label_kwargs)
        self.end_label         = Label(text=f"Total {self.n_frames} frames · est. time: {self.total_time:.2f} s",
            **label_kwargs)
        self.loading_label     = Label(text="Loading frames… 🔄",
            **label_kwargs)
        self.progress          = ProgressBar(max=1.0, value=0, size_hint=(1, None), height=200)

        self.status_label = Label(text=f"{self.progress.value:.0%}",
            **label_kwargs)
        root.add_widget(self.measurement_label)
        root.add_widget(self.end_label)
        root.add_widget(self.loading_label)
        root.add_widget(self.status_label)
        root.add_widget(self.progress)

    def _init_buttons(self,):
        # Continue button, initially disabled:
        self.continue_btn = Button(text="Continue ✔️", font_name='EmojiFont',
            size_hint=(1, None), height=50, disabled=True)
        # When pressed, switch back to main screen:
        self.continue_btn.bind(on_press=lambda *_: setattr(self.manager, 'current', 'main'))
        
        # Add buttons to the grid layout
        self.button_grid.add_widget(self.continue_btn)


        self.save_plot_btn = Button(text="Save Figure 💾📉", font_name='EmojiFont', size_hint=(1, None), height=40, disabled=True)
        self.save_plot_btn.bind(on_press=lambda *_: self.save_plot())
        self.button_grid.add_widget(self.save_plot_btn)
        
        self.save_img_btn = Button(text="Save Images 💾📸", font_name='EmojiFont', size_hint=(1, None), height=40, disabled=True)
        self.button_grid.add_widget(self.save_img_btn)

        

    def _update_time_progress(self, dt):
        """Advance progress by 1% each tick; stop when we reach 100%."""
        self.progress.value += 0.01
        self.acquisition_time = round(time.time() - self.start_time, 3)
        self.status_label.text = f"{self.progress.value:.0%}"
        self.end_label.text = f"Acquisition time: {self.acquisition_time:.2f} s, estimated time left: {self.total_time - self.acquisition_time:.2f} s"

        if self.progress.value >= 1.0:
            self.progress.value = 1.0
            Clock.unschedule(self._update_time_progress)

    def _acquire_loop(self):
        """Runs in a background thread, does the real camera work."""
        # ensure camera is ready
        self.start_time = time.time()
        if not self.setup.cam.is_opened():
            self.setup.cam.open()
        self.setup.open_shutter()

        frames = self.setup.cam.grab(self.n_frames)
        self.power = round(self.setup.get_power() * 1e6, 2)  # in uW
        self.setup.close_shutter()
        # once complete, schedule the “finish” on UI thread
        Clock.schedule_once(lambda dt, f=frames: self._finish_acquisition(f), 0)

    def _finish_acquisition(self, frames):
        # compute trajectory & time
        frames_roi = [f[self.setup.roi[0]:self.setup.roi[1], self.setup.roi[2]:self.setup.roi[3]] for f in frames]
        size_roi = frames_roi[0].shape[0] * frames_roi[0].shape[1]
        # compute the mean of pixels in the ROI for each frame
        self.trajectory = [f.sum() / size_roi for f in frames_roi]
        self.times      = [i * self.setup.texp for i in range(len(self.trajectory))]
        self.save_img_btn.bind(on_press=lambda *_: self.save_images(frames))

        # remove loading widgets
        self.loading_label.parent.remove_widget(self.loading_label)
        self.progress.parent.remove_widget(self.progress)
        self.status_label.parent.remove_widget(self.status_label)
        self.end_label.parent.remove_widget(self.end_label)

        # draw the trajectory
        self.ax[0].plot(self.times, self.trajectory, marker='o', linestyle='-')
        self.ax[0].set(xlabel='Time (s)', ylabel='Sum of pixels', title=f"Trajectory for {self.sample_name}, filter {self.filter_id}")

        cutoff = get_cutoff(frames[0], threshold=8)
        axob = self.ax[1].imshow(frames[0], clim = (100, cutoff))
    
        if self.setup.roi is not None:
            # Draw the ROI on the image
            draw_roi(self.ax[1], self.setup.roi)
        self.ax[1].set_title(f"Image and ROI")
        plt.colorbar(axob, ax=self.ax[1])
        
        self.mpl_canvas.draw()
        self.mpl_canvas.opacity = 1.0

        # enable buttons
        self.continue_btn.disabled   = False
        self.save_plot_btn.disabled  = False
        self.save_img_btn.disabled   = False

    def save_plot(self, *_):
        """Save the current figure to a file."""
        self.setup.settings.loc['POWER(uW)', 'value'] = round(self.power, 2)
        write_settings(self.save_path, self.setup.settings)
        fname = self.save_path + '/fluorescence_trajectory.png'
        self.fig.savefig(fname, dpi=300)
        # Save the data to a CSV file
        pd.DataFrame([self.times, self.trajectory]).T.to_csv(fname.replace('.png', '_data.csv'), index=False, header=['Time (s)', 'Sum of pixels'])

        self.save_plot_btn.text = f"Figure saved! Measurement nr: {self.measurement_nr} 💾📉✅️" 
        self.save_plot_btn.disabled = True
        print(f"Image saved to: {fname}")

    def save_images(self, frames):
        """Save the frames to a file."""
        self.setup.settings.loc['POWER(uW)', 'value'] = round(self.power, 2)
        write_settings(self.save_path, self.setup.settings)
        dir_path = self.save_path + '\\' + FILTERS[self.filter_id] + '_' + '_P_' + str(self.power) 
        for n, frame in enumerate(frames):
            path_file = dir_path + 'uW_frame_' + str(n).zfill(3) +'.tif'
            io.imsave(path_file, frame)
        
        self.save_img_btn.text = f"Images saved! Measurement nr: {self.measurement_nr} 💾📸✅️" 
        self.save_img_btn.disabled = True
        

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
