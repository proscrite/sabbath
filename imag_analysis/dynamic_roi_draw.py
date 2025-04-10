
from skimage import io
import numpy as np
import matplotlib.pyplot as plt

def run_roi_selector(image):
    # Initialize variables to manage the clicks and rectangle patch
    click_positions = []
    dynamic_rect = None  # This will hold the rectangle patch
    final_roi = None   # To store the finalized ROI coordinates
    dynamic_rect = None  # Holds the rectangle patch

    def update_rectangle(event):
        nonlocal dynamic_rect, click_positions
        if event.xdata is None or event.ydata is None:
            return

        # Calculate rectangle coordinates based on the first click and current mouse position
        x1, y1 = click_positions[0]
        x2, y2 = int(event.xdata), int(event.ydata)
        top_left = (min(x1, x2), min(y1, y2))
        width = abs(x2 - x1)
        height = abs(y2 - y1)

        # Create the rectangle patch on the first call; update it on subsequent calls
        if dynamic_rect is None:
            dynamic_rect = plt.Rectangle(top_left, width, height, edgecolor='red',
                                         facecolor='none', linewidth=2)
            ax.add_patch(dynamic_rect)
        else:
            dynamic_rect.set_xy(top_left)
            dynamic_rect.set_width(width)
    dynamic_rect = None  # Holds the rectangle patch

    def update_rectangle(event):
        nonlocal dynamic_rect, click_positions
        if event.xdata is None or event.ydata is None:
            return

        # Calculate rectangle coordinates based on the first click and current mouse position
        x1, y1 = click_positions[0]
        x2, y2 = int(event.xdata), int(event.ydata)
        top_left = (min(x1, x2), min(y1, y2))
        width = abs(x2 - x1)
        height = abs(y2 - y1)

        # Create the rectangle patch on the first call; update it on subsequent calls
        if dynamic_rect is None:
            dynamic_rect = plt.Rectangle(top_left, width, height, edgecolor='red',
                                         facecolor='none', linewidth=2)
            ax.add_patch(dynamic_rect)
        else:
            dynamic_rect.set_xy(top_left)
            dynamic_rect.set_width(width)
            dynamic_rect.set_height(height)
        fig.canvas.draw_idle()

    def on_mouse_click(event):
        nonlocal click_positions, dynamic_rect, final_roi
        # Only handle events within the image
        if event.xdata is None or event.ydata is None:
            return

        if event.button == 1:  # Left mouse button
            if len(click_positions) == 0:
                # Start a new ROI selection
                # Optionally, clear the previous rectangle if starting a new selection
                if dynamic_rect is not None:
                    dynamic_rect.remove()
                    dynamic_rect = None
                    fig.canvas.draw_idle()
                click_positions.append((int(event.xdata), int(event.ydata)))
                print(f"First click at: {click_positions[-1]}")
            elif len(click_positions) == 1:
                # Complete the ROI selection
                click_positions.append((int(event.xdata), int(event.ydata)))
                print(f"Second click at: {click_positions[-1]}")
                update_rectangle(event)
                # Store the finalized ROI
                final_roi = click_positions.copy()
                print("ROI finalized:", final_roi)
                # Reset click_positions to allow new selections if desired
                click_positions.clear()

    def on_mouse_move(event):
        # Update the rectangle dynamically after the first click
        if len(click_positions) == 1:
            update_rectangle(event)

    # Set up the matplotlib figure and axis
    fig, ax = plt.subplots()
    ax.imshow(image)

    # Connect event handlers
    fig.canvas.mpl_connect('button_press_event', on_mouse_click)
    fig.canvas.mpl_connect('motion_notify_event', on_mouse_move)

    plt.show()  # This will block until the window is closed
    roi_selected = np.array(final_roi).ravel()
    final_roi_list = [ roi_selected[0], roi_selected[1], roi_selected[3], roi_selected[2] ]  
    return final_roi_list

# If run as a script, execute the ROI selector and print the result.
if __name__ == '__main__':
    roi = run_roi_selector()
    print("Returned ROI:", roi)