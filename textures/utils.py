'''Contains some utility function for imaya.textures package'''

import pymel.core as pc
import os.path as op


__all__ = ['readFullPathFromAttr', 'expandPath']


def expandPath(path):
    try:
        path = pc.workspace.expandName(path)
    except:
        pass
    path = op.abspath(path)
    return op.normpath(path)


def readFullPathFromAttr(attr):
    '''the original function to be called from some functions this module
    returns fullpath according to the current workspace'''
    val = pc.getAttr(unicode(attr))
    return expandPath(val)
