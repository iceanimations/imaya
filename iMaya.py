# Date: Mon 26/11/2012

import os, sys, subprocess, tempfile, stat
import pymel.core as pc
import maya.cmds as cmds
import iutilities as util
import traceback
import base64
op = os.path

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
                              typ="mayaAscii",
                              pr = pr)
        else:
            pc.exportAll(path + ".ma", force = True,
                         typ = "mayaAscii", pr = pr)

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

def newScene(func):
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
    return wrapper

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
def addReference(paths=[], dup = True, *arg, **kwarg):
    '''
    adds reference to the component at 'path' (str)
    @params:
            path: valid path to the asset dir (str)
            component: (Rig, Model, Shaded Model) (str)
            dup: allow duplicate referencing
    '''
    for path in paths:
        # get the existing references
        if not dup and referenceExists(path) :
            cmds.file(path, loadReference = True)
        # create reference
        else:
            try:
                cmds.file(path, r = True)
            except RuntimeError:
                pc.error('file not found')

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

def textureFiles(selection = True, key = lambda x: True):

    '''
    @key: filter the tex with it
    '''

    texs = []
    fileNodes = getFileNodes(selection)

    texs += filter(key, (pc.getAttr(fNode + '.ftn') for fNode in fileNodes))

    for tex in texs[:]:
        if op.exists(tex):
            texs.extend(util.getSequenceFiles(tex))

    return texs

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

            status = _rendShader(shader + ".ma",
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

def snapshot():
    snapLocation = op.join(os.getenv("tmp"), str(int(util.randomNumber()*100000)))
    command = """float $currFrame = `currentTime -q`;
int $format = `getAttr "defaultRenderGlobals.imageFormat"`;
setAttr "defaultRenderGlobals.imageFormat" 8;
playblast -frame $currFrame -format "image" -cf "{image}" -orn 0 -v 0 -wh {res} -p 100;
setAttr "defaultRenderGlobals.imageFormat" $format;""".format(res =
                                                              " ".join(map(str, conf.presetGeo["resolution"])),
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

def openFile(path, f = False):
    pc.openFile(path, force = f)

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


if __name__ == "__main__":
    for _ in xrange(1):
        snapshot()
    print "loaded"
