from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.widget import Widget

from microscope_control.button_decorators import PopupMixin, text_popup, combo_popup
from microscope_control.main import Setup

from functools import partial

class PowerManagement(Screen, PopupMixin):
    """Mockup power management screen for prototyping UI without hardware."""
    def __init__(self, setup, **kwargs):
        super().__init__(**kwargs)
        self.setup = setup
        root = BoxLayout(orientation='vertical')
        root.add_widget(Label(text="Power Management", font_size=24, size_hint_y=None, height=50))
        root.add_widget(Widget(size_hint_y=1))      # Spacer to push content down

        layout = GridLayout(cols=2, spacing=10, padding=10, size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))

        self.attenuation = 100.0
        self.correction_factor = 4.0
        self.position_max_power = 0.0

        self.read_power = round(setup.get_raw_power() * 1e6, 2)
        self.true_power = round(setup.get_power() * 1e6, 2)

        self._add_buttons(layout)

        root.add_widget(layout)
        root.add_widget(Widget(size_hint_y=1))      # Spacer to push content down
        self.add_widget(root)

    def on_enter(self, *args):
        """Called when the screen is entered. Initialize power readings and update labels."""
        self.setup.open_shutter()
        self.update_power_labels()

    def _add_buttons(self, layout):

        self.read_power_label = Label(text=f"🔎⚡️ Read Power: {self.read_power} uW", font_name='EmojiFont', font_size = 25)
        self.true_power_label = Label(text=f"👌⚡️ True Power: {self.true_power} uW", font_name='EmojiFont', font_size = 25)

        self.icon_shutter_status = Label(text="🟢", font_size=25, font_name='EmojiFont')
        self.label_shutter_status = Label(text=f"Shutter: Open ", font_size=25, font_name='EmojiFont')
        
        layout.add_widget(self.read_power_label)
        layout.add_widget(self.icon_shutter_status)
        layout.add_widget(Widget(size_hint_y=None, height=20))  # Spacer for layout balance
        layout.add_widget(Widget(size_hint_y=None, height=20))  # Spacer for layout balance

        layout.add_widget(self.true_power_label)
        layout.add_widget(self.label_shutter_status)

        layout.add_widget(Widget(size_hint_y=None, height=20))  # Spacer for layout balance
        layout.add_widget(Widget(size_hint_y=None, height=20))  # Spacer for layout balance


        self.button_correction_factor = Button(text=f"✍️ Correction factor: {self.setup.power_correction_factor}", font_name='EmojiFont', size_hint=(1, None), height=50)
        self.button_correction_factor.bind(on_press=self.set_correction_factor)
        layout.add_widget(self.button_correction_factor)

        self.button_attenuation = Button(text=f"🔈 Attenuation: {self.attenuation} %", font_name='EmojiFont', size_hint=(1, None), height=50)
        self.button_attenuation.bind(on_press=self.set_attenuation)
        layout.add_widget(self.button_attenuation)

        self.button_max_power = Button(text=f"🔊🔋 Calibrate maximum Power", font_name='EmojiFont', size_hint=(1, None), height=50)
        self.button_max_power.bind(on_press=self.set_max_power)
        layout.add_widget(self.button_max_power)

        self.button_position_max = Button(text=f"📌 Position Max Power: {self.position_max_power}", font_name='EmojiFont', size_hint=(1, None), height=50)
        layout.add_widget(self.button_position_max)

        self.button_shutter = Button(text="🔒 Toggle Shutter", font_name='EmojiFont', size_hint=(1, None), height=50, 
            on_release=lambda x: self.manage_toggle_shutter())
        layout.add_widget(self.button_shutter)

        self.button_refresh = Button(text='Refresh Power reading 📟🔋', font_name='EmojiFont', size_hint=(1, None), height=50,
            on_release=self.update_power_labels)
        layout.add_widget(self.button_refresh)

        layout.add_widget(Button(text = "🔙 Go Back", size_hint=(1, None), height=50,
            on_release=self.go_back, font_name='EmojiFont'))

    @text_popup(
        title="Set power correction factor",
        get_current=lambda self: f"✍️ Current Correction Factor: {self.button_correction_factor.text}",
        hint="Correction factor (e.g. 4.0)",
        validate=float,
        on_success=lambda self, t: (
            setattr(self.setup, 'power_correction_factor', t),
            setattr(self.button_correction_factor, 'text', f"✍️ Correction Factor: {t:.2f}"),
            self.update_power_labels()
        )
    )
    def set_correction_factor(self): 
        pass

    @combo_popup(
        title="Choose attenuation",
        get_current=lambda self: f"{self.button_attenuation.text}",
        hint="Attenuation factor (e.g. 4.0).",
        validate=float,
        choices=[(1, '1'), (10, '10'), (25, '25'), (50, '50'), (100, '100')],
        on_success=lambda self, val: (
            print(f"Attenuation set to: {val}"),
            self.setup.attenuate_power(float(val)),
            setattr(self.button_attenuation, 'text', f"🔈 Attenuation: {val} %"),
        )
    )
    def set_attenuation(self, *_):
        pass

    def set_max_power(self, *_):
        # self.setup.set_max_power()
        print("Setting max power...")
        self.setup.set_maximum_power()
        self.position_max_power = self.setup.position_max
        self.update_power_labels()

    def update_power_labels(self, instance=None):
        """Update the power labels with the current read and true power values."""
        # Update the power labels based on the current correction factor
        self.read_power = round(self.setup.get_raw_power() * 1e6, 2)  # Convert to microWatts
        self.true_power = round(self.setup.get_power() * 1e6, 2)  # Convert to microWatts
        self.read_power_label.text = f"🔎⚡️ Read Power: {self.read_power} uW"
        self.true_power_label.text = f"👌⚡️ True Power: {self.true_power:.2f} uW"

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
        self.update_power_labels()

    def go_back(self, *_):
        # Close the popup and return to the main screen
        self.setup.close_shutter()
        self.manager.current = 'main'
        self.manager.remove_widget(self)