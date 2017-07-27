'''Contains some utility function for imaya.textures package'''

import pymel.core as pc
import os.path as op


__all__ = ['readPathAttr']


def expand_path(path):
    try:
        path = pc.workspace.expandName(path)
    except:
        pass
    path = op.abspath(path)
    return op.normpath(path)


def read_full_path_from_attribute(attr):
    '''the original function to be called from some functions this module
    returns fullpath according to the current workspace'''
    val = pc.getAttr(unicode(attr))
    return expand_path(val)


readPathAttr = read_full_path_from_attribute
