'''
Main file for library iMaya
'''

import os
import tempfile
import traceback
import re
import subprocess
from collections import OrderedDict

try:
    import pymel.core as pc
    import maya.cmds as cmds
except:
    pass

import iutil as util

from .references import referenceInfo
from .files import export, importScene, get_file_path
from .exceptions import ShaderApplicationError
from .utils import removeLastNumber


op = os.path
FPS_MAPPINGS = {'film (24 fps)': 'film', 'pal (25 fps)': 'pal'}


class ArbitraryConf(object):
    # iMaya depends on the following external attributes
    # provided here incase it is not overridden by the user
    local_drives = ['c:', 'd:', r'\\']
    presetGeo = {
            'camera': 'RenderCam',
            'geometry': 'SphereSurfaceShape',
            'path': r'r:\Pipe_Repo\Projects\DAM\Data\presetScene\ball.ma',
            'resolution': [256, 256]}

conf = ArbitraryConf()
userHome = op.expanduser('~')


def displaySmoothness(smooth=True):
    '''equivalent to pressing 1 and 3 after selecting geometry'''
    if smooth:
        pc.mel.eval(
                'displaySmoothness -divisionsU 3 -divisionsV 3 '
                '-pointsWire 16 -pointsShaded 4 -polygonObject 3;')
    else:
        pc.mel.eval(
                'displaySmoothness -divisionsU 0 -divisionsV 0 '
                '-pointsWire 4 -pointsShaded 1 -polygonObject 1;')


def createRedshiftProxy(path):
    node = pc.PyNode(pc.mel.redshiftCreateProxy()[0])
    node.fileName.set(path)
    return node


def createGPUCache(path):
    xformNode = pc.createNode('transform')
    pc.createNode('gpuCache', parent=xformNode).cacheFileName.set(path)
    pc.xform(xformNode, centerPivots=True)


def mc2mdd(mcPath):
    '''Converts a .mcc file to a .mdd file in the same directory'''
    # ___ define mdd path/name
    mddpath = op.splitext(mcPath)[0].replace('\\', '/')
    fps = '25'
    # ___ MC to PC2 to MDD
    mcName = op.basename(mddpath)
    mcPath = op.dirname(mddpath) + '/'
    pc2 = mddpath + ".pc2"
    pc.cacheFile(pc2=0, pcf=pc2, f=mcName, dir=mcPath)
    p = subprocess.Popen(
            ["R:\\Pipe_Repo\\Users\\Qurban\\applications\\PC2_MDD.exe", pc2,
                mddpath + ".mdd", fps], bufsize=2048, shell=True)
    p.wait()
    os.remove(pc2)


def addOptionVar(name, value, array=False):
    if type(value) == type(int):
        if array:
            pc.optionVar(iva=(name, value))
        else:
            pc.optionVar(iv=(name, value))
    elif isinstance(value, basestring):
        if array:
            pc.optionVar(sva=(name, value))
        else:
            pc.optionVar(sv=(name, value))


def getOptionVar(name):
    if pc.optionVar(exists=name):
        return pc.optionVar(q=name)


def setRenderableCamera(camera, append=False):
    '''truns the .renderable attribute on for the specified camera. Turns
    it off for all other cameras in the scene if append is set to True'''
    if not append:
        for cam in pc.ls(cameras=True):
            if cam.renderable.get():
                cam.renderable.set(False)
    camera.renderable.set(True)


def addCamera(name):
    camera = pc.camera(n='persp')
    camera = pc.ls(sl=True)[0]
    pc.rename(camera, name)
    return camera


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


def createShadingNode(typ):
    return pc.PyNode(
            pc.mel.eval(
                'createRenderNodeCB -asShader "surfaceShader" %s "";' % typ))


def switchToMasterLayer():
    if pc.editRenderLayerGlobals(
            q=True, currentRenderLayer=True).lower().startswith('default'):
        return
    for layer in getRenderLayers(renderableOnly=False):
        if layer.name().lower().startswith('default'):
            pc.editRenderLayerGlobals(currentRenderLayer=layer)
            break


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
                    raise TypeError(
                        node.name() + " does not contain a shape node")
            for obj in tempNode:
                if not obj.intermediateObject.get():
                    node = obj
        except:
            raise TypeError('Node must be an instance of pc.nt.Mesh')
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


def removeOptionVar(key, index=None):
    if index is not None:
        cmds.optionVar(rfa=(key, index))
    else:
        cmds.optionVar(rm=key)


def createComponentChecks():
    # Doesn't belong here. Should be purged.
    return any((util.localPath(path, conf.local_drives) for path in
                referenceInfo().values()))


def getShadingFileNodes(selection):
    return [fileNode for obj in cmds.ls(sl=selection, rn=False)
            for shader in filter(lambda hist: isinstance(hist,
                                                         pc.nt.ShadingEngine),
                                 pc.listHistory(obj, f=True))
            for fileNode in filter(lambda shaderHist: isinstance(shaderHist,
                                                                 pc.nt.File),
                                   getShadingEngineHistoryChain(shader))]


def imageInRenderView():
    ff = pc.getAttr('defaultRenderGlobals.imageFormat')
    pc.setAttr('defaultRenderGlobals.imageFormat', 32)
    render = pc.renderWindowEditor('renderView', e=1,
                                   wi=util.getTemp(suffix=".png"))
    pc.setAttr('defaultRenderGlobals.imageFormat', ff)
    return render[1]


def getShadingEngineHistoryChain(shader):
    chain = []
    sets = cmds.sets(str(shader), q=True)
    for inputs in map(lambda inp: getattr(
                                        pc.PyNode(shader), inp).inputs(),
                      ["vs", "ds", "ss"]):
        if inputs:
            chain.extend([x for x in pc.listHistory(inputs[0])
                         if not isinstance(x, pc.nt.Reference) and
                         ((x not in sets) if sets else True) and
                         not isinstance(x, pc.nt.GroupId)])
    return chain + [shader]

_pre = "D:\talha.ahmed\workspace\vim-home\pythonscripts\pyqt_mvc\scratch.py"


def _rendShader(shaderPath, renderImagePath, geometry=r"SphereSurfaceShape",
                cam="RenderCam", res=(256, 256),
                presetScenePath=_pre):
    rl = "1:masterLayer"
    mel = """
    setAttr vraySettings.vfbOn 0;
    setAttr defaultRenderLayer.renderable 1;
    setAttr defaultRenderGlobals.animation 0;
    setAttr vraySettings.relements_enableall 0;
    setAttr vraySettings.relements_separateFolders 0;
    file -r \\"{shaderPath}\\";
    $shader = ls(\\"-rn\\", \\"-type\\", \\"shadingEngine\\");
    connectAttr \\"{geometry}.iog\\" ($shader[0] + \\".dsm[0]\\");
    setAttr \\"vraySettings.vfbOn\\" 1;""".format(
            geometry=geometry,
            shaderPath=shaderPath.replace(r"\\", "\\").replace("\\", r"\\"))

    r = "vray"
    x, y = res
    rd = op.dirname(renderImagePath)
    basename = op.basename(renderImagePath)
    of = "png"
    rl = "1:masterLayer"
    status = util.silentShellCall(
            'render -r {r} -preRender "{mel}"  -of'
            '"{of}" -rd "{rd}" -im "{basename}" -x {x} -y {y} -rl {rl}'
            '"{path}"'.format(
                **{
                    "r": r,
                    "cam": cam,
                    "x": x,
                    "y": y,
                    "rd": rd,
                    "of": of,
                    "basename": basename,
                    "mel": mel,
                    "path": presetScenePath,
                    "rl": rl}))
    return status


def render(*arg, **kwarg):
    '''
    @return: path to render image and shader n/w that was exported. tuple
    '''
    selection = pc.ls(sl=True)
    try:
        if kwarg.get("sg"):
            presetGeo = conf.presetGeo
            with tempfile.NamedTemporaryFile(suffix=".ma") as fobj:
                shader = op.splitext(fobj.name)[0]
            pc.select(getShadingEngineHistoryChain(kwarg.get("sg").keys()[0]),
                      ne=True)
            pc.Mel.eval('file -type "mayaAscii"')
            print export(op.basename(shader),
                         op.dirname(shader),
                         selection=True,
                         pr=False)
            with tempfile.NamedTemporaryFile(suffix=".png") as fobj:
                renImage = op.splitext(fobj.name)[0]

            _rendShader(shader + ".ma",
                                 renImage,
                                 geometry=presetGeo["geometry"],
                                 cam=presetGeo["camera"],
                                 res=presetGeo["resolution"],
                                 presetScenePath=presetGeo["path"])
            # quick hack to avoid rendering image not found error
            result = (r"R:\Pipe_Repo\Projects\DAM\Data\prod\assets\test\myTestThings\textures\.archive\face.png\2012-09-05_14-08-49.747865\face.png", shader + ".ma")
            # result = (renImage + ".png", shader + ".ma")
            # if int(status) != 0 or not all(map(op.exists, result)):
            #     raise ExportError(obj = kwarg["sg"].keys()[0])

        else:
            pc.runtime.mayaPreviewRenderIntoNewWindow()
            result = imageInRenderView()
    except BaseException as e:
        traceback.print_exc()
        raise e
    finally:
        pc.select(selection, ne=True)
    return result


def snapshot(
        resolution=conf.presetGeo["resolution"],
        snapLocation=op.join(
            os.getenv("tmp"), str(int(util.randomNumber()*100000)))):
    image_format = pc.getAttr("defaultRenderGlobals.imageFormat")
    pc.setAttr("defaultRenderGlobals.imageFormat", 8)
    pc.playblast(frame=pc.currentTime(q=True), format='image',
                 cf=snapLocation.replace('\\', '/'), orn=0, v=0, wh=resolution,
                 p=100, viewer=0, offScreen=1)
    pc.setAttr("defaultRenderGlobals.imageFormat", image_format)
    return snapLocation


def selected():
    '''
    @return True, if selection exists in the current scene
    '''
    s = pc.ls(sl=True, dag=True, geometry=True)
    if s:
        return True
    else:
        return False


def getMeshes(selection=False):
    '''
    returns only meshes from the scene or selection
    '''
    meshSet = set()
    for mesh in pc.ls(sl=selection):
        if type(mesh) == pc.nt.Transform:
            try:
                m = mesh.getShape()
                if type(m) == pc.nt.Mesh:
                    meshSet.add(m)
            except AttributeError:
                pass
        elif type(mesh) == pc.nt.Mesh:
            meshSet.add(mesh)
        else:
            pass
    return list(meshSet)


def getShadingEngines(selection=False):
    '''
    returns the materials and shading engines
    @param:
        selection: if True, returns the materials and shading engines of
        selected meshes else all
    @return: dictionary {material: [shadingEngine1, shadingEngine2, ...]}
    '''
    sgMtl = {}
    sg = set()
    if selection:
        # meshes = getMeshes(selection = selection)
        meshes = pc.ls(sl=True, dag=True, type='mesh')
        otherNodes = pc.ls(sl=True, dep=True)
        meshes += otherNodes
        for mesh in meshes:
            for s in pc.listConnections(mesh, type='shadingEngine'):
                sg.add(s)
        sg.update(pc.ls(sl=True, type='shadingEngine'))
    else:
        sg.update(set(pc.ls(type='shadingEngine')))
    for x in sg:
        ss = x.surfaceShader.inputs()
        ds = x.displacementShader.inputs()
        vs = x.volumeShader.inputs()
        imgs = x.imageShader.inputs()

        if ss:
            mtl = ss[0]
        elif ds:
            mtl = ds[0]
        elif vs:
            mtl = vs[0]
        elif imgs:
            mtl = imgs[0]
        else:
            continue

        # x = str(x)
        mtl = str(mtl)
        if not mtl:
            continue
        if mtl in sgMtl:
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


def addShadersToBin(binName, paths=[], new=True):
    '''
    bin is a group of shaders
    '''
    if paths and any(map(op.exists, paths)):
        pc.runtime.HypershadeWindow()
        pc.Mel.eval('refreshHyperShadeBinsUI "hyperShadePanel1Window|TearOffPane|hyperShadePanel1|mainForm|mainPane|createBarWrapForm|createAndOrganizeForm|createAndOrganizeTabs|Bins" true;')
        thisBin = pc.Mel.eval('hyperShadeCreateNewBin("hyperShadePanel1Window|TearOffPane|hyperShadePanel1|mainForm|mainPane|createBarWrapForm|createAndOrganizeForm|createAndOrganizeTabs|Bins|binsScrollLayout|binsGridLayout", "%s")' % binName) if new else binName
    for path in paths:
        if op.exists(path):
            for sg in objFilter(pc.nt.ShadingEngine, importScene(paths=[path],
                                new=False)):
                pc.Mel.eval(
                        'hyperShadeAddNodeAndUpstreamNodesToBin("%s", "%s")' %
                        (thisBin, str(sg)))


def applyShaderToSelection(path):
    '''
    applies a shader to selected mesh in the current scene
    @params:
        @path: path to a maya file, which contains a shader
    '''
    try:
        if op.exists(path):
            sgs = objFilter(pc.nt.ShadingEngine, importScene(paths=[path],
                            new=False))
            for sg in sgs:
                pc.hyperShade(assign=sg)
                break
            if len(sgs) > 1:
                pc.warning(
                    "Number of shader were more then one but only applied " +
                    str(sg))
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
    selection = pc.ls(sl=True)
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
             "store_doubles_as_float": 1,
             "cache_format": "mcc"}

    combineMeshes = []
    curSelection = []
    pc.select(cl=True)
    for objectSet in objs:
        if (type(pc.PyNode(objectSet)) == pc.nt.ObjectSet):
            pc.select(pc.PyNode(objectSet).members())
            meshes = [shape
                      for transform in pc.PyNode(objectSet).dsm.inputs(
                              type="transform")
                      for shape in transform.getShapes(type="mesh", ni=True)]

            combineMesh = pc.createNode("mesh")
            pc.rename(combineMesh, objectSet.split(":")[-1]+"_tmp_cache"
                      if objectSet.split(':') else combineMesh)
            combineMeshes.append(combineMesh)
            polyUnite = pc.createNode("polyUnite")
            print meshes
            for i in xrange(len(meshes)):
                meshes[i].outMesh >> polyUnite.inputPoly[i]
                meshes[i].worldMatrix[
                        meshes[i].instanceNumber()] >> polyUnite.inputMat[i]

            polyUnite.output >> combineMesh.inMesh
            pc.select(cl=True)
            objectSet = combineMesh
        elif type(pc.PyNode(objectSet)) == pc.nt.Transform:
            objectSet = objectSet.getShape(ni=True)
        elif type(pc.PyNode(objectSet)) != pc.nt.Mesh:
            continue

        curSelection.append(objectSet)
        pc.select(curSelection)

    try:
        command = 'doCreateGeometryCache2 {version} {{ "{time_range_mode}", "{start_time}", "{end_time}", "{cache_file_dist}", "{refresh_during_caching}", "{cache_dir}", "{cache_per_geo}", "{cache_name}", "{cache_name_as_prefix}", "{action_to_perform}", "{force_save}", "{simulation_rate}", "{sample_multiplier}", "{inherit_modf_from_cacha}", "{store_doubles_as_float}", "{cache_format}"}};'.format(**flags)
        caches = pc.Mel.eval(command)

        if naming and len(naming) == len(objs) == len(caches):

            for index in range(len(naming)):
                dir = op.dirname(caches[index])
                path_no_ext = op.splitext(caches[index])[0]
                os.rename(path_no_ext + '.mc',
                          op.join(dir, naming[index]) + '.mc')
                os.rename(path_no_ext + '.xml',
                          op.join(dir, naming[index]) + '.xml')

                map(caches.append, (op.join(dir, naming[index]) + '.xml',
                                    op.join(dir, naming[index]) + '.mc'))

            caches = caches[len(naming):]

    finally:
        print combineMeshes
        pc.delete(map(lambda x: x.getParent(), combineMeshes))
        pc.select(selection)
        # pc.informBox("Exported",
        #              "All meshes in the list have been exported", "OK")

    return caches


def maya_version():
    return int(re.search('\\d{4}', pc.about(v=True)).group())


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


def getCameras(
        renderableOnly=True, ignoreStartupCameras=True,
        allowOrthographic=True):
    return [cam for cam in pc.ls(type='camera')
            if ((not renderableOnly or cam.renderable.get()) and
                (allowOrthographic or not cam.orthographic.get()) and
                (not ignoreStartupCameras or not cam.getStartupCamera()))]


def removeAllLights():
    for light in pc.ls(type='light'):
        try:
            pc.delete(light)
        except:
            pass


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


def toggleViewport2Point0(flag):
    '''Activates the Viewport 2.0 if flag is set to True'''
    panl = 'modelPanel4'
    for pan in pc.getPanel(allPanels=True):
        if pan.name().startswith('modelPanel'):
            if pc.modelEditor(pan, q=True, av=True):
                panl = pan.name()
    if flag:
        pc.mel.setRendererInModelPanel("ogsRenderer", panl)
    else:
        pc.mel.setRendererInModelPanel("base_OpenGL_Renderer", panl)


def getRenderLayers(nonReferencedOnly=True, renderableOnly=True):
    return [layer for layer in pc.ls(exactType='renderLayer')
            if ((not nonReferencedOnly or not layer.isReferenced()) and
                (not renderableOnly or layer.renderable.get())) and
            not (re.match(r'.+defaultRenderLayer\d*', str(layer)) or
            re.match(r'.*defaultRenderLayer\d+', str(layer)))]


def getResolution():
    res = (320, 240)
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


def getDisplayLayers():
    try:
        return [pc.PyNode(layer) for layer in
                pc.layout('LayerEditorDisplayLayerLayout', q=True,
                          childArray=True)]
    except TypeError:
        pc.warning('Display layers not found in the scene')
        return []


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

            aovs = [aov.attr('aovType').get()
                    for aov in pc.ls(type='RedshiftAOV')
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


def replaceTokens(tokens, path):
    for key, value in tokens.items():
        if key and value:
            path = re.compile(key, re.I).sub(value, path)
    return path

renderpass_re = re.compile('<renderpass>', re.I)
aov_re = re.compile('<aov>', re.I)


def resolveAOVsInPath(path, layer, cam, framePadder='?'):
    paths = []
    renderer = currentRenderer()

    if renderer == 'redshift':
        tokens = OrderedDict()

        tokens['<beautypath>'] = op.dirname(path)

        basename = op.basename(path)
        number = ''
        if isAnimationOn():
            basename, number = removeLastNumber(basename, '')
        basename = op.splitext(basename)[0]
        if basename.endswith('.'):
            basename = basename[:-1]
        tokens['<beautyfile>'] = basename
        if cam:
            camera = re.sub(r'\.|:', '_', str(cam.firstParent()))
        else:
            camera = ''

        tokens['<camera>'] = camera
        tokens['<layer>'] = re.sub(r'\.|:', '_', str(layer))
        tokens['<renderlayer>'] = tokens['<layer>']

        sceneName, _ = op.splitext(op.basename(pc.sceneName()))
        if not sceneName:
            sceneName = pc.untitledFileName()
        tokens['<scene>'] = sceneName

        beauty = renderpass_re.sub('Beauty', path)
        beauty = aov_re.sub('Beauty', beauty)
        beauty = replaceTokens(tokens, beauty)
        paths.append(beauty)

        renderpasses = set()
        for aov in filter(
                lambda x: x.enabled.get(), pc.ls(type='RedshiftAOV')):
            newpath = aov.filePrefix.get()
            extIndex = aov.fileFormat.get()

            if pc.attributeQuery('name', n=aov, exists=True):
                renderpass = aov.attr('name').get()
            else:
                renderpass = aov.aovType.get().replace(' ', '')
                count = 1
                rp = renderpass
                while rp in renderpasses:
                    rp = renderpass + str(count)
                    count += 1
                renderpass = rp
                renderpasses.add(renderpass)

            exts = ['.iff', '.exr', '.tif', '.png', '.tga', '.jpg']
            tokens['<renderpass>'] = tokens['<aov>'] = renderpass
            newpath = replaceTokens(tokens, newpath)
            newpath = newpath+('.' if number else '')+number+exts[extIndex]
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
        paths.append(aov_re.sub('', renderpass_re.sub('', path)))

    return paths


def getGenericImageName(
        layer=None, camera=None, resolveAOVs=True, framePadder='?'):
    gins = []

    path = None

    # if currentRenderer() == 'redshift':
    #     path = pc.PyNode('redshiftOptions').imageFilePrefix.get()

    if path is None:
        if layer is None and camera is None:
            fin = pc.renderSettings(fin=True, lut=True)
        elif layer is None:
            fin = pc.renderSettings(fin=True, lut=True, camera=camera)
        elif camera is None:
            fin = pc.renderSettings(fin=True, lut=True, layer=layer)
        else:
            fin = pc.renderSettings(
                    fin=True, lut=True, layer=layer, camera=camera)
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


def getOutputFilePaths(
        renderLayer=None, useCurrentLayer=False, camera=None,
        useCurrentCamera=False, ignoreStartupCameras=True, switchToLayer=False,
        framePadder='?'):
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
            gins = getGenericImageName(
                    layer=layer, camera=cam, framePadder=framePadder)
            outputFilePaths.extend(gins)

    return outputFilePaths


def getImagesLocation(workspace=None):
    if workspace:
        return pc.workspace(
                workspace, en=pc.workspace(workspace, fre='images'))
    else:
        return pc.workspace(en=pc.workspace(fre='images'))


def getFrameRange():
    if isAnimationOn():
        frange = (
                pc.SCENE.defaultRenderGlobals.startFrame.get(),
                pc.SCENE.defaultRenderGlobals.endFrame.get(),
                pc.SCENE.defaultRenderGlobals.byFrameStep.get())
    else:
        frange = (pc.currentTime(q=1), pc.currentTime(q=1), 1)
    return frange


def setCurrentRenderLayer(layer):
    pc.editRenderLayerGlobals(crl=layer)

# if __name__ == "__main__":
    # for _ in xrange(1):
    # snapshot()
    # print "loaded"
