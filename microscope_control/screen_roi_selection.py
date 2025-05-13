
from skimage import io
import numpy as np
import matplotlib.pyplot as plt
from kivy_garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button


def draw_roi(ax, roi):
    # Draw a rectangle on the image based on the ROI coordinates
    top_left = (roi[0], roi[1])
    width = roi[1] - roi[0]
    height = roi[2] - roi[1]
    dynamic_rect = plt.Rectangle(top_left, width, height, edgecolor='red',
                                    facecolor='none', linewidth=2)
    ax.add_patch(dynamic_rect)


class ROI_selection_screen(Screen):
    def __init__(self, setup, **kwargs):
        super().__init__(**kwargs)
        self.setup = setup
        self.setup.open_shutter()
        img = self.setup.cam.snap(timeout=15)
        self.setup.close_shutter()
        self.img = img


        # Initialize variables to manage the clicks and rectangle patch
        self.click_positions = []
        self.dynamic_rect = None  # This will hold the rectangle patch
        self.final_roi = None   # To store the finalized ROI coordinates
        
        # Build the UI
        root = BoxLayout(orientation='vertical')
        self.fig, self.ax = plt.subplots()
        self.ax.imshow(self.img)
        self.mpl_canvas  = FigureCanvasKivyAgg(self.fig)
        root.add_widget(self.mpl_canvas )

        # --- confirm button (disabled until ROI done) ---
        self.confirm_btn = Button(text="Confirm ROI", size_hint=(1, None), 
                                  height=50,disabled=True)
        self.confirm_btn.bind(on_press=self._on_confirm)
        root.add_widget(self.confirm_btn)

        self.add_widget(root)

        # Connect mouse events
        self.cid_click = self.fig.canvas.mpl_connect(
            'button_press_event', self._on_mouse_click
        )
        self.cid_move = self.fig.canvas.mpl_connect(
            'motion_notify_event', self._on_mouse_move
        )

    def _on_mouse_click(self, event):
        if event.xdata is None or event.ydata is None or event.button != 1:
            return
        x, y = int(event.xdata), int(event.ydata)

        if not self.click_positions:
            # first click: reset any existing rectangle
            if self.dynamic_rect:
                self.ax.patches.remove(self.dynamic_rect)
                self.dynamic_rect = None
                self.mpl_canvas .draw_idle()
            self.click_positions = [(x, y)]
        else:
            # second click: finalize
            self.click_positions.append((x, y))
            self._update_rectangle(event)
            # store as [x0, y0, x1, y1] for downstream code
            x0, y0 = self.click_positions[0]
            x1, y1 = self.click_positions[1]
            self.final_roi = [min(x0, x1), max(x0, x1), 
                              min(y0, y1), max(y0, y1)]
            self.confirm_btn.disabled = False
            # clear so user *could* draw again if they wanted
            self.click_positions = []

    def _on_mouse_move(self, event):
        if len(self.click_positions) == 1 and event.xdata is not None:
            self._update_rectangle(event)

    def _update_rectangle(self, event):
        x0, y0 = self.click_positions[0]
        x1, y1 = int(event.xdata), int(event.ydata)
        tl = (min(x0, x1), min(y0, y1))
        w, h = abs(x1 - x0), abs(y1 - y0)

        if self.dynamic_rect is None:
            self.dynamic_rect = plt.Rectangle(
                tl, w, h, edgecolor='red', facecolor='none', linewidth=2
            )
            self.ax.add_patch(self.dynamic_rect)
        else:
            self.dynamic_rect.set_xy(tl)
            self.dynamic_rect.set_width(w)
            self.dynamic_rect.set_height(h)

        self.mpl_canvas .draw_idle()

    def _on_confirm(self, _):
        # save ROI back into the setup and go home
        self.setup.roi = self.final_roi
        self.manager.current = 'main'
    