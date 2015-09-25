"""
A simple terminal viewer for JSON files. It supports folding
and traversal. Currently does not support arbitrary JSON
but should handle dsconfig files.

Useful additions might include search, filtering and possibly
editing features.
"""

import urwid
from urwidtrees.tree import Tree
from urwidtrees.widgets import TreeBox
from urwidtrees.decoration import CollapsibleIndentedTree


class FocusableText(urwid.WidgetWrap):

    def __init__(self, path, data):
        txt = path[-1]
        child = get_path(path, data)
        if isinstance(txt, int):  # we're in a list
            # TODO: support containers inside lists
            a = urwid.Text(str(txt)+":")
            b = urwid.Text(str(child))
            t = urwid.Columns([("pack", a), b], dividechars=2)
        else:
            if isinstance(child, (dict, list)):
                t = urwid.Text(str(txt))
            else:
                t = urwid.Text("%s:  %s" % (txt, child))
        w = urwid.AttrMap(t, 'body', 'focus')
        urwid.WidgetWrap.__init__(self, w)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


def get_path(path, dictlike):
    for step in path:
        dictlike = dictlike[step]
    return dictlike


def del_path(path, dictlike):
    for step in path[:-1]:
        dictlike = dictlike[step]
    del dictlike[path[-1]]


class MyTree(Tree):

    def __init__(self, data):
        self.data = data
        self.root = tuple(data.keys())

    def __getitem__(self, pos):
        return FocusableText(pos, self.data)

    # helpers

    def _get_children(self, path):
        node = get_path(path, self.data)
        if node:
            if isinstance(node, dict):
                children = node.keys()
                return [path + (child,) for child in sorted(children)]
            elif isinstance(node, list):
                children = range(len(node))
                return [path + (child,) for child in children]
        return []

    def _get_siblings(self, path):
        parent = self.parent_position(path)
        if parent is not None:
            return self._get_children(parent)
        return [path]

    # UrwidTrees Tree API

    def parent_position(self, path):
        if path != self.root:
            return path[:-1]

    def first_child_position(self, path):
        try:
            children = self._get_children(path)
        except KeyError:
            return path
        if children:
            return children[0]

    def last_child_position(self, path):
        try:
            children = self._get_children(path)
        except KeyError:
            return path
        if children:
            return children[-1]

    def next_sibling_position(self, path):
        siblings = self._get_siblings(path)
        if path in siblings:
            myindex = siblings.index(path)
            if myindex + 1 < len(siblings):  # path is not the last entry
                return siblings[myindex + 1]

    def prev_sibling_position(self, path):
        siblings = self._get_siblings(path)
        if path in siblings:
            myindex = siblings.index(path)
            if myindex > 0:  # path is not the first entry
                return siblings[myindex - 1]


class MyTreeBox(TreeBox):

    def keypress(self, size, key):
        "Spicing up the keybindings!"
        # if key == "delete":
        #     _, path = self.get_focus()
        #     self.set_focus(path[:-1])
        #     del_path(path, treedata)
        #     self.refresh()
        if key == "enter":
            w, pos = self._walker.get_focus()
            if self._tree.is_collapsed(pos):
                self.expand_focussed()
            else:
                self.collapse_focussed()
        elif key == "right":
            self.expand_focussed()
            self.focus_first_child()
        elif key in ("q", "esc"):
            raise urwid.ExitMainLoop()
        else:
            return TreeBox.keypress(self, size, key)


palette = [
    ('focus', 'light gray', 'dark blue', 'standout'),
    ('bars', 'dark blue', 'light gray', ''),
    ('arrowtip', 'light blue', 'light gray', ''),
    ('connectors', 'light red', 'light gray', ''),
]


if __name__ == "__main__":

    import json
    import signal
    import sys

    # make ctrl+C exit properly, without breaking the terminal
    def exit_handler(signum, frame):
        raise urwid.ExitMainLoop()
    signal.signal(signal.SIGINT, exit_handler)

    # redirecting stdin breaks things. This was supposed to help
    # but it does not. Fixme!
    old_stdin = sys.stdin
    sys.stdin = open('/dev/tty')
    screen = urwid.raw_display.Screen()

    sys.stdin = old_stdin
    if len(sys.argv) == 2:
        with open(sys.argv[1]) as f:
            treedata = {sys.argv[1]: json.load(f)}
    else:
        # # try to read from stdin
        # treedata = {"stdin": json.load(sys.stdin)}
        sys.exit("You must give a JSON file as input")

    tree = CollapsibleIndentedTree(MyTree(treedata), indent=2,
                                   is_collapsed=lambda path: len(path) > 1,
                                   arrow_tip_char=None,
                                   icon_frame_left_char=None,
                                   icon_frame_right_char=None,
                                   icon_collapsed_char="+",
                                   icon_expanded_char="-")
    box = MyTreeBox(tree)
    loop = urwid.MainLoop(box, palette, screen=screen)
    loop.run()
