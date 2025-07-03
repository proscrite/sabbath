from functools import wraps
from kivy.uix.popup import Popup
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

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
