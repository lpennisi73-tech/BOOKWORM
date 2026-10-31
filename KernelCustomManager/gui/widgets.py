"""
Widgets GTK4 réutilisables par les onglets
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gio, GObject, Gtk, Pango


class Row(GObject.Object):
    """Ligne d'une SimpleList : valeurs affichées + donnée associée libre"""

    def __init__(self, values, data=None):
        super().__init__()
        self.values = ["" if v is None else str(v) for v in values]
        self.data = data

    def __getitem__(self, index):
        return self.values[index]


class SimpleList(Gtk.ScrolledWindow):
    """
    Tableau de texte (Gtk.ColumnView + Gio.ListStore), remplace TreeView + ListStore.

        lst = SimpleList(["Paquet", "Taille"], expand=[0])
        lst.append(["linux-image…", "80 MB"], data=chemin)
        row = lst.selected()   # Row ou None ; row[0], row.data
    """

    def __init__(self, columns, expand=(), min_height=None, on_activate=None):
        super().__init__(vexpand=True, hexpand=True)
        if min_height:
            self.set_min_content_height(min_height)

        self.store = Gio.ListStore(item_type=Row)
        self.selection = Gtk.SingleSelection(model=self.store, autoselect=False, can_unselect=True)
        self.view = Gtk.ColumnView(model=self.selection, show_row_separators=True,
                                   reorderable=False)
        self.view.add_css_class("data-table")

        for index, title in enumerate(columns):
            factory = Gtk.SignalListItemFactory()
            factory.connect("setup", self._setup)
            factory.connect("bind", self._bind, index)
            column = Gtk.ColumnViewColumn(title=title, factory=factory, resizable=True,
                                          expand=index in expand)
            self.view.append_column(column)

        if on_activate:
            self.view.connect("activate", lambda view, position: on_activate(self.store.get_item(position)))

        self.set_child(self.view)

    @staticmethod
    def _setup(_factory, item):
        item.set_child(Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END,
                                 margin_start=4, margin_end=4))

    @staticmethod
    def _bind(_factory, item, index):
        row = item.get_item()
        label = item.get_child()
        label.set_text(row.values[index])
        label.set_tooltip_text(row.values[index] or None)

    def clear(self):
        self.store.remove_all()

    def append(self, values, data=None):
        self.store.append(Row(values, data))

    def set_rows(self, rows):
        """rows: itérable de listes de valeurs, ou de Row"""
        items = [r if isinstance(r, Row) else Row(r) for r in rows]
        self.store.splice(0, self.store.get_n_items(), items)

    def selected(self):
        return self.selection.get_selected_item()

    def __len__(self):
        return self.store.get_n_items()


def page_box(spacing=12, margin=12):
    """Conteneur vertical standard d'un onglet"""
    return Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing,
                   margin_top=margin, margin_bottom=margin,
                   margin_start=margin, margin_end=margin)


def section(title, child=None, spacing=8):
    """
    Bloc titré (remplace Gtk.Frame(label=...)). Retourne (widget, boîte intérieure).
    """
    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    if title:
        heading = Gtk.Label(label=title, xalign=0)
        heading.add_css_class("heading")
        outer.append(heading)
    inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing,
                    margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    card.add_css_class("card")
    card.append(inner)
    outer.append(card)
    if child is not None:
        inner.append(child)
    return outer, inner


def markup_label(markup="", wrap=True, selectable=False):
    label = Gtk.Label(xalign=0, wrap=wrap, selectable=selectable,
                      wrap_mode=Pango.WrapMode.WORD_CHAR)
    if markup:
        label.set_markup(markup)
    return label


def title_label(title, subtitle=None):
    """Titre d'onglet en gras + sous-titre atténué"""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    heading = Gtk.Label(label=title, xalign=0, wrap=True)
    heading.add_css_class("title-4")
    box.append(heading)
    if subtitle:
        sub = Gtk.Label(label=subtitle, xalign=0, wrap=True)
        sub.add_css_class("dim-label")
        box.append(sub)
    return box


def button_row(*buttons, homogeneous=False):
    box = Gtk.Box(spacing=6, homogeneous=homogeneous)
    for button in buttons:
        box.append(button)
    return box


def button(label, on_clicked, style=None, tooltip=None):
    btn = Gtk.Button(label=label)
    btn.connect("clicked", lambda _b: on_clicked())
    if style:
        btn.add_css_class(style)  # "suggested-action", "destructive-action", "flat"…
    if tooltip:
        btn.set_tooltip_text(tooltip)
    return btn


def labeled(label, widget, hexpand=True):
    """Ligne « Libellé : [widget] »"""
    box = Gtk.Box(spacing=8)
    box.append(Gtk.Label(label=label, xalign=0))
    widget.set_hexpand(hexpand)
    box.append(widget)
    return box


def entry(text="", placeholder="", password=False):
    if password:
        widget = Gtk.PasswordEntry(show_peek_icon=True)
        if placeholder:
            widget.set_property("placeholder-text", placeholder)
    else:
        widget = Gtk.Entry(text=text, placeholder_text=placeholder)
    return widget


def monospace_view():
    """Zone de texte en lecture seule (police à chasse fixe), dans un ScrolledWindow"""
    view = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR,
                        top_margin=6, bottom_margin=6, left_margin=6, right_margin=6)
    scrolled = Gtk.ScrolledWindow(vexpand=True, child=view)
    return scrolled, view


def clear_box(box):
    child = box.get_first_child()
    while child is not None:
        following = child.get_next_sibling()
        box.remove(child)
        child = following


def run_once_when_mapped(widget, callback):
    """Appelle callback() la première fois que widget devient visible (chargement différé)"""
    def on_map(w):
        w.disconnect(handler)
        callback()
    handler = widget.connect("map", on_map)


def inner_tabs(pages):
    """
    Onglets internes d'une page : pages = [(nom, titre, widget), …].
    Retourne (conteneur, Gtk.Stack).
    """
    stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, vexpand=True)
    for name, title, widget in pages:
        stack.add_titled(widget, name, title)
    switcher = Gtk.StackSwitcher(stack=stack, halign=Gtk.Align.CENTER)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    box.append(switcher)
    box.append(stack)
    return box, stack


def info_bar(*markups):
    """Bandeau d'informations système (remplace le Gtk.Frame en haut des onglets)"""
    bar = Gtk.Box(spacing=24, margin_top=6, margin_bottom=6, margin_start=12, margin_end=12)
    for markup in markups:
        label = Gtk.Label(xalign=0)
        label.set_markup(markup)
        bar.append(label)
    return bar
