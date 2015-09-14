# Date: Mon 26/11/2012

import os, tempfile
import pymel.core as pc
import maya.cmds as cmds
try:
    import iutil as util
except:
    import iutilities as util
reload(util)
import traceback
op = os.path
import re
import shutil
from collections import OrderedDict
import qutil
reload(qutil)


class ArbitraryConf(object):
    # iMaya depends on the following external attributes
    # provided here incase it is not overridden by the user
    local_drives = ['c:', 'd:', r'\\']
    presetGeo = {'camera': 'RenderCam',
                 'geometry': 'SphereSurfaceShape',
                 'path': r'r:\Pipe_Repo\Projects\DAM\Data\presetScene\ball.ma',
                 'resolution': [256, 256]}

conf = ArbitraryConf()

class ExportError(Exception):
    '''
    Maya asset export failed.
    '''
    def __init__(self, *arg, **kwarg):
        self.code = 0
        self.error = "Export failed. Some error occured while exporting maya scene."
        self.value = kwarg.get("obj","")
        self.strerror = self.__str__()

    def __str__(self):
        return (self.value + ". " if self.value else "") + self.error

class ShaderApplicationError(Exception):
    '''
    Unable to apply shader.
    '''
    def __init__(self, *arg, **kwarg):
        self.code = 1
        self.error = "Unable to apply shader"
        self.strerror = self.__str__()

    def __str__(self):
        return "ShaderApplicationError: ", self.error

class FileInfo(object):

    @classmethod
    def save(cls, key, value):
        pc.fileInfo[key] = value

    @classmethod
    def get(cls, key):
        return pc.fileInfo.get(key, '').decode('unicode_escape')

    @classmethod
    def remove(cls, key):
        if cls.get(key):
            return pc.fileInfo.pop(key)

def addMeshesToGroup(meshes, grp):
    group2 = pc.ls(grp)
    if group2:
        if len(group2) == 1:
            pc.parent(meshes, group2)
    else:
        pc.select(meshes)
        pc.group(name=grp)

def batchRender():
    '''Renders all active render layers in current Maya scene, according to
    render settings and saves renders to Project Directory
    @return: Generator containing layer names'''
    layers = getRenderLayers()
    for layer in layers:
        layer.renderable.set(0)
    for layer in layers:
        layer.renderable.set(1)
        yield layer.name()
        pc.mel.mayaBatchRenderProcedure(1, "", "", "", "")
        layer.renderable.set(0)


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

def getCombinedMeshFromSet(_set):
    meshes = [shape for transform in _set.dsm.inputs() for shape in transform.getShapes(ni=True, type='mesh')]
    if not meshes: return
    pc.select(meshes)
    mesh = pc.polyUnite(ch=1, mergeUVSets=1, name=_set.name().replace('_geo_', '_shaded_').replace('_set', '_combined'))[0]
    try: pc.delete(_set)
    except: pass
    return mesh

def createShadingNode(typ):
    return pc.PyNode(pc.mel.eval('createRenderNodeCB -asShader "surfaceShader" %s "";'%typ))

def switchToMasterLayer():
    if pc.editRenderLayerGlobals(q=True, currentRenderLayer=True).lower().startswith('default'):
        return
    for layer in getRenderLayers(renderableOnly=False):
        if layer.name().lower().startswith('default'):
            pc.editRenderLayerGlobals(currentRenderLayer=layer)
            break

def removeNamespace(obj=None):
    '''removes the namespace of the given or selected PyNode'''
    if not obj:
        obj = pc.ls(sl=True)[0]
    name = obj.name()
    nameParts = name.split(':')
    ns = ':'.join(nameParts[0:-1]) + ':'
    pc.namespace(mergeNamespaceWithRoot=True, removeNamespace=ns)

def applyCache(node, xmlFilePath):
    '''
    applies cache to the given mesh or set
    @param node: ObjectSet or Mesh
    '''
    xmlFilePath = xmlFilePath.replace('\\', '/')
    if isinstance(node, pc.nt.Transform):
        try:
            tempNode = node.getShapes(ni=True)
            if not tempNode:
                tempNode = pc.ls(node, dag=True, type='mesh')
                if not tempNode:
                    raise TypeError, node.name() + " does not contain a shape node"
            for obj in tempNode:
                if not obj.intermediateObject.get():
                    node = obj
        except:
            raise TypeError, 'Node must be an instance of pc.nt.Mesh'
            return
    elif isinstance(node, pc.nt.Mesh):
        pass
    pc.mel.doImportCacheFile(xmlFilePath, "", [node], list())

def deleteCache(mesh=None):
    if not mesh:
        try:
            mesh = pc.ls(sl=True)[0]
        except IndexError:
            return
    try:
        if mesh.history(type='cacheFile'):
            pc.select(mesh)
            pc.mel.eval('deleteCacheFile 3 { "keep", "", "geometry" } ;')
    except Exception as ex:
        pc.warning(str(ex))

def meshesCompatible(mesh1, mesh2):
    try:
        if len(mesh1.f) == len(mesh2.f):
            if len(mesh1.vtx) == len(mesh2.vtx):
                if len(mesh1.e) == len(mesh2.e):
                    return True
    except AttributeError:
        raise TypeError, 'Objects must be instances of pymel.core.nodetypes.Mesh'
    return False

def setsCompatible(obj1, obj2):
    '''
    returns True if two ObjectSets are compatible for cache
    '''
    if type(obj1) != pc.nt.ObjectSet and type(obj2) != pc.nt.ObjectSet:
        raise TypeError, 'Values must be instances of pymel.core.nodetypes.ObjectSet'
    flag = True
    # check if the number of members is equal in both sets
    if len(obj1) == len(obj2):
        # check if the order and meshes are compatible in each set
        for i in range(len(obj1)):
            try:
                if not meshesCompatible(obj1.dagSetMembers[i].inputs()[0],
                                        obj2.dagSetMembers[i].inputs()[0]):
                    flag = False
                    break
            except IndexError:
                flag = False
                break
    else:
        flag = False

    return flag

geo_sets_compatible = setsCompatible

def geo_set_valid(obj1):
    '''  '''
    obj1 = pc.nt.ObjectSet(obj1)
    if 'geo_set' not in obj1.name().lower():
        return False
    for i in range(len(obj1)):
        try:
            member = obj1.dagSetMembers[i].inputs()[0]
            mesh = member.getShape(type='mesh', ni=True)
        except:
            return False
        if not mesh or not mesh.numVertices():
            return False
    return True

def get_geo_sets(nonReferencedOnly=False, validOnly=False):
    geosets = []
    for node in pc.ls(exactType='objectSet'):
        if 'geo_set' in node.name().lower() and (not nonReferencedOnly or
                not node.isReferenced()) and (not validOnly or
                        geo_set_valid(node) ):
            geosets.append(node)
    return geosets

def getGeoSets():
    '''return only valid geo sets'''
    try:
        return [s for s in pc.ls(exactType=pc.nt.ObjectSet) if
                s.name().lower().endswith('_geo_set') and geo_set_valid(s)]
    except IndexError:
        pass

def referenceExists(path):
    # get the existing references
    exists = cmds.file(r = True, q = True)
    exists = [util.normpath(x) for x in exists]
    path = util.normpath(path)
    if path in exists: return True

def export(filename, filepath, selection = True, pr = True,
           *args, **kwargs):
    '''
    '''
    path = os.path.join(filepath, filename)
    filetype = cmds.file(q=True, typ=True)[0]
    try:
        if selection:

            pc.exportSelected(path,
                              force=True,
                              expressions = True,
                              constructionHistory = True,
                              channels = True,
                              shader = True,
                              constraints = True,
                              options="v=0",
                              typ=filetype,
                              pr = pr)
        else:
            pc.exportAll(path , force = True,
                         typ = filetype, pr = pr)

    except BaseException as e:
        traceback.print_exc()
        print e
        raise BaseException

def extractShadersAndSave(filename, filepath, selection = True):
    '''
    extract all the shaders
    '''
    pass

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
def objSetDiff(new, cur):

    # curSg.union([pc.PyNode(obj) for obj in cur])
    curSgs = set([str(obj) for obj in cur])
    # newSg = pc.sets()
    # newSg.union([pc.PyNode(obj) for obj in new])
    newSgs = set([str(obj) for obj in new])
    diff = newSgs.difference(curSgs)
    return [obj for obj in diff]

def newScene(func = None):
    '''
    Make a bare scene.
    '''
    def wrapper(*arg, **kwarg):

        if kwarg.get("newScene"):
            pc.newFile(f=True)
        else: pass
        print "newScene"
        print arg
        print kwarg
        return func(*arg, **kwarg)
    return wrapper if func else pc.newFile(f=True)

def newcomerObjs(func):
    '''
    @return: the list of objects that were added to the scene
    after calling func
    '''
    def wrapper(*arg, **kwarg):
        selection = cmds.ls(sl = True)
        cur = cmds.ls()
        print "newcomerObjs"
        print arg
        print kwarg
        func(*arg, **kwarg)
        new = objSetDiff(cmds.ls(), cur)
        pc.select(selection)
        return new
    return wrapper

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

def removeReference(ref):
    ''':type ref: pymel.core.system.FileReference()'''
    if ref:
        ref.removeReferenceEdits()
        ref.remove()

def find_geo_set_in_ref(ref, key=lambda node: 'geo_set' in node.name().lower()):
    for node in ref.nodes():
        if pc.nodeType(node) == 'objectSet':
            if key(node):
                return node

@newScene
@newcomerObjs
def importScene(paths = [], *arg, **kwarg):
    '''
    imports the paths
    @params:
            path: path to component (list)
    '''

    for path in paths:
        if referenceExists(path):
            cmds.file(path, importReference = True)
        # create reference
        else:
            try:
                cmds.file(path, i = True)
            except RuntimeError:
                pc.error('File not found.')

def addOptionVar(key, value, array = True):
    '''
    creates an option variable
    '''
    if array:
        cmds.optionVar(sva = (key, value))
    else:
        cmds.optionVar(sv = (key, value))

def removeOptionVar(key, index = None):
    if index is not None:
        cmds.optionVar(rfa = (key, index))
    else: cmds.optionVar(rm = key)

def getOptionVars(key):
    return cmds.optionVar(q = key)

def createComponentChecks():
    # Doesn't belong here. Should be purged.
    return any((util.localPath(path, conf.local_drives) for path in referenceInfo().values()))

def getFileNodes(selection = False, rn = False):

    return pc.ls(type = 'file', sl = selection, rn = rn)

def getShadingFileNodes(selection):
    return [fileNode for obj in cmds.ls(sl = selection,
                                      rn = False)
            for shader in filter(lambda hist: isinstance(hist,
                                                         pc.nt.ShadingEngine),
                                 pc.listHistory(obj, f = True))
            for fileNode in filter(lambda shaderHist: isinstance(shaderHist,
                                                                 pc.nt.File),
                                   getShadingEngineHistoryChain(shader))]

def imageInRenderView():
    ff = pc.getAttr('defaultRenderGlobals.imageFormat')
    pc.setAttr('defaultRenderGlobals.imageFormat', 32)
    render = pc.renderWindowEditor('renderView', e=1, wi = util.getTemp(suffix = ".png"))
    pc.setAttr('defaultRenderGlobals.imageFormat', ff)
    return render[1]

def renameFileNodePath(mapping):
    if not mapping:
        return False # an exception should (idly) be raise
    else:
        for fileNode in pc.ls(type= "file"):
            for path in mapping:
                if util.normpath(pc.getAttr(fileNode + ".ftn")) == util.normpath(path):
                    pc.setAttr(fileNode + ".ftn", mapping[path])

def getShadingEngineHistoryChain(shader):
    chain = []
    sets = cmds.sets( str( shader ), q = True )
    for inputs in map(lambda inp: getattr(pc.PyNode(shader),
                                        inp).inputs(),
                    ["vs", "ds", "ss"]):
        if inputs:
            chain.extend([x for x in pc.listHistory(inputs[0])
            if not isinstance( x, pc.nt.Reference )
            and ((not x in sets) if sets else True)
            and not isinstance(x, pc.nt.GroupId)])
    return chain + [shader]

class SetDict(dict):
    ''' A type of dictionary which can only have sets as its values and update
    performs union on sets
    '''
    def __getitem__(self, key):
        if not self.has_key(key):
            self[key]=set()
        return super(SetDict, self).__getitem__(key)

    def __setitem__(self, key, val):
        if not isinstance(val, set):
            raise TypeError, 'value must be a set'
        super(SetDict, self).__setitem__(key, val)

    def get(self, key, *args, **kwargs):
        return self.__getitem__(key)

    def update(self, d):
        if not isinstance(d, SetDict):
            raise TypeError, "update argument must be a setDict"
        for k, v in d.iteritems():
            self[k].update(v)


uvTilingModes = ['None', 'zbrush', 'mudbox', 'mari', 'explicit']
def textureFiles(selection = True, key = lambda x: True, getTxFiles=True,
        returnAsDict=False):
    '''
    @key: filter the tex with it
    :rtype setDict:
    '''
    ftn_to_texs = SetDict()
    fileNodes = getFileNodes(selection)

    for fn in fileNodes:
        texs = getTexturesFromFileNode(fn, key=key, getTxFiles=True)
        ftn_to_texs.update(texs)

    if returnAsDict:
        return ftn_to_texs
    else:
        return list(reduce(lambda a,b: a.union(b), ftn_to_texs.values(), set()))

def getTexturesFromFileNode(fn, key=lambda x:True, getTxFiles=True,
        getTexFiles=True):
    ''' Given a Node of type file, get all the paths and texture files
    :type fn: pc.nt.File
    '''
    if not isinstance(fn, pc.nt.File):
        if not pc.nodeType == 'file':
            raise TypeError, '%s is not a file node' % fn

    texs = SetDict()

    filepath = readPathAttr(fn + '.ftn')
    uvTilingMode = uvTilingModes[0]

    # New in Maya 2015
    if pc.attributeQuery('uvTilingMode', node=fn, exists=True):
        uvTilingMode = uvTilingModes[pc.getAttr(fn + '.uvt')]

    # still attempt to resolve using tokens in string
    if uvTilingMode == 'None':
        uvTilingMode = str(util.detectUdim(filepath))
    elif not uvTilingMode == 'explicit':
        filepath = readPathAttr(fn + '.cfnp')

    # definitely no udim
    if uvTilingMode == 'None':
        if key(filepath) and op.exists(filepath) and op.isfile(filepath):
            texs[filepath].add(filepath)
        if pc.getAttr(fn + '.useFrameExtension'):
            seqTex = util.getSequenceFiles(filepath)
            if seqTex:
                texs[filepath].update(seqTex)

    # explicit naming
    elif uvTilingMode == 'explicit':
        if key(filepath) and op.exists(filepath) and op.isfile(filepath):
            texs[filepath].add(filepath)
        indices = pc.getAttr(fn + '.euvt', mi=True)
        for index in indices:
            filepath = readPathAttr(fn + '.euvt[%d].eutn'%index)
            if key(filepath) and op.exists(filepath) and op.isfile(filepath):
                texs[filepath].add(filepath)

    else: # 'mari', 'zbrush', 'mudbox'
        texs[filepath].update( util.getUVTiles( filepath, uvTilingMode ))

    if getTxFiles:
        for k, files in texs.iteritems():
            texs[k].update(filter(None,
                [util.getFileByExtension(f) for f in files]))

    if getTexFiles:
        for k, files in texs.iteritems():
            texs[k].update(filter(None,
                [util.getFileByExtension(f, ext='tex') for f in files]))

    return texs

def getFullpathFromAttr(attr):
    ''' get full path from attr
    :type attr: pymel.core.general.Attribute
    '''
    node = pc.PyNode(attr).node()
    val = node.cfnp.get()
    if '<f>.' not in val: val = node.ftn.get()
    return val

def readPathAttr(attr):
    '''the original function to be called from some functions this module
    returns fullpath according to the current workspace'''
    val = pc.getAttr(unicode( attr ))
    val = pc.workspace.expandName(val)
    val = op.abspath(val)
    return op.normpath(val)

def remapFileNode(fn, mapping):
    ''' Update file node with given mapping
    '''
    if not isinstance(fn, pc.nt.File):
        if not pc.nodeType == 'file':
            raise TypeError, '%s is not a file node' % fn

    reverse = []
    uvTilingMode = uvTilingModes[0]
    if pc.attributeQuery('uvTilingMode', node=fn, exists=True):
        uvTilingMode = uvTilingModes[pc.getAttr(fn + '.uvt')]

    if uvTilingMode == 'None' or uvTilingMode == 'explicit':
        path = readPathAttr(fn + '.ftn')
        if mapping.has_key(path):
            pc.setAttr(fn + '.ftn', mapping[path])
            reverse.append((mapping[path], path))

    if uvTilingMode == 'explicit':
        reverse = []
        indices = pc.getAttr(fn + '.euvt', mi=True)
        for index in indices:
            path = readPathAttr(fn + '.euvt[%d].eutn'%index)
            if mapping.has_key(path):
                pc.setAttr(fn + '.euvt[%d].eutn'%index, mapping[path])
                reverse.append((mapping[path], path))

    elif uvTilingMode in uvTilingModes[1:4]:
        path = readPathAttr(fn + '.cfnp')
        if mapping.has_key(path):
            pc.setAttr(fn + '.ftn', mapping[path])
            reverse.append( (mapping[path], path) )

    return reverse

def map_textures(mapping):
    reverse = {}

    for fileNode in getFileNodes():
        for k, v in remapFileNode(fileNode, mapping):
            reverse[k]=v

    return reverse

def texture_mapping(newdir, olddir=None, scene_textures=None):
    if not scene_textures:
        scene_textures = textureFiles(returnAsDict=True)

    mapping = {}

    for ftn, texs in scene_textures.items():
        alltexs = [ftn] + texs
        for tex in alltexs:
            tex_dir, tex_base = os.path.split(tex)
            if olddir is None or util.paths_equal(tex_dir, olddir):
                mapping[tex] = os.path.join(newdir, tex_base)

    return mapping

def collect_textures(dest, scene_textures=None):
    '''
    Collect all scene texturefiles to a flat hierarchy in a single directory while resolving
    nameclashes

    @return: {ftn: tmp}
    '''

    # normalized -> temp
    mapping = {}
    if not op.exists(dest):
        return mapping

    if not scene_textures:
        scene_textures = textureFiles(selection = False, key = op.exists,
                returnAsDict=True)

    for myftn in scene_textures:
        if mapping.has_key(myftn):
            continue
        ftns, texs = util.find_related_ftns(myftn, scene_textures.copy())
        newmappings=util.lCUFTN(dest, ftns, texs)
        for fl, copy_to in newmappings.items():
            if op.exists(fl):
                shutil.copy(fl, copy_to)
        mapping.update(newmappings)

    return mapping

def _rendShader(shaderPath,
               renderImagePath,
               geometry = r"SphereSurfaceShape",
               cam = "RenderCam",
               res = (256, 256),
               presetScenePath = r"d:\user_files\hussain.parsaiyan\Desktop\Scenes\V-Ray\V-Ray Ball Scene\ball.ma"):
    rl = "1:masterLayer"
    mel = """setAttr vraySettings.vfbOn 0; setAttr defaultRenderLayer.renderable 1; setAttr defaultRenderGlobals.animation 0; setAttr vraySettings.relements_enableall 0; setAttr vraySettings.relements_separateFolders 0; file -r \\"{shaderPath}\\"; $shader = ls(\\"-rn\\", \\"-type\\", \\"shadingEngine\\"); connectAttr \\"{geometry}.iog\\" ($shader[0] + \\".dsm[0]\\"); setAttr \\"vraySettings.vfbOn\\" 1;""".format(geometry = geometry, shaderPath = shaderPath.replace(r"\\", "\\").replace("\\", r"\\"))

    r = "vray"
    x, y = res
    rd = op.dirname(renderImagePath)
    basename = op.basename(renderImagePath)
    of = "png"
    rl = "1:masterLayer"
    status = util.silentShellCall(r'render -r {r} -preRender "{mel}"  -of "{of}" -rd "{rd}" -im "{basename}" -x {x} -y {y} -rl {rl}  "{path}"'.format(
            **{"r": r,
               "cam": cam,
               "x": x,
               "y": y,
               "rd": rd,
               "of": of,
               "basename": basename,
               "mel": mel,
               "path": presetScenePath,
               "rl": rl}
              ))
    return status

def render(*arg, **kwarg):
    '''
    @return: path to render image and shader n/w that was exported. tuple
    '''
    selection = pc.ls(sl = True)
    try:
        if kwarg.get("sg"):
            presetGeo = conf.presetGeo
            with tempfile.NamedTemporaryFile(suffix = ".ma") as fobj:
                shader = op.splitext(fobj.name)[0]
            pc.select(getShadingEngineHistoryChain(kwarg.get("sg").keys()[0]),
                      ne = True)
            pc.Mel.eval('file -type "mayaAscii"')
            print "exporting"
            print export(op.basename(shader),
                         op.dirname(shader),
                         selection = True,
                         pr = False)
            print "exported"
            with tempfile.NamedTemporaryFile(suffix = ".png") as fobj:
                renImage = op.splitext(fobj.name)[0]

            _rendShader(shader + ".ma",
                                 renImage,
                                 geometry = presetGeo["geometry"],
                                 cam = presetGeo["camera"],
                                 res = presetGeo["resolution"],
                                 presetScenePath = presetGeo["path"]
                                 )
            # quick hack to avoid rendering image not found error
            result = (r"R:\Pipe_Repo\Projects\DAM\Data\prod\assets\test\myTestThings\textures\.archive\face.png\2012-09-05_14-08-49.747865\face.png", shader + ".ma")
            # result = (renImage + ".png", shader + ".ma")
            print "result: ", result
            # if int(status) != 0 or not all(map(op.exists, result)):
            #     raise ExportError(obj = kwarg["sg"].keys()[0])

        else:
            pc.runtime.mayaPreviewRenderIntoNewWindow()
            result = imageInRenderView()
    except BaseException as e:
        traceback.print_exc()
        raise e
    finally:
        pc.select(selection, ne = True)
    return result

def snapshot(resolution=conf.presetGeo["resolution"]):
    snapLocation = op.join(os.getenv("tmp"), str(int(util.randomNumber()*100000)))
    command = """float $currFrame = `currentTime -q`;
int $format = `getAttr "defaultRenderGlobals.imageFormat"`;
setAttr "defaultRenderGlobals.imageFormat" 8;
playblast -frame $currFrame -format "image" -cf "{image}" -orn 0 -v 0 -wh {res} -p 100;
setAttr "defaultRenderGlobals.imageFormat" $format;""".format(res =
                                                              " ".join(map(str, resolution)),
                                                              image =
                                                              snapLocation.replace("\\",
                                                                                   "/"))
    pc.mel.eval(command)
    return snapLocation

def selected():
    '''
    @return True, if selection exists in the current scene
    '''
    s = pc.ls(sl = True, dag = True, geometry = True)
    if s:
        return True
    else:
        return False

def getMeshes(selection = False):
    '''
    returns only meshes from the scene or selection
    '''
    meshSet = set()
    for mesh in pc.ls(sl = selection):
        if type(mesh) == pc.nt.Transform:
            try:
                m = mesh.getShape()
                if type(m) == pc.nt.Mesh:
                    meshSet.add(m)
            except AttributeError:
                pass
        elif type(mesh) == pc.nt.Mesh:
            meshSet.add(mesh)
        else: pass
    return list(meshSet)

def getShadingEngines(selection = False):
    '''
    returns the materials and shading engines
    @param:
        selection: if True, returns the materials and shading engines of selected meshes else all
    @return: dictionary {material: [shadingEngine1, shadingEngine2, ...]}
    '''
    sgMtl = {}
    sg = set()
    if selection:
        #meshes = getMeshes(selection = selection)
        meshes = pc.ls(sl=True, dag=True, type='mesh')
        otherNodes = pc.ls(sl=True, dep=True)
        meshes += otherNodes
        for mesh in meshes:
            for s in pc.listConnections(mesh, type = 'shadingEngine'):
                sg.add(s)
        sg.update(pc.ls(sl=True, type = 'shadingEngine' ))
    else:
        sg.update(set(pc.ls(type = 'shadingEngine')))
    for x in sg:
        ss = x.surfaceShader.inputs()
        ds = x.displacementShader.inputs()
        vs = x.volumeShader.inputs()
        imgs = x.imageShader.inputs()

        if ss: mtl = ss[0]
        elif ds: mtl = ds[0]
        elif vs: mtl = vs[0]
        elif imgs: mtl = imgs[0]
        else: continue

        #x = str(x)
        mtl = str(mtl)
        if not mtl: continue
        if sgMtl.has_key(mtl):
            if x not in sgMtl[mtl]:
                sgMtl[mtl].append(x)
        else:
            sgMtl[mtl] = [x]
    return sgMtl

def bins():
    binScenes = pc.getAttr("defaultRenderGlobals.hyperShadeBinList")
    if binScenes:
        return binScenes.split(";")
    else:
        return []

def objFilter(objType, objList):
    '''
    filter an objList for a particular type of maya obj
    @objType: currently only accepts PyNodes
    '''
    return filter(lambda obj: isinstance(pc.PyNode(obj),
                                         objType),
                  objList)

def addShadersToBin(binName, paths = [], new = True):
    '''
    bin is a group of shaders
    '''
    if paths and any(map(op.exists, paths)):
        pc.runtime.HypershadeWindow()
        pc.Mel.eval('refreshHyperShadeBinsUI "hyperShadePanel1Window|TearOffPane|hyperShadePanel1|mainForm|mainPane|createBarWrapForm|createAndOrganizeForm|createAndOrganizeTabs|Bins" true;')
        thisBin = pc.Mel.eval('hyperShadeCreateNewBin("hyperShadePanel1Window|TearOffPane|hyperShadePanel1|mainForm|mainPane|createBarWrapForm|createAndOrganizeForm|createAndOrganizeTabs|Bins|binsScrollLayout|binsGridLayout", "%s")' %binName) if new else binName
    for path in paths:
        if op.exists(path):
            for sg in objFilter(pc.nt.ShadingEngine,
                                importScene(paths = [path], new = False)):
                pc.Mel.eval('hyperShadeAddNodeAndUpstreamNodesToBin("%s", "%s")'%(thisBin, str(sg)))

def createFileNodes(paths=[]):
    for path in paths:
        if op.exists(path):
            # createNodes and setAttrs
            fileNode = pc.shadingNode('file', asTexture=True)
            pc.setAttr(str(fileNode)+".ftn", path)
            placeNode = pc.shadingNode('place2dTexture', asUtility=True)

            # default connect placeNode and fileNode
            placeNode.coverage >> fileNode.coverage
            placeNode.translateFrame >> fileNode.translateFrame
            placeNode.rotateFrame >> fileNode.rotateFrame
            placeNode.mirrorU >> fileNode.mirrorU
            placeNode.mirrorV >> fileNode.mirrorV
            placeNode.stagger >> fileNode.stagger
            placeNode.wrapU >> fileNode.wrapU
            placeNode.wrapV >> fileNode.wrapV
            placeNode.repeatUV >> fileNode.repeatUV
            placeNode.offset >> fileNode.offset
            placeNode.rotateUV >> fileNode.rotateUV
            placeNode.noiseUV >> fileNode.noiseUV
            placeNode.vertexUvOne >> fileNode.vertexUvOne
            placeNode.vertexUvTwo >> fileNode.vertexUvTwo
            placeNode.vertexUvThree >> fileNode.vertexUvThree
            placeNode.vertexCameraOne >> fileNode.vertexCameraOne
            placeNode.outUV >> fileNode.uv
            placeNode.outUvFilterSize >> fileNode.uvFilterSize

def applyShaderToSelection(path):
    '''
    applies a shader to selected mesh in the current scene
    @params:
        @path: path to a maya file, which contains a shader
    '''
    try:
        if op.exists(path):
            sgs = objFilter(pc.nt.ShadingEngine, importScene(paths = [path], new = False))
            for sg in sgs:
                pc.hyperShade(assign = sg)
                break
            if len(sgs) > 1:
                pc.warning("Number of shader were more then one but only applied " + str(sg))
    except ShaderApplicationError as e:
        print e
        raise e

def make_cache(objs, frame_in, frame_out, directory, naming):
    '''
    :objs: list of sets and mesh whose cache is to be generated
    :frame_in: start frame of the cache
    :frame_out: end frame of the cache
    :directory: the directory in which the caches are to be dumped
    :naming: name of each obj's cache file. List of strings (order important)
    '''
    selection = pc.ls(sl = True)
    flags = {"version": 5,
             # whether to use the time slider as the range for which the
             # cache is generated
             "time_range_mode": 0,
             "start_time": frame_in,
             "end_time": frame_out,
             "cache_file_dist": "OneFile",
             "refresh_during_caching": 0,
             "cache_dir": directory.replace('\\', "/"),
             "cache_per_geo": "1",
             "cache_name": "foobar",
             "cache_name_as_prefix": 0,
             "action_to_perform": "export",
             "force_save": 0,
             "simulation_rate": 1,
             "sample_multiplier": 1,
             "inherit_modf_from_cacha": 0,
             "store_doubles_as_float":1,
             "cache_format": "mcc"}

    combineMeshes = []
    curSelection = []
    pc.select(cl=True)
    for objectSet in objs:
        if (type(pc.PyNode(objectSet)) == pc.nt.ObjectSet):
            pc.select(pc.PyNode(objectSet).members())
            meshes = [shape
                      for transform in pc.PyNode(objectSet).dsm.inputs(
                              type = "transform")
                      for shape in transform.getShapes(type = "mesh",
                                                    ni = True)]

            combineMesh = pc.createNode("mesh")
            pc.rename(combineMesh, objectSet.split(":")[-1]+"_tmp_cache"
                      if objectSet.split(':') else combineMesh)
            combineMeshes.append(combineMesh)
            polyUnite = pc.createNode("polyUnite")
            print meshes
            for i in xrange(len(meshes)):
                meshes[i].outMesh >> polyUnite.inputPoly[i]
                meshes[i].worldMatrix[0] >> polyUnite.inputMat[i]

            polyUnite.output >> combineMesh.inMesh
            pc.select(cl=True)
            objectSet = combineMesh
        elif type(pc.PyNode(objectSet)) == pc.nt.Transform:
            objectSet = objectSet.getShape(ni=True)
        elif type(pc.PyNode(objectSet))!=pc.nt.Mesh:
            continue

        curSelection.append(objectSet)
        pc.select(curSelection)
    try:
        command =  'doCreateGeometryCache2 {version} {{ "{time_range_mode}", "{start_time}", "{end_time}", "{cache_file_dist}", "{refresh_during_caching}", "{cache_dir}", "{cache_per_geo}", "{cache_name}", "{cache_name_as_prefix}", "{action_to_perform}", "{force_save}", "{simulation_rate}", "{sample_multiplier}", "{inherit_modf_from_cacha}", "{store_doubles_as_float}", "{cache_format}"}};'.format(**flags)
        print command
        caches = pc.Mel.eval(command)

        if naming and len(naming) == len(objs) == len(caches):

            for index in range(len(naming)):
                dir = op.dirname(caches[index])
                path_no_ext = op.splitext(caches[index])[0]
                os.rename(path_no_ext + '.mc',
                          op.join(dir, naming[index])
                          + '.mc')
                os.rename(path_no_ext + '.xml',
                          op.join(dir, naming[index])
                          + '.xml')

                map(caches.append, (op.join(dir, naming[index]) + '.xml',
                                    op.join(dir, naming[index]) + '.mc'))

            caches = caches[len(naming):]
    finally:
        print combineMeshes
        pc.delete(map(lambda x: x.getParent(),combineMeshes))
        pc.select(selection)
        # pc.informBox("Exported",
        #              "All meshes in the list have been exported", "OK")

    return caches

def openFile(filename):
    if op.exists(filename):
        if op.isfile(filename):
            ext = op.splitext(filename)[-1]
            if ext in ['.ma', '.mb']:
                typ = 'mayaBinary' if ext == '.mb' else 'mayaAscii'
                pc.mel.eval("file -f -options \"v=0;\" -ignoreVersion -prompt 0 -loadReferenceDepth \"all\"  -typ \"%s\" -o \"%s\";"%(typ, filename.replace('\\', '/')))
            else:
                pc.warning('Specified path is not a maya file: %s'%filename)
        else:
            pc.warning('Specified path is not a file: %s'%filename)
    else:
        pc.warning('File path does not exist: %s'%filename)

def saveSceneAs(path):
    cmds.file(rename=path)
    cmds.file(save=True)

def save_scene(ext):
    type = 'mayaBinary' if ext == '.mb' else 'mayaAscii'
    cmds.file(save=True, type=type)

def maya_version():
    return int(re.search('\\d{4}', pc.about(v=True)).group())

def is_modified():
    return cmds.file(q=True, modified=True)

def get_file_path():
    return cmds.file(q=True, location=True)

def rename_scene(name):
    cmds.file(rename=name)

def findUIObjectByLabel(parentUI, objType, label, case=True):
    try:
        if not case:
            label = label.lower()
        try:
            parentUI = pc.uitypes.Layout(parentUI)
        except:
            parentUI = pc.uitypes.Window(parentUI)

        for child in parentUI.getChildren():
            child
            if isinstance(child, objType):
                thislabel = child.getLabel()
                if not case:
                    thislabel = thislabel.lower()

                if label in thislabel:
                    return child
            if isinstance(child, pc.uitypes.Layout):
                obj = findUIObjectByLabel(child, objType, label, case)
                if obj:
                    return obj

    except Exception as e:
        print parentUI, e
        return None

def getProjectPath():
    return pc.workspace(q=True, o=True)

def setProjectPath(path):
    if op.exists(path):
        pc.workspace(e=True, o=path)
        return True

def getCameras(renderableOnly=True, ignoreStartupCameras=True,
        allowOrthographic=True):
    return [cam  for cam in pc.ls(type='camera')
            if ((not renderableOnly or cam.renderable.get()) and
                (allowOrthographic or not cam.orthographic.get()) and
                (not ignoreStartupCameras or not cam.getStartupCamera()))]

def isAnimationOn():
    return pc.SCENE.defaultRenderGlobals.animation.get()

def currentRenderer():
    renderer = pc.SCENE.defaultRenderGlobals.currentRenderer.get()
    if renderer == '_3delight':
        renderer = '3delight'
    return renderer

def toggleTextureMode(val):
    for panel in pc.getPanel(type='modelPanel'):
        me = pc.modelPanel(panel, q=True, me=True)
        pc.modelEditor(me, e=True, displayAppearance='smoothShaded')
        pc.modelEditor(me, e=True, dtx=val)

def getRenderLayers(nonReferencedOnly=True, renderableOnly=True):
    return [layer for layer in pc.ls(exactType='renderLayer')
            if ((not nonReferencedOnly or not layer.isReferenced()) and
                    (not renderableOnly or layer.renderable.get())) and
            not (re.match(r'.+defaultRenderLayer\d*', str(layer)) or
            re.match(r'.*defaultRenderLayer\d+', str(layer)))]

def getResolution():
    res = ( 320, 240 )
    if currentRenderer() != "vray":
        renderGlobals = pc.ls(renderGlobals=True)
        if renderGlobals:
            resNodes = renderGlobals[0].resolution.inputs()
            if resNodes:
                res = (resNodes[0].width.get(), resNodes[0].height.get())
    else:
        res = (pc.SCENE.vraySettings.width.get(),
                pc.SCENE.vraySettings.height.get())
    return res


def getImageFilePrefix():
    prefix = ""
    if currentRenderer != "vray":
        prefix = pc.SCENE.defaultRenderGlobals.imageFilePrefix.get()
    else:
        prefix = pc.SCENE.vraySettings.fileNamePrefix.get()
    if not prefix:
        prefix = op.splitext(op.basename(get_file_path()))[0]
    return prefix


def getRenderPassNames(enabledOnly=True, nonReferencedOnly=True):
    renderer = currentRenderer()
    if renderer == 'arnold':
        return [aov.attr('name').get() for aov in pc.ls(type='aiAOV')
                if ((not enabledOnly or aov.enabled.get()) and
                    (not nonReferencedOnly or not aov.isReferenced()))]
    elif renderer == 'redshift':
        if not pc.attributeQuery('name', type='RedshiftAOV', exists=True):

            aovs = [aov.attr('aovType').get() for aov in pc.ls(type='RedshiftAOV')
                    if ((not enabledOnly or aov.enabled.get()) and
                        (not nonReferencedOnly or not aov.isReferenced()))]

            finalaovs = set()
            for aov in aovs:
                aov = aov.replace(" ", "")
                newaov = aov
                count = 1
                while newaov in finalaovs:
                    newaov = aov + str(count)
                    count += 1
                finalaovs.add(newaov)
            return list(finalaovs)
        else:
            return [aov.attr('name').get() for aov in pc.ls(type='RedshiftAOV')
                    if ((not enabledOnly or aov.enabled.get()) and
                        (not nonReferencedOnly or not aov.isReferenced()))]


    else:
        return []

frameno_re = re.compile(r'\d+')
renderpass_re = re.compile('<renderpass>', re.I)
aov_re = re.compile('<aov>', re.I)
def removeLastNumber(path, bychar='?'):
    numbers = frameno_re.findall(path)
    if numbers:
        pos = path.rfind(numbers[-1])
        path = path[:pos] + path[pos:].replace(numbers[-1],  bychar * len(numbers[-1]))
        return path, numbers[-1]
    return path, ''


def resolveAOVsInPath(path, layer, cam, framePadder='?'):
    paths = []
    renderer = currentRenderer()

    if renderer == 'redshift':
        print path, type(path)
        beauty = renderpass_re.sub('Beauty', path)
        beauty = aov_re.sub('Beauty', beauty )
        paths.append(beauty)

        tokens = OrderedDict()

        tokens['<beautypath>']=op.dirname(path)

        basename = op.basename(path)
        number = ''
        if isAnimationOn():
            basename, number = removeLastNumber(basename, '')
        basename = op.splitext(basename)[0]
        if basename.endswith('.'):
            basename = basename[:-1]
        tokens['<beautyfile>']=basename
        if cam:
            camera = re.sub(r'\.|:', '_', str(cam.firstParent()))
        else:
            camera = ''

        tokens['<camera>']=camera
        tokens['<layer>']=re.sub(r'\.|:', '_', str(layer))
        tokens['<renderlayer>'] = tokens['<layer>']

        sceneName, ext=op.splitext(op.basename(pc.sceneName()))
        if not sceneName:
            sceneName = pc.untitledFileName()
        tokens['<scene>']=sceneName

        renderpasses = set()
        for aov in filter(lambda x:x.enabled.get(), pc.ls(type='RedshiftAOV')):

            newpath = aov.filePrefix.get()

            if pc.attributeQuery('name', n=aov, exists=True):
                renderpass = aov.attr('name').get()
            else:
                renderpass = aov.aovType.get().replace(' ', '')
                count = 1
                rp = renderpass
                while rp in renderpasses:
                    rp = renderpass + str(count)
                    count +=1
                renderpass = rp
                renderpasses.add(renderpass)

            tokens['<renderpass>'] = tokens['<aov>'] = renderpass

            for key, value in tokens.items():
                if key and value:
                    newpath = re.compile(key, re.I).sub(value, newpath)

            newpath = newpath+('.' if number else '')+number+ext
            paths.append(newpath)


    elif renderer == 'arnold':
        if not renderpass_re.search(path):
            return [path]
        passes = getRenderPassNames()
        if not passes:
            passes = ['']
        for pas in passes:
            paths.append(renderpass_re.sub(pas, path))

    else:
        paths.append( aov_re.sub('', renderpass_re.sub('', path )))

    return paths


def getGenericImageName(layer=None, camera=None, resolveAOVs=True, framePadder='?'):
    gins = []

    path = None

    if currentRenderer() == 'redshift':
        path = pc.PyNode('redshiftOptions').imageFilePrefix.get()

    if path is None:
        if layer is None and camera is None:
            fin = pc.renderSettings(fin=True, lut=True)
        elif layer is None:
            fin = pc.renderSettings(fin=True, lut=True, camera=camera)
        elif camera is None:
            fin = pc.renderSettings(fin=True, lut=True, layer=layer)
        else:
            fin = pc.renderSettings(fin=True, lut=True, layer=layer, camera=camera)
        path = fin[0]


    if resolveAOVs:
        if not camera:
            cams = getCameras(True, False)
            if cams:
                camera = cams[0]
        gins = resolveAOVsInPath(
                path,
                layer if layer else pc.editRenderLayerGlobals(q=1, crl=1),
                camera if camera else '',
                framePadder)

    if not gins:
        gins = [path]
    if isAnimationOn():
        gins = [removeLastNumber(gin, framePadder)[0] for gin in gins]

    return gins


def getOutputFilePaths(renderLayer=None, useCurrentLayer=False,
        camera = None, useCurrentCamera=False, ignoreStartupCameras=True,
        switchToLayer=False, framePadder='?'):
    outputFilePaths = []

    renderLayers = None
    if renderLayer:
        renderLayers = [pc.nt.RenderLayer(renderLayer)]
    elif not useCurrentLayer:
        layers = getRenderLayers()
        if layers:
            renderLayers = layers
    if renderLayers is None:
        renderLayers = [None]

    for layer in renderLayers:

        if layer != pc.editRenderLayerGlobals(q=1, crl=1) and switchToLayer:
            pc.editRenderLayerGlobals(crl=layer)

        renderableCams = getCameras(True, ignoreStartupCameras)
        cameras = None
        if camera:
            cameras = [camera]
        elif not useCurrentCamera:
            if renderableCams:
                cameras = renderableCams
        if cameras is None:
            cameras = [getCameras(False, False)[0]]

        for cam in cameras:
            gins = getGenericImageName(layer=layer, camera=cam,
                    framePadder=framePadder)
            outputFilePaths.extend(gins)

    return outputFilePaths

def getImagesLocation(workspace=None):
    if workspace:
        return pc.workspace(workspace, en=pc.workspace(workspace,
            fre='images'))
    else:
        return pc.workspace(en=pc.workspace(fre='images'))

def getFrameRange():
    if isAnimationOn():
        frange = (pc.SCENE.defaultRenderGlobals.startFrame.get(),
                pc.SCENE.defaultRenderGlobals.endFrame.get(),
                pc.SCENE.defaultRenderGlobals.byFrameStep.get())
    else:
        frange = (pc.currentTime(q=1), pc.currentTime(q=1), 1)
    return frange

def getBitString():
    if pc.about(is64=True):
        return '64bit'
    return '32bit'

def setCurrentRenderLayer(layer):
    pc.editRenderLayerGlobals(crl=layer)

if __name__ == "__main__":
    for _ in xrange(1):
        snapshot()
    print "loaded"
