import numpy as np
from skimage import io
import threading

from scipy.stats import kurtosis
import matplotlib.pyplot as plt

from kivy.uix.screenmanager import Screen
from kivy.app import App
from kivy_garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.clock import Clock


class autofocus_whitelight(Screen):
    """Autofocus using white light illumination with coarse and fine passes."""
    def __init__(self, setup, **kwargs):
        super().__init__(**kwargs)
        self.setup = setup
        self.setup.cam.set_exposure(0.03)
        self.setup.close_shutter()
        self.abort = False

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
        content = GridLayout(cols=2, rows=2)
        content.add_widget(Label(text="Have you switched to white light illumination?"))
        content.add_widget(Label())
        btn_yes = Button(text="Yes", size_hint_y=None, height=50)
        btn_yes.bind(on_press=self._start_coarse)
        btn_no = Button(text="Cancel", size_hint_y=None, height=50)
        btn_no.bind(on_press=self.cancel_autofocus)
        content.add_widget(btn_yes)
        content.add_widget(btn_no)

        self.popup = Popup(
            title="Autofocus Confirmation",
            content=content,
            size_hint=(0.8, 0.5),
            auto_dismiss=False
        )
        self.popup.open()

    def cancel_autofocus(self, *_):
        """Abort any running autofocus and return to main screen."""
        self.abort = True
        self.setup.cam._wait_for_next_frame()
        self.setup.cam.set_exposure(self.setup.exposure)
        if hasattr(self, 'popup'):
            self.popup.dismiss()
        self.manager.current = 'main'
        self.manager.remove_widget(self.manager.get_screen('autofocus'))

    def _start_coarse(self, *_):
        self.popup.dismiss()
        self.setup.motor.move_to(14.0)  # move to the starting position
        self.setup.motor.wait_move()
        self.call_autofocus_pass(
            nsteps=20, step=-0.1,
            z_list_attr='zpos_coarse',
            metric_list_attr='kurt_coarse',
            ax=self.ax[0],
            title="Coarse Autofocus Metric"
        )

    def call_autofocus_fine(self, *_):
        """Triggered by Continue button after coarse pass."""
        # disable to prevent re-entry
        self.continue_btn.disabled = True
        # return to coarse best plane
        best = self.zpos_coarse[np.argmax(self.kurt_coarse)]
        self.setup.motor.move_to(best)
        self.setup.motor.wait_move()
        # step back one coarse step so fine scan straddles focus
        self.setup.motor.move_by(+0.1)
        self.setup.motor.wait_move()

        self.call_autofocus_pass(
            nsteps=20, step=-0.01,
            z_list_attr='zpos_fine',
            metric_list_attr='kurt_fine',
            ax=self.ax[1],
            title="Fine Autofocus Metric"
        )

    def call_autofocus_pass(self, nsteps, step, z_list_attr, metric_list_attr, ax, title):
        """Kick off a threaded autofocus pass (coarse or fine)."""
        setattr(self, z_list_attr, [])
        setattr(self, metric_list_attr, [])
        self.current_ax = ax
        setattr(self, 'nsteps', nsteps)
        setattr(self, 'step', step)

        # move to start of pass for coarse only
        if step == -0.1:
            self.setup.motor.move_to(14.0)
            self.setup.motor.wait_move()

        self.mlp_canvas.opacity = 1.0
        threading.Thread(
            target=self._loop_autofocus,
            args=(nsteps, step, z_list_attr, metric_list_attr, ax, title),
            daemon=True
        ).start()

    def _loop_autofocus(self, nsteps, step, z_attr, k_attr, ax, title):
        img0 = self.setup.cam.snap(timeout=15.0).astype('int16')
        for i in range(nsteps):
            if self.abort:
                break
            img = self.setup.cam.snap(timeout=15.0).astype('int16')
            img = img - img0
            z = round(self.setup.motor.get_position(), 3)
            k = kurtosis(img.flatten(), fisher=True, bias=False)
            print(f"Image {i} at {z} mm")

            getattr(self, z_attr).append(z)
            getattr(self, k_attr).append(k)
            # schedule UI update
            Clock.schedule_once(lambda dt, z=z, k=k: self._update_plot(z, k, ax, title))
            # move stage
            self.setup.motor.move_by(step)
            self.setup.motor.wait_move()

        # finalize
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
        self.setup.motor.move_to(best_z)
        self.setup.motor.wait_move()

        # if we've just finished fine, go back to main
        if z_attr == 'zpos_fine':
            self.continue_btn.text = 'Return to main menu'
            self.continue_btn.bind(on_press=self.cancel_autofocus)
            self.continue_btn.disabled = False
        else:
            # enable continue button for fine
            self.continue_btn.disabled = False

if __name__ == "__main__":
    autofocus_whitelight()