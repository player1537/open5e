#!/usr/bin/env python2
"""

"""

from __future__ import print_function

from contextlib import contextmanager

from docutils.frontend import OptionParser
from docutils.parsers.rst import Parser
from docutils.nodes import (
    GenericNodeVisitor, NodeVisitor, SkipChildren,
)
from docutils.utils import new_document


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


class Content(object):
    pass


class ContentParagraph(Content):
    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return '{!r}'.format(self.text)


class ContentHeading(Content):
    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return 'Heading: {!r}'.format(
            self.text,
        )


class ContentListItem(Content):
    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return '* {!r}'.format(self.text)


class ContentTable(Content):
    def __init__(self, heading, rows):
        self.heading = heading
        self.rows = rows

    def __repr__(self):
        return 'Table: {!r}'.format(self.heading)


class Spell(object):
    """
    <document source="./source/Spellcasting/spells_a-z/a/acid-splash.rst">
        <target ids="srd-acid-splash" names="srd:acid-splash">
        <section ids="acid-splash" names="acid\ splash">
            <title>
                Acid Splash
            <section ids="conjuration-cantrip" names="conjuration\ cantrip">
                <title>
                    Conjuration cantrip
                <paragraph>
                    <strong>
                        Casting Time:
                     1 action
                <paragraph>
                    <strong>
                        Range:
                     60 feet
                <paragraph>
                    <strong>
                        Components:
                     V, S
                <paragraph>
                    <strong>
                        Duration:
                     Instantaneous
                <paragraph>
                    You hurl a bubble of acid. Choose one creature within range, or choose
                    two creatures within range that are within 5 feet of each other. A
                    target must succeed on a Dexterity saving throw or take 1d6 acid damage.
                <paragraph>
                    This spell's damage increases by 1d6 when you reach 5th level (2d6),
                    11th level (3d6), and 17th level (4d6).
    """

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

    def __repr__(self):
        return '{}(\n  {}\n)'.format(
            self.__class__.__name__,
            ',\n  '.join((
                '{}={!r}'.format(k, v)
                for k, v in self.__dict__.iteritems()
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
        default_settings = OptionParser(
            components=(Parser,),
        ).get_default_values()

        document = new_document(input_filename, default_settings)
        parser = Parser()
        parser.parse(f.read(), document)

        return document


def main(input_filename):
    document = parse_document(input_filename)
    print(document.pformat())
    spell = Spell.parse(document)
    print(spell)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('input_filename')
    args = parser.parse_args()

    main(**vars(args))
