'''Sphinx .NET Domain

API documentation support for .NET langauges
'''

import re

from sphinx import addnodes
from sphinx.domains import Domain, ObjType
from sphinx.locale import l_, _
from sphinx.directives import ObjectDescription
from sphinx.roles import XRefRole
from sphinx.domains.python import _pseudo_parse_arglist
from sphinx.util.nodes import make_refnode
from sphinx.util.docfields import Field, GroupedField, TypedField


class DotNetSignature(object):
    '''Signature parsing for .NET directives

    Attributes
        prefix
            Object prefix or namespace

        member
            Member name

        arguments
            List of arguments
    '''

    def __init__(self, prefix, member, arguments):
        self.prefix = prefix
        self.member = member
        self.arguments = arguments

    @classmethod
    def from_string(cls, signature):
        '''Create signature objects from string definition

        :param signature: construct definition
        :type signature: string
        '''
        re_signature = re.compile(
            r'''
            ^(?:(?P<prefix>[\w\_\-\.]+)\.|)
            (?P<member>[\w\_\-]+)
            (?:\((?P<arguments>[^)]+)\)|)$
            ''',
            re.VERBOSE)
        match = re_signature.match(signature)
        if match:
            arg_string = match.group('arguments')
            arguments = None
            if arg_string:
                arguments = re.split(r'\,\s+', arg_string)
            return cls(
                prefix=match.group('prefix'),
                member=match.group('member'),
                arguments=arguments
            )
        return cls()

    def full_name(self):
        '''Return full name of member'''
        if self.prefix is not None:
            return '.'.join([self.prefix, self.member])
        return self.member

    def prefix(self, prefix):
        '''Return prefix of object, compared to input prefix

        :param prefix: object prefix to compare against
        '''
        pass

    def __str__(self):
        return '.'.join([str(self.prefix), str(self.member)])


class DotNetObject(ObjectDescription):
    '''Description of a .NET construct object.

    Class variables
    ---------------

        has_arguments
            If set to ``True`` this object is callable and a
            `desc_parameterlist` is added

        display_prefix
            What is displayed right before the documentation entry

        class_object
            TODO

        short_name
            Short cross reference name for object

        long_name
            Long cross reference and indexed data name for object
    '''

    has_arguments = False
    display_prefix = None
    class_object = False
    short_name = None
    long_name = None

    def handle_signature(self, sig, signode):
        '''Parses out pieces from construct signatures

        Parses out prefix and argument list from construct definition. This is
        assuming that the .NET languages this will support will be in a common
        format, such as::

            Namespace.Class.method(argument, argument, ...)

        The namespace and class will be determined by the nesting of rST
        directives.

        Returns
            Altered :py:data:`signode` with attributes corrected for rST
            nesting/etc
        '''
        sig = DotNetSignature.from_string(sig.strip())
        prefix = self.env.temp_data.get('dn:prefix', None)
        objectname = self.env.temp_data.get('dn:object')

        if prefix and sig.prefix == prefix:
            sig.prefix = None

        signode['object'] = sig.member
        signode['package'] = sig.prefix
        signode['fullname'] = sig.full_name()

        if self.display_prefix:
            signode += addnodes.desc_annotation(self.display_prefix,
                                                self.display_prefix)
        # TODO detect prefix that joins namespace and class/struct/etc
        if sig.prefix is not None:
            signode += addnodes.desc_addname(sig.prefix + '.', sig.prefix + '.')

        signode += addnodes.desc_name(sig.member, sig.member)
        if self.has_arguments:
            if not sig.arguments:
                signode += addnodes.desc_parameterlist()
            else:
                # TODO replace this
                _pseudo_parse_arglist(signode, ', '.join(sig.arguments))

        # TODO this should be prefix?
        return sig.full_name(), sig.prefix

    def add_target_and_index(self, name_obj, sig, signode):
        # TODO wtf does this do?
        objectname = self.options.get(
            'object', self.env.temp_data.get('dn:object'))
        fullname = name_obj[0]
        if fullname not in self.state.document.ids:
            signode['names'].append(fullname)
            signode['ids'].append(fullname.replace('$', '_S_'))
            signode['first'] = not self.names
            self.state.document.note_explicit_target(signode)
            objects = self.env.domaindata['dn']['objects']
            if fullname in objects:
                self.state_machine.reporter.warning(
                    'duplicate object description of %s, ' % fullname +
                    'other instance in ' +
                    self.env.doc2path(objects[fullname][0]),
                    line=self.lineno)
            objects[fullname] = self.env.docname, self.objtype

        indextext = self.get_index_text(objectname, name_obj)
        if indextext:
            self.indexnode['entries'].append(('single', indextext,
                                              fullname.replace('$', '_S_'),
                                              ''))

    def get_index_text(self, objectname, name_obj):
        # TODO wtf does this do?
        name, obj = name_obj
        if self.objtype == 'function':
            if not obj:
                return _('%s() (built-in function)') % name
            return _('%s() (%s method)') % (name, obj)
        elif self.objtype == 'package':
            return _('%s (package)') % name
        elif self.objtype == 'data':
            return _('%s (global variable or constant)') % name
        elif self.objtype == 'attribute':
            return _('%s (%s attribute)') % (name, obj)
        return ''

    @classmethod
    def get_type(cls):
        return ObjType(l_(cls.long_name), cls.short_name)


class DotNetObjectNested(DotNetObject):
    '''Nestable object'''

    def before_content(self):
        '''Build up prefix with nested elements'''
        super(DotNetObjectNested, self).before_content()
        prefix_existing = self.env.temp_data.get('dn:prefix', None)
        print('Existing prefix: %s' % prefix_existing)
        if self.names:
            (parent, prefix) = self.names.pop()
            print('New prefix: %s' % prefix)
            self.env.temp_data['dn:prefix'] = prefix
            self.clsname_set = True

    def after_content(self):
        super(DotNetObjectNested, self).after_content()
        if self.clsname_set:
            self.env.temp_data['dn:prefix'] = None


class DotNetCallable(DotNetObject):
    '''An object that is callable with arguments'''
    has_arguments = True
    doc_field_types = [
        TypedField('arguments', label=l_('Arguments'),
                   names=('argument', 'arg', 'parameter', 'param'),
                   typerolename='func', typenames=('paramtype', 'type')),
        Field('returnvalue', label=l_('Returns'), has_arg=False,
              names=('returns', 'return')),
        Field('returntype', label=l_('Return type'), has_arg=False,
              names=('rtype',)),
    ]


# Types
class DotNetNamespace(DotNetObjectNested):
    short_name = 'ns'
    long_name = 'namespace'
    display_prefix = 'namespace '


class DotNetClass(DotNetObjectNested):
    short_name = 'cls'
    long_name = 'class'
    display_prefix = 'class '


class DotNetStructure(DotNetObjectNested):
    short_name = 'struct'
    long_name = 'structure'
    display_prefix = 'structure '


class DotNetInterface(DotNetObjectNested):
    short_name = 'iface'
    long_name = 'interface'
    display_prefix = 'interface '


class DotNetDelegate(DotNetObjectNested):
    short_name = 'del'
    long_name = 'delegate'
    display_prefix = 'delegate '


class DotNetEnumeration(DotNetObjectNested):
    short_name = 'enum'
    long_name = 'enumeration'
    display_prefix = 'enumeration '


# Members
class DotNetMethod(DotNetCallable):
    class_object = True
    short_name = 'meth'
    long_name = 'method'


class DotNetProperty(DotNetCallable):
    class_object = True
    short_name = 'prop'
    long_name = 'property'


# Cross referencing
class DotNetXRefRole(XRefRole):

    def process_link(self, env, refnode, has_explicit_title, title, target):
        refnode['dn:object'] = env.temp_data.get('dn:object')
        refnode['dn:namespace'] = env.temp_data.get('dn:namespace')
        if not has_explicit_title:
            title = title.lstrip('.')
            # TODO tilde?
            target = target.lstrip('~')
            if title[0:1] == '~':
                title = title[1:]
                dot = title.rfind('.')
                if dot != -1:
                    title = title[dot+1:]
        if target[0:1] == '.':
            target = target[1:]
            refnode['refspecific'] = True
        return title, target


_types = [
    DotNetNamespace,
    DotNetClass,
    DotNetStructure,
    DotNetInterface,
    DotNetDelegate,
    DotNetEnumeration,

    DotNetMethod,
    DotNetProperty,
]


class DotNetDomain(Domain):
    '''.NET language domain.'''

    name = 'dn'
    label = '.NET'

    object_types = dict((cls.long_name, cls.get_type())
                        for cls in _types)
    directives = dict((cls.long_name, cls)
                     for cls in _types)
    roles = dict((cls.short_name, DotNetXRefRole())
                 for cls in _types)

    initial_data = {
        'objects': {}, # fullname -> docname, objtype
    }

    def clear_doc(self, docname):
        for fullname, (fn, _) in self.data['objects'].items():
            if fn == docname:
                del self.data['objects'][fullname]

    def find_obj(self, env, pkg, name, obj_type, searchorder=0):
        '''Find object reference

        :param env: Build environment
        :param pkg: Object package
        :param name: Object name
        :param obj_type: Object type
        :param searchorder: Search for exact match
        '''
        # Skip parens
        if name[-2:] == '()':
            name = name[:-2]

        if not name:
            return []

        objects = self.data['objects']
        matches = []
        newname = None

        if pkg is not None:
            fullname = '.'.join([pkg, name])

        if searchorder == 1:
            if pkg and fullname in objects:
                newname = fullname
            else:
                newname = name
        else:
            if name in objects:
                newname = name
            elif pkg and fullname in objects:
                newname = fullname

        return newname, objects.get(newname)

    def resolve_xref(self, env, fromdocname, builder, obj_type, target, node,
                     contnode):
        objectname = node.get('dn:object')
        namespace = node.get('dn:namespace')
        searchorder = node.hasattr('refspecific') and 1 or 0

        name, obj = self.find_obj(env, namespace, target, obj_type, searchorder)

        if not obj:
            return None
        # TODO required to swap out dollar sigil?
        return make_refnode(builder, fromdocname, obj[0],
                            name.replace('$', '_S_'), contnode, name)

    def get_objects(self):
        # TODO wtf does this do?
        for refname, (docname, type) in self.data['objects'].iteritems():
            yield refname, refname, type, docname, \
                  refname.replace('$', '_S_'), 1


def setup(app):
    app.add_domain(DotNetDomain)