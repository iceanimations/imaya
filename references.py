import os

import pymel.core as pc
import maya.cmds as cmds

from .utils import newScene, newcomerObjs

def getReferences(loaded=False, unloaded=False):
    refs = []
    for ref in pc.ls(type=pc.nt.Reference):
        if ref.referenceFile():
            refs.append(ref.referenceFile())
    if loaded:
        return [ref for ref in refs if ref.isLoaded()]
    if unloaded:
        return [ref for ref in refs if not ref.isLoaded()]
    return refs

def addRef(path):
    namespace = os.path.basename(path)
    namespace = os.path.splitext(namespace)[0]
    match = re.match('(.*)([-._]v\d+)(.*)', namespace)
    if match:
        namespace = match.group(1) + match.group(3)
    return pc.createReference(path, namespace=namespace, mnc=False)

def getCombinedMesh(ref):
    '''returns the top level meshes from a reference node'''
    meshes = []
    if ref:
        for node in pc.FileReference(ref).nodes():
            if type(node) == pc.nt.Mesh:
                try:
                    node.firstParent().firstParent()
                except pc.MayaNodeError:
                    if not node.isIntermediate():
                        meshes.append(node.firstParent())
                except Exception as ex:
                    #self.errorsList.append('Could not retrieve combined mesh for Reference\n'+ref.path+'\nReason: '+ str(ex))
                    print 'Error: %r: %r'%(type(ex), ex)
    return meshes

def referenceExists(path):
    # get the existing references
    exists = cmds.file(r = True, q = True)
    exists = [util.normpath(x) for x in exists]
    path = util.normpath(path)
    if path in exists: return True

def get_reference_paths():
    '''
    Query all the top-level reference nodes in a file or in the currently open scene
    @return: {refNode: path} of all level one scene references
    '''
    refs = {}
    for ref in pc.listReferences():
        refs[ref] = str(ref.path)
    return refs

referenceInfo = get_reference_paths

@newScene
@newcomerObjs
def addReference(paths=[], dup = True, stripVersionInNamespace=True, *arg, **kwarg):
    '''
    adds reference to the component at 'path' (str)
    @params:
            path: valid path to the asset dir (str)
            component: (Rig, Model, Shaded Model) (str)
            dup: allow duplicate referencing
    '''
    for path in paths:
        namespace = os.path.basename(path)
        namespace = os.path.splitext(namespace)[0]
        if stripVersionInNamespace:
            # version part of the string is recognized as .v001
            match = re.match('(.*)([-._]v\d+)(.*)', namespace)
            if match:
                namespace = match.group(1) + match.group(3)
        cmds.file(path, r=True,
                mnc=False, namespace=namespace)

def createReference(path, stripVersionInNamespace=True):
    if not path or not op.exists(path):
        return None
    before = pc.listReferences()
    namespace = op.basename(path)
    namespace = op.splitext(namespace)[0]
    if stripVersionInNamespace:
        # version part of the string is recognized as .v001
        match = re.match('(.*)([-._]v\d+)(.*)', namespace)
        if match:
            namespace = match.group(1) + match.group(3)
    pc.createReference(path, namespace=namespace, mnc=False)
    after = pc.listReferences()
    new = [ref for ref in after if ref not in before and not
            ref.refNode.isReferenced()]
    return new[0]

def removeAllReferences():
    refNodes = pc.ls(type=pc.nt.Reference)
    refs = []
    for node in refNodes:
        if not node.referenceFile():
            continue
        try: refs.append(pc.FileReference(node))
        except: pass

    while refs:
        try:
            ref = refs.pop()
            if ref.parent() is None:
                removeReference(ref)
            else:
                refs.insert(0, ref)
        except Exception as e:
            print 'Error removing reference: ', str(e)


def removeReference(ref):
    ''':type ref: pymel.core.system.FileReference()'''
    if ref:
        ref.removeReferenceEdits()
        ref.remove()

