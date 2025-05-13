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
    """Autofocus using white light illumination."""
    def __init__(self, setup, **kwargs):
        super().__init__(**kwargs)
        self.setup = setup
        self.setup.close_shutter()
        
        root = BoxLayout(orientation='vertical')
        self.fig, self.ax = plt.subplots(1, 2, figsize=(10, 4), dpi=100, sharey=True)

        self.mlp_canvas = FigureCanvasKivyAgg(self.fig)
        self.mlp_canvas.opacity = 0.0
        root.add_widget(self.mlp_canvas)
        self.add_widget(root)

        self.continue_btn = Button(text="Continue ✔️", font_name='EmojiFont', size_hint=(1, None), height=40, disabled=True)
        self.continue_btn.bind(on_press=lambda *_: setattr(self.manager, 'current', 'main'))
        root.add_widget(self.continue_btn)

        self.init_popup()

    def init_popup(self):
        
        popup_content = GridLayout(cols=2, rows=2)
        label = Label(text="Have you switched to white light illumination?")
        label2 = Label(text="" )
        button_confirm = Button(text="Yes", size_hint=(1, None), height=50)
        button_confirm.bind(on_press=self.perform_autofocus)
        button_cancel = Button(text="Cancel", size_hint=(1, None), height=50)
        button_cancel.bind(on_press=self.cancel_autofocus)

        popup_content.add_widget(label)
        popup_content.add_widget(label2)
        popup_content.add_widget(button_confirm)
        popup_content.add_widget(button_cancel)
        self.confirmation_popup = Popup(title="Confirmation: Autofocus using white light illumination",
                                content=popup_content,
                                size_hint=(0.8, 0.5),
                                auto_dismiss=False)
        self.confirmation_popup.open()

    def cancel_autofocus(self, instance):
        """Cancel autofocus, dismiss popup and return to main screen"""
        self.confirmation_popup.dismiss()
        self.manager.current = 'main'
        self.manager.remove_widget(self.manager.get_screen('autofocus'))

    def perform_autofocus(self, *_):
        """Perform autofocus using white light illumination."""
        self.confirmation_popup.dismiss()
        self.call_autofocus_coarse()

    def call_autofocus_coarse(self, *_):
        self.setup.motor.move_to(14.0)  # move to the starting position
        self.setup.motor.wait_move()  
        # Perform coarse autofocus
        self.step1 = -0.1
        self.nsteps1 = 20
        self.zpos_coarse = []
        self.kurt_coarse = []
        self.mlp_canvas.opacity = 1.0

        threading.Thread(target=self._loop_autofocus, args=(self.nsteps1, self.step1), daemon=True).start()
                
        # self.ax[0].plot(zpos_coarse, kurt_coarse)
        # self.ax[0].set(title = "Coarse Autofocus Metric", xlabel = "Z Position (mm)", ylabel = "Kurtosis (arb. units)")
        # self.mlp_canvas.draw()
    """
        # Perform fine autofocus
        step2 = -0.01
        nsteps2 = 20
        zpos_fine, kurt_fine = self.loop_autofocus(nsteps=nsteps2, step_size=step2)

        best_kurt = np.argmax(kurt_fine)
        best_zpos = zpos_fine[best_kurt]
        print(f"Best position: {best_zpos} mm")
        self.setup.motor.move_to(best_zpos)  # move to the best position
        self.setup.motor.wait_move()
        
        # Plot fine autofocus metric
        self.ax[1].plot(zpos_fine, kurt_fine)
        self.ax[1].set(title = "Fine Autofocus Metric", xlabel = "Z Position (mm)", ylabel = "Kurtosis (arb. units)")
        self.fig.tight_layout()
        self.mlp_canvas.draw()

        """


    def _loop_autofocus(self, nsteps = 20, step_size = -0.01):
        """Autofocus using white light illumination."""
        
        kurt_array = []
        zpos = []
        self.setup.cam.set_exposure(0.02)
        img0 = self.setup.cam.snap(timeout=15.0)
        for i in range(nsteps):
            img = self.setup.cam.snap(timeout=15.0)
            img = img.astype("int16")
            img = img - img0
            z = round(self.setup.motor.get_position(), 3)
            zpos.append(z)
            print(f"Image {i} at {z} mm")
            # zstring = str(z).zfill(2)
            # io.imsave(path_save +  f"image_{str(i).zfill(2)}_{zstring}mm.tiff", img)
            # print(f"Image {i} taken at {self.setup.motor.get_position()} mm")
            kurt = kurtosis(img.flatten(), axis=None, fisher=True, bias=False)
            kurt_array.append(kurt)
            self.setup.motor.move_by(step_size)
            self.setup.motor.wait_move()  # wait for the move to finish
            
            # schedule a UI update
            Clock.schedule_once(lambda dt, z=z, k=kurt: self._update_plot(z, k))
        
        Clock.schedule_once(lambda dt: self._finish_autofocus_loop(), 0)

    def _update_plot(self, z, kurt):
        # collect
        self.zpos_coarse.append(z)
        self.kurt_coarse.append(kurt)

        # redraw
        if len(self.zpos_coarse) < self.nsteps1:
            self.ax[0].clear()
            self.ax[0].plot(self.zpos_coarse, self.kurt_coarse)
            self.ax[0].set(title="Autofocus Metric", xlabel="Z Position (mm)", ylabel="Kurtosis (arb. units)")
            self.mlp_canvas.draw()

    def _finish_autofocus_loop(self, *_):
        best_kurt_coarse = np.argmax(self.kurt_coarse)
        best_zcoarse = self.zpos_coarse[best_kurt_coarse]
        print(f"Coarse focus position: {best_zcoarse} mm")
        self.setup.motor.move_to(best_zcoarse)  # move to the best position
        self.setup.motor.wait_move()
        self.setup.motor.move_by(-self.step1) # move back one coarse step
        self.setup.motor.wait_move()
        self.continue_btn.disabled   = False

if __name__ == "__main__":
    autofocus_whitelight()