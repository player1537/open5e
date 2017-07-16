#!/usr/bin/env python3.6
"""

"""

from contextlib import contextmanager
import json
import os
from pathlib import Path

from docutils.frontend import OptionParser
from docutils.parsers.rst import Parser
from docutils.nodes import (
    GenericNodeVisitor, NodeVisitor, SkipChildren,
)
from docutils.utils import new_document


class DelegatingJSONEncoder(json.JSONEncoder):
    """
    Some of our objects aren't inherently JSON-encodable, such as numpy arrays
    or custom classes (e.g. :class:`Unit`). This encoder allows a magic
    ``__json__`` method to be defined on the class that returns a
    JSON-encodable object.

    """
    def default(self, o):
        if hasattr(o, '__json__'):
            return o.__json__()

        return super(DelegatingJSONEncoder, self).default(o)


class SimpleJSON(object):
    """
    This base class provides a default ``__json__`` method to be used by
    :class:`DelegatingJSONEncoder` as well as a convenience method to convert
    the object to JSON using that encoder.

    """
    def __json__(self):
        return self.__dict__

    def tojson(self, *args, **kwargs):
        """Convert this object to a JSON string"""
        return DelegatingJSONEncoder(*args, **kwargs).encode(self)


class NodeVisitorProxy(NodeVisitor, object):
    def __init__(self, proxy_class, document, **kwargs):
        super(NodeVisitorProxy, self).__init__(document)
        self._kwargs = kwargs
        self._set_proxy(proxy_class)

    def _set_proxy(self, proxy_class):
        self._proxy = proxy_class(document=self.document, **self._kwargs)

    def dispatch_departure(self, node):
        ret = self._proxy.dispatch_departure(node)
        if ret is None:
            pass

        elif isinstance(ret, type):
            self._set_proxy(ret)

        else:
            return ret

    def dispatch_visit(self, node):
        ret = self._proxy.dispatch_visit(node)
        if ret is None:
            pass

        elif isinstance(ret, type):
            self._set_proxy(ret)

        else:
            return ret


class Content(SimpleJSON):
    pass


class ContentParagraph(Content):
    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return '{!r}'.format(self.text)

    def __json__(self):
        return {
            'tag': 'p',
            'props': {},
            'children': [
                self.text.replace('\n', ' '),
            ],
        }


class ContentHeading(Content):
    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return 'Heading: {!r}'.format(
            self.text,
        )

    def __json__(self):
        return {
            'tag': 'h1',
            'props': {},
            'children': [
                self.text.replace('\n', ' '),
            ],
        }


class ContentListItem(Content):
    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return '* {!r}'.format(self.text)

    def __json__(self):
        return {
            'tag': 'ul',
            'props': {},
            'children': [
                {
                    'tag': 'li',
                    'props': {},
                    'children': [
                        self.text.replace('\n', ' '),
                    ],
                },
            ],
        }


class ContentTable(Content):
    def __init__(self, heading, rows):
        self.heading = heading
        self.rows = rows

    def __repr__(self):
        return 'Table: {!r}'.format(self.heading)

    def __json__(self):
        return {
            'tag': 'p',
            'props': {},
            'children': [
                'table not supported, sorry!',
            ],
        }


class Spell(SimpleJSON):
    def __init__(self):
        self.source = None
        self.id = None
        self.name = None
        self.type = None
        self.casting_time = None
        self.range = None
        self.components = None
        self.duration = None
        self.content = []

    def __json__(self):
        return {
            'type': 'spell',
            'source': self.source,
            'id': self.id,
            'name': self.name,
            'attributes': {
                'type': self.type,
                'casting_time': self.casting_time,
                'range': self.range,
                'components': self.components,
                'duration': self.duration,
            },
            'content': self.content,
        }

    def __repr__(self):
        return '{}(\n  {}\n)'.format(
            self.__class__.__name__,
            ',\n  '.join((
                '{}={!r}'.format(k, v)
                for k, v in self.__dict__.items()
            )),
        )

    @classmethod
    def parse(cls, document):
        spell = cls()
        visitor = NodeVisitorProxy(SpellSourceVisitor, document, spell=spell)
        document.walkabout(visitor)

        return spell


class SpellVisitor(GenericNodeVisitor, object):
    def __init__(self, document, spell):
        self.document = document
        self.spell = spell

    def visit_problematic(self, node):
        raise SkipChildren

    def visit_system_message(self, node):
        raise SkipChildren

    def default_visit(self, node):
        raise NotImplementedError('{}.visit_{}'.format(
            self.__class__.__name__,
            node.__class__.__name__,
        ))

    def default_departure(self, node):
        pass


class SpellSourceVisitor(SpellVisitor):
    def visit_document(self, node):
        self.spell.source = node.attributes['source']
        return SpellIdVisitor


class SpellIdVisitor(SpellVisitor):
    def visit_target(self, node):
        self.spell.id = node.attributes['names'][0]
        return SpellNameVisitor


class SpellNameVisitor(SpellVisitor):
    def visit_section(self, node):
        pass

    def visit_title(self, node):
        pass

    def visit_Text(self, node):
        self.spell.name = node.astext()

    def depart_title(self, node):
        return SpellTypeVisitor


class SpellTypeVisitor(SpellVisitor):
    def visit_section(self, node):
        self.spell.type = node.attributes['names'][0]

    def visit_title(self, node):
        pass

    def visit_Text(self, node):
        pass

    def depart_title(self, node):
        return SpellCastingTimeVisitor


class SpellCastingTimeVisitor(SpellVisitor):
    def visit_paragraph(self, node):
        pass

    def visit_strong(self, node):
        assert node.astext() == 'Casting Time:'
        raise SkipChildren

    def visit_Text(self, node):
        self.spell.casting_time = node.astext().strip()

    def depart_paragraph(self, node):
        return SpellRangeVisitor


class SpellRangeVisitor(SpellVisitor):
    def visit_paragraph(self, node):
        pass

    def visit_strong(self, node):
        assert node.astext() == 'Range:'
        raise SkipChildren

    def visit_Text(self, node):
        self.spell.range = node.astext().strip()

    def depart_paragraph(self, node):
        return SpellComponentsVisitor


class SpellComponentsVisitor(SpellVisitor):
    def visit_paragraph(self, node):
        pass

    def visit_strong(self, node):
        assert node.astext() == 'Components:'
        raise SkipChildren

    def visit_Text(self, node):
        if self.spell.components is None:
            self.spell.components = ''

        self.spell.components += node.astext().strip()

    def depart_paragraph(self, node):
        return SpellDurationVisitor


class SpellDurationVisitor(SpellVisitor):
    def visit_paragraph(self, node):
        pass

    def visit_strong(self, node):
        assert node.astext() == 'Duration:', node.astext()
        raise SkipChildren

    def visit_Text(self, node):
        self.spell.duration = node.astext().strip()

    def depart_paragraph(self, node):
        return SpellContentVisitor


class SpellContentVisitor(SpellVisitor):
    def visit_bullet_list(self, node):
        return SpellBulletListItemVisitor

    def visit_table(self, node):
        return SpellTableVisitor

    def visit_paragraph(self, node):
        pass

    def visit_strong(self, node):
        return SpellHeadingVisitor

    def visit_Text(self, node):
        self.spell.content.append(ContentParagraph(
            node.astext().strip(),
        ))
        return SpellContentVisitor


def SpellHeadingVisitor(SpellVisitor):
    def visit_Text(self, node):
        self.spell.content.append(ContentHeading(
            node.astext().strip(),
        ))

    def depart_strong(self, node):
        return SpellContentVisitor


class SpellBulletListItemVisitor(SpellVisitor):
    def visit_list_item(self, node):
        pass

    def visit_paragraph(self, node):
        pass

    def visit_Text(self, node):
        self.spell.content.append(ContentListItem(
            text=node.astext().strip(),
        ))

        return SpellBulletListItemVisitor

    def depart_bullet_list(self, node):
        return SpellContentVisitor


class SpellTableVisitor(SpellVisitor):
    def __init__(self, **kwargs):
        super(SpellTableVisitor, self).__init__(**kwargs)
        self.in_heading = False
        self.heading = []
        self.rows = []

    def visit_tgroup(self, node):
        pass

    def visit_colspec(self, node):
        pass

    def visit_thead(self, node):
        self.in_heading = True

    def depart_thead(self, node):
        self.in_heading = False

    def visit_tbody(self, node):
        pass

    def visit_row(self, node):
        if not self.in_heading:
            self.rows.append([])

    def visit_entry(self, node):
        pass

    def visit_paragraph(self, node):
        pass

    def visit_Text(self, node):
        if self.in_heading:
            self.heading.append(node.astext().strip())

        else:
            self.rows[-1].append(node.astext().strip())

    def depart_table(self, node):
        return SpellContentVisitor


def parse_document(input_filename):
    with open(input_filename, 'r') as f:
        option_parser = OptionParser(
            components=(Parser,),
        )

        default_settings = option_parser.get_default_values()

        settings = default_settings.copy()
        settings.update({
            'report_level': 100,
        }, option_parser)

        document = new_document(input_filename, settings)
        parser = Parser()
        parser.parse(f.read(), document)

        return document


def full_paths(root_directory):
    for root, dirs, files in os.walk(root_directory):
        root = Path(root)

        for path in files:
            path = root / path

            yield path


def parse_all_spells(root_directory):
    for path in full_paths(root_directory):
        if not str(path).startswith('source/Spellcasting/spells_a-z/'):
            continue

        if path.name == 'index.rst':
            continue

        try:
            yield Spell.parse(parse_document(path))
        except NotImplementedError:
            pass
        except AssertionError:
            pass


def main(input_filename, debug=False, find_all=False):
    if find_all:
        all_spells = list(parse_all_spells(input_filename))
        encoder = DelegatingJSONEncoder(indent=2)
        print(encoder.encode(all_spells))

    else:
        document = parse_document(input_filename)
        if debug:
            print(document.pformat())

        spell = Spell.parse(document)
        print(spell.tojson(indent=2))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('input_filename')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--find-all', action='store_true')
    args = parser.parse_args()

    main(**vars(args))
