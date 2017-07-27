import re
import pymel.core as pc
import maya.cmds as cmds
import os.path as op

import functools


def objSetDiff(new, cur):
    # curSg.union([pc.PyNode(obj) for obj in cur])
    curSgs = set([str(obj) for obj in cur])
    # newSg = pc.sets()
    # newSg.union([pc.PyNode(obj) for obj in new])
    newSgs = set([str(obj) for obj in new])
    diff = newSgs.difference(curSgs)
    return [obj for obj in diff]


def getNiceName(name, full=False):
    if full:
        return name.replace(':', '_').replace('|', '_')
    return name.split(':')[-1].split('|')[-1]


frameno_re = re.compile(r'\d+')


def removeLastNumber(path, bychar='?'):
    dirname, basename = op.split(path)
    numbers = frameno_re.findall(basename)
    if numbers:
        pos = basename.rfind(numbers[-1])
        basename = (basename[:pos] + basename[pos:].replace(numbers[-1],
                    bychar * len(numbers[-1])))
        path = op.normpath(op.join(dirname, basename))
        return path, numbers[-1]
    return path, ''


def newScene(func=None):
    '''
    Make a bare scene.
    '''
    def wrapper(*arg, **kwarg):

        if kwarg.get("newScene"):
            pc.newFile(f=True)
        else:
            pass
        return func(*arg, **kwarg)
    return wrapper if func else pc.newFile(f=True)


def newcomerObjs(func):
    '''
    @return: the list of objects that were added to the scene
    after calling func
    '''
    def wrapper(*arg, **kwarg):
        selection = cmds.ls(sl=True)
        cur = cmds.ls()
        func(*arg, **kwarg)
        new = objSetDiff(cmds.ls(), cur)
        pc.select(selection)
        return new
    return wrapper


def undoChunk(func):
    ''' This is a decorator for all functions that cause a change in a maya
    scene. It wraps all changes of the decorated function in a single undo
    chunk
    '''
    def _wrapper(*args, **dargs):
        res = None
        try:
            undoChunk = dargs.pop('chunkOpen')
        except KeyError:
            undoChunk = None
        if undoChunk is True:
            pc.undoInfo(openChunk=True)
        try:
            res = func(*args, **dargs)
        finally:
            if undoChunk is False:
                pc.undoInfo(closeChunk=True)
            return res
    return _wrapper


def getBitString():
    if pc.about(is64=True):
        return '64bit'
    return '32bit'


def removeNamespace(obj=None):
    '''removes the namespace of the given or selected PyNode'''
    if not obj:
        obj = pc.ls(sl=True)[0]
    name = obj.name()
    nameParts = name.split(':')
    ns = ':'.join(nameParts[0:-1]) + ':'
    pc.namespace(mergeNamespaceWithRoot=True, removeNamespace=ns)


def isNodeType(node, typ=None):
    if typ is None:
        typ = pc.nt.Transform
    if typ != pc.nt.Transform and isinstance(node, pc.nt.Transform):
        node = node.getShape(ni=True)
    return isinstance(node, typ)


isMesh = functools.partial(isNodeType, typ=pc.nt.Mesh)


def removeNamespaceFromName(obj):
    splits = obj.split(':')
    return ':'.join(splits[1:-1] + [splits[-1]])


def removeNamespaceFromPathName(path):
    return '|'.join([removeNamespaceFromName(x) for x in path.split('|')])
