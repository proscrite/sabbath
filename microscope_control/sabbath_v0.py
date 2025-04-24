import kivy
from .main import Setup
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.checkbox import CheckBox
from functools import partial
import time
from microscope_control.Constants import *
# from microscope_control.utils import *

class Sabbath(App):
    def build(self):
        self.setup = Setup()
        self.setup.init_settings()
        self.setup.open_all_devices()
        # Main layout
        self.root_layout = FloatLayout()
        # Status labels layout
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
        self.add_button('Print Power', self.print_power_label)
        self.add_button('Toggle Shutter', self.manage_toggle_shutter)
        self.add_button('Settings', self.show_settings_menu)
        
        self.root_layout.add_widget(self.button_layout)
        
        # Return the main layout
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

    def manage_spectra(self, *_):
        layout = GridLayout(rows=2, padding=10, spacing=10)
        side_layout = GridLayout(cols=1, padding=10, spacing=10)
        label_status_sample = Label(text=f"Current sample: {getattr(self.setup, 'filter_id', '?')}", font_size=18)

        sample_input = TextInput(hint_text="Or enter Filter ID", multiline=False)
        popup = Popup(title='Select sample ID', content=layout, size_hint=(0.8, 0.8))

        grid = GridLayout(cols=4, spacing=10, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        # Shared callback function
        def set_sample(value_or_widget, popup, label, *_):
            try:            
                if isinstance(value_or_widget, TextInput):
                    sample_id = int(value_or_widget.text)
                    value = SAMPLES[sample_id]
                    
                else:
                    value = SAMPLES[value_or_widget]

                self.label_sample_status.text = f"Sample: {value}"
                label.text = f"Setting sample... ({value})"
                # self.setup.move_filter(value)
                popup.dismiss()
            except Exception as e:
                print(f"Invalid filter value: {e}")
                if isinstance(value, Button):
                    value.text = "Invalid"
                else:
                    sample_input.text = "Invalid input"

        # Add filter buttons dynamically
        for fid, name in SAMPLES.items():
            btn = Button(text=str(fid), size_hint_y=None, size_hint_x = 0.2, height=30)
            # Bind a unique partial per button
            btn.bind(on_press=partial(set_sample, fid, popup, label_status_sample))
            grid.add_widget(btn)
            filter_center = name.split('_')[0].replace('Center-', '')
            grid.add_widget(Label(text=str(filter_center), size_hint_y=None, height=30))

        # Handle text input + Enter
        sample_input.bind(on_text_validate=partial(set_sample, sample_input, popup, label_status_sample))

        layout.add_widget(side_layout)
        layout.add_widget(grid)

        side_layout.add_widget(label_status_sample)
        side_layout.add_widget(sample_input)

        popup.open()
 
    def print_power_label(self, *_):
        power = self.setup.print_power()
        if hasattr(self, 'power_label'):
            self.power_label.text = f"P: {power * 1e6:.2f} μW"
        else:
            self.status_layout.add_widget(self.power_label)

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

    def manage_zpos(self, *_):
        # Create a popup for Z position management
        zpos = self.setup.read_zpos()
        layout = GridLayout(cols=2, padding=10, spacing=10)
        side_layout = GridLayout(cols=1, padding=10, spacing=10)
        label_status_z = Label(text=f"Current Z Position: {zpos}", font_size=18)

        zpos_input = TextInput(hint_text="Enter Z Position", multiline=False)
        zpos_button = Button(text="Set Z Position")
        popup = Popup(title='Set Z Position', content=layout, size_hint=(0.5, 0.5))

        def call_move_zpos_with_input(textinput, popup, label, *_):
            try:
                value = float(textinput.text)
                label.text += '\nMoving Z Position...'
                self.setup.move_zpos(value)
                self.label_status_z.text = f"Z Position: {self.setup.read_zpos()}"
                popup.dismiss()
            except ValueError:
                textinput.text = "Invalid input"

        handler = partial(call_move_zpos_with_input, zpos_input, popup, label_status_z)
        zpos_input.bind(on_text_validate=handler)
        zpos_button.bind(on_press=handler)

        layout.add_widget(zpos_input)
        side_layout.add_widget(label_status_z)
        side_layout.add_widget(zpos_button)
        layout.add_widget(side_layout)

        popup.open()

    def manage_exposure(self, *_):
        # Create a popup for exposure management
        layout = GridLayout(cols=2, padding=10, spacing=10)
        side_layout = GridLayout(cols=1, padding=10, spacing=10)
        label_status_exposure = Label(text=f"Current Exposure: {self.setup.texp}", font_size=18)

        exposure_input = TextInput(hint_text="Enter Exposure Time", multiline=False)
        exposure_button = Button(text="Set Exposure Time")
        popup = Popup(title='Set Exposure Time', content=layout, size_hint=(0.5, 0.5))

        def call_set_exposure_with_input(textinput, popup, label, *_):
            try:
                value = float(textinput.text)
                label.text += '\nSetting Exposure...'
                self.setup.set_exposure(value)
                self.label_exposure_status.text = f"Exposure: {value:.2f} s"
                popup.dismiss()
            except ValueError:
                textinput.text = "Invalid input"

        handler = partial(call_set_exposure_with_input, exposure_input, popup, label_status_exposure)
        exposure_input.bind(on_text_validate=handler)
        exposure_button.bind(on_press=handler)

        layout.add_widget(exposure_input)
        side_layout.add_widget(label_status_exposure)
        side_layout.add_widget(exposure_button)
        layout.add_widget(side_layout)

        popup.open()

    def choose_filter(self, *_):
        layout = GridLayout(cols=2, padding=10, spacing=10)
        side_layout = GridLayout(cols=1, padding=10, spacing=10)
        label_status_filter = Label(text=f"Current Filter: {getattr(self.setup, 'filter_id', '?')}", font_size=18)

        filter_input = TextInput(hint_text="Or enter Filter ID", multiline=False)
        popup = Popup(title='Set Filter ID', content=layout, size_hint=(0.8, 0.8))

        grid = GridLayout(cols=4, spacing=10, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        # Shared callback function
        def set_filter(value_or_widget, popup, label, *_):
            try:            
                if isinstance(value_or_widget, TextInput):
                    value = int(value_or_widget.text)
                else:
                    value = int(value_or_widget)

                assert value in range(1, 13)
                label.text = f"Setting Filter... ({value})"
                print(f"Setting filter to {value}")
                self.setup.move_filter(value)
                self.label_filter_status.text = f"Filter: {value}"
                popup.dismiss()
            except Exception as e:
                print(f"Invalid filter value: {e}")
                if isinstance(value, Button):
                    value.text = "Invalid"
                else:
                    filter_input.text = "Invalid input"

        # Add filter buttons dynamically
        for fid, name in FILTERS.items():
            btn = Button(text=str(fid), size_hint_y=None, height=30)
            # Bind a unique partial per button
            btn.bind(on_press=partial(set_filter, fid, popup, label_status_filter))
            grid.add_widget(btn)
            filter_center = name.split('_')[0].replace('Center-', '')
            grid.add_widget(Label(text=str(filter_center), size_hint_y=None, height=30))

        # Handle text input + Enter
        filter_input.bind(on_text_validate=partial(set_filter, filter_input, popup, label_status_filter))

        layout.add_widget(side_layout)
        layout.add_widget(grid)

        side_layout.add_widget(label_status_filter)
        side_layout.add_widget(filter_input)

        popup.open()

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

if __name__ == '__main__':
    Sabbath().run()
