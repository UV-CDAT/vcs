import cdutil
import warnings
import vtk
import vcs
from . import vcs2vtk
import numpy
import os
import traceback
import sys
import cdms2
import cdtime
import inspect
from . import VTKAnimate
from . import vcsvtk


def _makeEven(val):
    if (val & 0x1):
        val -= 1
    return val


def updateNewElementsDict(display, master):
    newelts = getattr(display, "newelements", {})
    for key in newelts:
        if key in master:
            master[key] += newelts[key]
        else:
            master[key] = newelts[key]
    return master


class VCSInteractorStyle(vtk.vtkInteractorStyleUser):

    def __init__(self, parent):
        self.AddObserver("LeftButtonPressEvent", parent.leftButtonPressEvent)
        self.AddObserver(
            "LeftButtonReleaseEvent",
            parent.leftButtonReleaseEvent)
        self.AddObserver("ConfigureEvent", parent.configureEvent)
        if sys.platform == "darwin":
            self.AddObserver("RenderEvent", parent.renderEvent)


class VTKVCSBackend(object):

    def __init__(self, canvas, renWin=None,
                 debug=False, bg=None):
        self._lastSize = None
        self.canvas = canvas
        self.renWin = renWin
        self.contextView = None
        self.debug = debug
        self.bg = bg
        self.type = "vtk"
        self.plotApps = {}
        self.plotRenderers = set()
        # Maps priorities to renderers
        self.text_renderers = {}
        self.logoRenderer = None
        self.logoRepresentation = None
        self.renderer = None
        self._renderers = {}
        self._plot_keywords = [
            'cdmsfile',
            'cell_coordinates',
            # dataset bounds in lon/lat coordinates
            'dataset_bounds',
            # This may be smaller than the data viewport. It is used
            # if autot is passed
            'ratio_autot_viewport',
            # used to render the dataset for clicked point info (hardware
            # selection)
            'surface_renderer',
            # (xScale, yScale) - datasets can be scaled using the window ratio
            'surface_scale',
            # the same as vcs.utils.getworldcoordinates for now. getworldcoordinates uses
            # gm.datawc_... or, if that is not set, it uses data axis margins
            # (without bounds).
            'plotting_dataset_bounds',
            # dataset bounds before masking
            'vtk_dataset_bounds_no_mask',
            'renderer',
            'vtk_backend_grid',
            # vtkGeoTransform used for geographic transformation
            'vtk_backend_geo',
            # "vtk_backend_pipeline_context_area",
            "vtk_backend_viewport_scale",
            "vtk_backend_draw_area_bounds",
        ]
        self.numberOfPlotCalls = 0
        self.renderWindowSize = None
        self.clickRenderer = None
        # Turn on anti-aliasing by default
        # Initially set to 16x Multi-Sampled Anti-Aliasing
        self.antialiasing = 8

        if renWin is not None:
            self.renWin = renWin
            if renWin.GetInteractor() is None and self.bg is False:
                self.createDefaultInteractor()

        if sys.platform == "darwin":
            self.reRender = False
            self.oldCursor = None

        self._animationActorTransforms = {}

    def setAnimationStepper(self, stepper):
        for plot in list(self.plotApps.values()):
            plot.setAnimationStepper(stepper)

    def interact(self, *args, **kargs):
        if self.renWin is None:
            warnings.warn("Cannot interact if you did not open the canvas yet")
            return
        interactor = self.renWin.GetInteractor()
        # Mac seems to handle events a bit differently
        # Need to add observers on renWin
        # Linux is fine w/o it so no need to do it
        if sys.platform == "darwin":
            self.renWin.AddObserver("RenderEvent", self.renderEvent)
            self.renWin.AddObserver(
                "LeftButtonPressEvent",
                self.leftButtonPressEvent)
            self.renWin.AddObserver(
                "LeftButtonReleaseEvent",
                self.leftButtonReleaseEvent)
            self.renWin.AddObserver("ConfigureEvent", self.configureEvent)
            self.renWin.AddObserver("EndEvent", self.endEvent)
        if interactor is None:
            warnings.warn("Cannot start interaction. Blank plot?")
            return
        warnings.warn(
            "Press 'Q' to exit interactive mode and continue script execution")
        self.showGUI()
        interactor.Start()

    def endEvent(self, obj, event):
        if self.renWin is not None:
            if self.reRender:
                self.reRender = False
                self.renWin.Render()

    def renderEvent(self, caller, evt):
        renwin = self.renWin if (caller is None) else caller
        window_size = renwin.GetSize()
        if (window_size != self.renderWindowSize):
            self.configureEvent(caller, evt)
            self.renderWindowSize = window_size

    def leftButtonPressEvent(self, obj, event):
        xy = self.renWin.GetInteractor().GetEventPosition()
        sz = self.renWin.GetSize()
        x = float(xy[0]) / sz[0]
        y = float(xy[1]) / sz[1]
        st = ""
        for dnm in self.canvas.display_names:
            d = vcs.elements["display"][dnm]
            if d.array[0] is None:
                continue
            # Use the hardware selector to determine the cell id we clicked on
            selector = vtk.vtkHardwareSelector()
            if 'surface_renderer' in d.backend:
                surfaceRenderer = d.backend['surface_renderer']
            else:
                print('No "surface_renderer" in display backend')
                return
            dataset = d.backend['vtk_backend_grid']
            if (surfaceRenderer and dataset):
                selector.SetRenderer(surfaceRenderer)
                selector.SetArea(xy[0], xy[1], xy[0], xy[1])
                selector.SetFieldAssociation(
                    vtk.vtkDataObject.FIELD_ASSOCIATION_CELLS)
                # We only want to render the surface for selection
                renderers = self.renWin.GetRenderers()
                renderers.InitTraversal()
                while(True):
                    renderer = renderers.GetNextItem()
                    if (renderer is None):
                        break
                    renderer.SetDraw(False)
                surfaceRenderer.SetDraw(True)

                selection = selector.Select()
                renderers.InitTraversal()
                while(True):
                    renderer = renderers.GetNextItem()
                    if (renderer is None):
                        break
                    renderer.SetDraw(True)
                surfaceRenderer.SetDraw(False)
                if (selection.GetNumberOfNodes() > 0):
                    selectionNode = selection.GetNode(0)
                    prop = selectionNode.GetProperties().Get(selectionNode.PROP())
                    if (prop):
                        cellIds = prop.GetMapper().GetInput().GetCellData().GetGlobalIds()
                        if (cellIds):
                            st += "Var: %s\n" % d.array[0].id
                            # cell attribute
                            a = selectionNode.GetSelectionData().GetArray(0)
                            geometryId = a.GetValue(0)
                            cellId = cellIds.GetValue(geometryId)
                            attributes = dataset.GetCellData().GetScalars()
                            if (attributes is None):
                                attributes = dataset.GetCellData().GetVectors()
                            elementId = cellId

                            geoTransform = d.backend['vtk_backend_geo']
                            if (geoTransform):
                                geoTransform.Inverse()
                            # Use the world picker to get world coordinates
                            # we deform the dataset, so we need to fix the
                            # world picker using xScale, yScale
                            xScale, yScale = d.backend['surface_scale']
                            worldPicker = vtk.vtkWorldPointPicker()
                            worldPicker.Pick(xy[0], xy[1], 0, surfaceRenderer)
                            worldPosition = list(worldPicker.GetPickPosition())
                            lonLat = worldPosition
                            if (attributes is None):
                                # if point dataset, return the value for the
                                # closest point
                                cell = dataset.GetCell(cellId)
                                closestPoint = [0, 0, 0]
                                subId = vtk.mutable(0)
                                pcoords = [0, 0, 0]
                                dist2 = vtk.mutable(0)
                                weights = [0] * cell.GetNumberOfPoints()
                                cell.EvaluatePosition(worldPosition, closestPoint,
                                                      subId, pcoords, dist2, weights)
                                indexMax = numpy.argmax(weights)
                                pointId = cell.GetPointId(indexMax)
                                attributes = dataset.GetPointData().GetScalars()
                                if (attributes is None):
                                    attributes = dataset.GetPointData().GetVectors()
                                elementId = pointId
                            if (geoTransform):
                                geoTransform.InternalTransformPoint(
                                    worldPosition, lonLat)
                                geoTransform.Inverse()
                            if (float("inf") not in lonLat):
                                st += "X=%4.1f\nY=%4.1f\n" % (
                                    lonLat[0], lonLat[1])
                            # get the cell value or the closest point value
                            if (attributes):
                                if (attributes.GetNumberOfComponents() > 1):
                                    v = attributes.GetTuple(elementId)
                                    st += "Value: (%g, %g)" % (v[0], v[1])
                                else:
                                    value = attributes.GetValue(elementId)
                                    st += "Value: %g" % value

        if st == "":
            return
        ren = vtk.vtkRenderer()
        ren.SetBackground(.96, .96, .86)
        ren.SetViewport(x, y, min(x + .2, 1.), min(y + .2, 1))
        ren.SetLayer(self.renWin.GetNumberOfLayers() - 1)
        self.renWin.AddRenderer(ren)
        a = vtk.vtkTextActor()
        a.SetInput(st)
        p = a.GetProperty()
        p.SetColor(0, 0, 0)
        bb = [0, 0, 0, 0]
        a.GetBoundingBox(ren, bb)
        ps = vtk.vtkPlaneSource()
        ps.SetCenter(bb[0], bb[2], 0.)
        ps.SetPoint1(bb[1], bb[2], 0.)
        ps.SetPoint2(bb[0], bb[3], 0.)
        ps.Update()
        m2d = vtk.vtkPolyDataMapper2D()
        m2d.SetInputConnection(ps.GetOutputPort())
        a2d = vtk.vtkActor2D()
        a2d.SetMapper(m2d)
        a2d.GetProperty().SetColor(.93, .91, .67)
        ren.AddActor(a2d)
        ren.AddActor(a)
        ren.ResetCamera()
        self.clickRenderer = ren
        self.renWin.Render()

    def leftButtonReleaseEvent(self, obj, event):
        if self.clickRenderer is not None:
            self.clickRenderer.RemoveAllViewProps()
            self.renWin.RemoveRenderer(self.clickRenderer)
            self.renWin.Render()
            self.clickRenderer = None

    def configureEvent(self, obj, ev):
        if not self.renWin:
            return

        if self.get3DPlot() is not None:
            return

        sz = self.renWin.GetSize()
        if self._lastSize == sz:
            # We really only care about resize event
            # this is mainly to avoid segfault vwith Vistraisl which does
            # not catch configure Events but only modifiedEvents....
            return

        self._lastSize = sz
        plots_args = []
        key_args = []

        new = {}
        original_displays = list(self.canvas.display_names)
        for dnm in self.canvas.display_names:
            d = vcs.elements["display"][dnm]
            # displays keep a reference of objects that were internally created
            # so that we can clean them up
            # it is stored in display.newelements
            # here we compile the list of all these objects
            new = updateNewElementsDict(d, new)

            # Now we need to save all that was plotted so that we can replot
            # on the new sized template
            # that includes keywords passed
            parg = []
            if d.g_type in ["text", "textcombined"]:
                continue
            for a in d.array:
                if a is not None:
                    parg.append(a)
            parg.append(d._template_origin)
            parg.append(d.g_type)
            parg.append(d.g_name)
            plots_args.append(parg)
            # remember display used so we cna re-use
            key = {"display_name": dnm}
            if d.ratio is not None:
                key["ratio"] = d.ratio
            key["continents"] = d.continents
            key["continents_line"] = d.continents_line
            key_args.append(key)

        # Have to pull out the UI layer so it doesn't get borked by the z
        self.hideGUI()

        if self.canvas.configurator is not None:
            restart_anim = self.canvas.configurator.animation_timer is not None
        else:
            restart_anim = False

        # clear canvas no render and preserve display
        # so that we can replot on same display object
        self.canvas.clear(render=False, preserve_display=True)

        # replots on new sized canvas
        for i, pargs in enumerate(plots_args):
            self.canvas.plot(*pargs, render=False, **key_args[i])

        # compiled updated list of all objects created internally
        for dnm in self.canvas.display_names:
            d = vcs.elements["display"][dnm]
            new = updateNewElementsDict(d, new)

        # Now clean the object created internally that are no longer
        # in use
        for e in new:
            if e == "display":
                continue
            # Loop for all types
            for k in new[e]:
                # Loop through all elements created internally for that type
                if k in vcs.elements[e]:
                    found = False
                    # Loop through all existing displays
                    for d in list(vcs.elements["display"].values()):
                        if d.g_type == e and d.g_name == k:
                            # Ok this is still in use on some display
                            found = True
                    # object is no longer associated with any display
                    # and it was created internally
                    # we can safely remove it
                    if not found:
                        del(vcs.elements[e][k])

        # Only keep original displays since we replotted on them
        for dnm in self.canvas.display_names:
            if dnm not in original_displays:
                del(vcs.elements["display"][dnm])
        # restore original displays
        self.canvas.display_names = original_displays

        if self.canvas.animate.created() and self.canvas.animate.frame_num != 0:
            self.canvas.animate.draw_frame(
                allow_static=False,
                render_offscreen=False)

        self.showGUI(render=False)
        if self.renWin.GetSize() != (0, 0):
            self.scaleLogo()
        if restart_anim:
            self.canvas.configurator.start_animating()

    def clear(self, render=True):
        if self.renWin is None:  # Nothing to clear
            return
        renderers = self.renWin.GetRenderers()
        renderers.InitTraversal()
        ren = renderers.GetNextItem()
        self.text_renderers = {}
        hasValidRenderer = True if ren is not None else False

        for gm in self.plotApps:
            app = self.plotApps[gm]
            app.plot.quit()

        self.hideGUI()
        # while ren is not None:
        #     ren.RemoveAllViewProps()
        #     if not ren.GetLayer() == 0:
        #         self.renWin.RemoveRenderer(ren)
        #     else:
        #         # Update background color
        #         r, g, b = [c / 255. for c in self.canvas.backgroundcolor]
        #         ren.SetBackground(r, g, b)
        #     ren = renderers.GetNextItem()
        if self.contextView:
            self.contextView.GetScene().ClearItems()
            r, g, b = [c / 255. for c in self.canvas.backgroundcolor]
            self.contextView.GetRenderer().SetBackground(r, g, b)
        self._animationActorTransforms = {}
        self.showGUI(render=False)

        if hasValidRenderer and self.renWin.IsDrawable() and render:
            self.renWin.Render()
        self.numberOfPlotCalls = 0
        self.logoRenderer = None
        self.createLogo()
        self._renderers = {}

    def createDefaultInteractor(self, ren=None):
        defaultInteractor = self.renWin.GetInteractor()
        if defaultInteractor is None:
            if self.bg:
                # this is only used to pass event to vtk objects
                # it does not listen to events form the window
                # it is used in vtkweb
                defaultInteractor = vtk.vtkGenericRenderWindowInteractor()
            else:
                defaultInteractor = vtk.vtkRenderWindowInteractor()
        self.vcsInteractorStyle = VCSInteractorStyle(self)
        if ren:
            self.vcsInteractorStyle.SetCurrentRenderer(ren)
        defaultInteractor.SetInteractorStyle(self.vcsInteractorStyle)
        defaultInteractor.SetRenderWindow(self.renWin)
        self.vcsInteractorStyle.On()

    def createRenWin(self, *args, **kargs):
        if self.contextView is None:
            self.contextView = vtk.vtkContextView()

        if self.renWin is None:
            self.renWin = self.contextView.GetRenderWindow()

            self.renWin.SetWindowName("VCS Canvas %i" % self.canvas._canvas_id)
            self.renWin.SetAlphaBitPlanes(1)
            # turning on Stencil for Labels on iso plots
            self.renWin.SetStencilCapable(1)
            # turning off antialiasing by default
            # mostly so that pngs are same accross platforms
            self.renWin.SetMultiSamples(self.antialiasing)

            width = self.canvas.width
            height = self.canvas.height

            if "width" in kargs and kargs["width"] is not None:
                width = kargs["width"]
            if "height" in kargs and kargs["height"] is not None:
                height = kargs["height"]
            self.initialSize(width, height)

        if self.renderer is None:
            self.renderer = self.contextView.GetRenderer()
            r, g, b = [c / 255. for c in self.canvas.backgroundcolor]
            self.renderer.SetBackground(r, g, b)
            self.createDefaultInteractor(self.renderer)

        if self.bg:
            self.renWin.SetOffScreenRendering(True)

        if "open" in kargs and kargs["open"]:
            self.renWin.Render()

    def createRenderer(self, *args, **kargs):
        if not self.renderer:
            self.createRenWin(*args, **kargs)
        return self.renderer

    def update(self, *args, **kargs):
        self._lastSize = None
        if self.renWin:
            if self.get3DPlot():
                plots_args = []
                key_args = []
                for dnm in self.canvas.display_names:
                    d = vcs.elements["display"][dnm]
                    parg = []
                    for a in d.array:
                        if a is not None:
                            parg.append(a)
                    parg.append(d._template_origin)
                    parg.append(d.g_type)
                    parg.append(d.g_name)
                    plots_args.append(parg)
                    if d.ratio is not None:
                        key_args.append({"ratio": d.ratio})
                    else:
                        key_args.append({})
                for i, args in enumerate(plots_args):
                    self.canvas.plot(*args, **key_args[i])
            else:
                self.configureEvent(None, None)

    def canvasinfo(self):
        if self.renWin is None:
            mapstate = False
            width = self.canvas.width
            height = self.canvas.height
            depth = None
            x = 0
            y = 0
        else:
            try:  # mac but not linux
                mapstate = self.renWin.GetWindowCreated()
            except Exception:
                mapstate = True
            width, height = self.renWin.GetSize()
            depth = self.renWin.GetDepthBufferSize()
            try:  # mac not linux
                x, y = self.renWin.GetPosition()
            except Exception:
                x, y = 0, 0
        info = {
            "mapstate": mapstate,
            "height": height,
            "width": width,
            "depth": depth,
            "x": x,
            "y": y,
        }
        return info

    def orientation(self, *args, **kargs):
        canvas_info = self.canvasinfo()
        w = canvas_info["width"]
        h = canvas_info["height"]
        if w > h:
            return "landscape"
        else:
            return "portrait"

    def resize_or_rotate_window(self, W=-99, H=-99, x=-99, y=-99, clear=0):
        # Resize and position window to the provided arguments except when the
        # values are default and negative. In the latter case, it should just
        # rotate the window.
        if clear:
            self.clear()
        if self.renWin is None:
            if W != -99:
                self.canvas.width = W
                self.canvas.height = H
            else:
                W = self.canvas.width
        else:
            self.setsize(W, H)
            self.canvas.width = W
            self.canvas.height = H

    def portrait(self, W=-99, H=-99, x=-99, y=-99, clear=0):
        self.resize_or_rotate_window(W, H, x, y, clear)

    def landscape(self, W=-99, H=-99, x=-99, y=-99, clear=0):
        self.resize_or_rotate_window(W, H, x, y, clear)

    def initialSize(self, width=None, height=None):
        import vtkmodules
        if hasattr(vtkmodules.vtkRenderingOpenGL2Python, "vtkXOpenGLRenderWindow") and\
                isinstance(self.renWin, vtkmodules.vtkRenderingOpenGL2Python.vtkXOpenGLRenderWindow):
            if os.environ.get("DISPLAY", None) is None:
                raise RuntimeError("No DISPLAY set. Set your DISPLAY env variable or install mesalib conda package")

        # Gets user physical screen dimensions
        if isinstance(width, int) and isinstance(height, int):
            self.setsize(width, height)
            self._lastSize = (width, height)
            return

        screenSize = self.renWin.GetScreenSize()
        try:
            # following works on some machines but not all
            # Creates the window to be 60% of user's screen's width
            cw = int(screenSize[0] * .6)
            ch = int(cw / self.canvas.size)
            if ch > screenSize[1]:
                # If still too big use 60% of height
                # typical case: @doutriaux1 screens
                ch = int(screenSize[1] * .6)
                cw = int(ch * self.canvas.size)
        except Exception:
            cw = self.canvas.width
        # Respect user chosen aspect ratio
        ch = int(cw / self.canvas.size)
        # Sets renWin dimensions
        # make the dimensions even for Macs
        cw = _makeEven(cw)
        ch = _makeEven(ch)
        self.canvas.width = cw
        self.canvas.height = ch
        self.setsize(cw, ch)
        self._lastSize = (cw, ch)

    def open(self, width=None, height=None, **kargs):
        self.createRenWin(open=True, width=width, height=height)

    def close(self):
        if self.renWin is None:
            return
        self.clear()
        self.renWin.Finalize()
        self.renWin = None

    def isopened(self):
        if self.renWin is None:
            return False
        elif self.renWin.GetOffScreenRendering() and self.bg:
            # IN bg mode
            return False
        else:
            return True

    def geometry(self, *args):
        if len(args) == 0:
            return {'width': self.canvas.width, 'height': self.canvas.height}
        if len(args) < 2:
            raise TypeError("Function takes zero or two <width, height> "
                            "or more than two arguments. Got " + len(*args))
        x = args[0]
        y = args[1]

        self.canvas.width = x
        self.canvas.height = y
        if self.renWin is not None:
            self.setsize(x, y)
        self._lastSize = (x, y)

    def setsize(self, x, y):
        self.renWin.SetSize(x, y)
        self.configureEvent(None, None)

    def flush(self):
        if self.renWin is not None:
            self.renWin.Render()

    def plot(self, data1, data2, template, gtype, gname, bg, *args, **kargs):
        self.numberOfPlotCalls += 1
        # these are keyargs that can be reused later by the backend.
        returned = {}
        if self.bg is None:
            if bg:
                self.bg = True
            else:
                self.bg = False
        self.createRenWin(**kargs)
        if self.bg:
            self.renWin.SetOffScreenRendering(True)
        self.cell_coordinates = kargs.get('cell_coordinates', None)
        self.canvas.initLogoDrawing()
        if gtype == "text":
            tt, to = gname.split(":::")
            tt = vcs.elements["texttable"][tt]
            to = vcs.elements["textorientation"][to]
            gm = tt
        elif gtype in ("xvsy", "xyvsy", "yxvsx", "scatter"):
            gm = vcs.elements["1d"][gname]
        else:
            gm = vcs.elements[gtype][gname]
        tpl = vcs.elements["template"][template]

        if kargs.get("renderer", None) is None:
            if (gtype in ["3d_scalar", "3d_dual_scalar", "3d_vector"]) and (
                    self.renderer is not None):
                ren = self.renderer
        else:
            ren = kargs["renderer"]

        vtk_backend_grid = kargs.get("vtk_backend_grid", None)
        vtk_dataset_bounds_no_mask = kargs.get(
            "vtk_dataset_bounds_no_mask", None)
        vtk_backend_geo = kargs.get("vtk_backend_geo", None)
        bounds = vtk_dataset_bounds_no_mask if vtk_dataset_bounds_no_mask else None

        pipeline = vcsvtk.createPipeline(gm, self, kargs)
        if pipeline is not None:
            returned.update(pipeline.plot(data1, data2, tpl,
                                          vtk_backend_grid, vtk_backend_geo, **kargs))
        elif gtype in ["3d_scalar", "3d_dual_scalar", "3d_vector"]:
            cdms_file = kargs.get('cdmsfile', None)
            cdms_var = kargs.get('cdmsvar', None)
            if cdms_var is not None:
                raise Exception()
            if cdms_file is not None:
                gm.addPlotAttribute('file', cdms_file)
                gm.addPlotAttribute('filename', cdms_file)
                gm.addPlotAttribute('url', cdms_file)
            returned.update(self.plot3D(data1, data2, tpl, gm, ren, **kargs))
        elif gtype in ["text"]:
            if tt.priority != 0:
                tt_key = (
                    tt.priority, tuple(
                        tt.viewport), tuple(
                        tt.worldcoordinate), tt.projection)
                # if tt_key in self.text_renderers:
                #     ren = self.text_renderers[tt_key]
                # else:
                #     ren = self.createRenderer()
                #     self.renWin.AddRenderer(ren)
                #     self.setLayer(ren, 1)

                view = self.contextView

                area = vtk.vtkContextArea()
                view.GetScene().AddItem(area)

                vp = self.canvas._viewport
                wc = self.canvas._worldcoordinate

                [renWinWidth, renWinHeight] = self.renWin.GetSize()
                geom = vtk.vtkRecti(int(vp[0] * renWinWidth), int(vp[2] * renWinHeight), int((vp[1] - vp[0]) * renWinWidth), int((vp[3] - vp[2]) * renWinHeight))

                rect = vtk.vtkRectd(0.0, 0.0, float(renWinWidth), float(renWinHeight))

                vcs2vtk.configureContextArea(area, rect, geom)

                returned["vtk_backend_text_actors"] = vcs2vtk.genTextActor(
                    area,
                    to=to,
                    tt=tt,
                    cmap=self.canvas.colormap, geoBounds=bounds, geo=vtk_backend_geo)
                # self.setLayer(ren, tt.priority)
                # self.text_renderers[tt_key] = ren
        elif gtype == "line":
            if gm.priority != 0:
                vcs2vtk.prepLine(self, gm, geoBounds=bounds, cmap=self.canvas.colormap)
                # returned["vtk_backend_line_actors"] = actors
                # create_renderer = True
                # for act, geo in actors:
                #     ren, xScale, yScale = self.fitToViewport(
                #         act,
                #         gm.viewport,
                #         wc=gm.worldcoordinate,
                #         geo=geo,
                #         geoBounds=bounds,
                #         priority=gm.priority,
                #         create_renderer=create_renderer)
                #     create_renderer = False

        elif gtype == "marker":
            if gm.priority != 0:
                view = self.contextView

                area = vtk.vtkContextArea()
                view.GetScene().AddItem(area)

                vp = gm.viewport
                wc = gm.worldcoordinate

                # rect = vtk.vtkRectd(wc[0], wc[2], wc[1] - wc[0], wc[3] - wc[2])

                [renWinWidth, renWinHeight] = self.renWin.GetSize()
                geom = vtk.vtkRecti(int(vp[0] * renWinWidth), int(vp[2] * renWinHeight), int((vp[1] - vp[0]) * renWinWidth), int((vp[3] - vp[2]) * renWinHeight))

                # vcs2vtk.configureContextArea(area, rect, geom)

                # ren, xScale, yScale = \
                #     self.findOrCreateUniqueRenderer(None, gm.viewport,
                #                                     gm.worldcoordinate, None,
                #                                     None, gm.priority, True)


                # create a new renderer for this mapper
                # (we need one for each mapper because of camera flips)
                # if not dataset_renderer:
                xScale, yScale, xc, yc, yd, flipX, flipY = self.computeScaleToFitViewport(
                    vp,
                    wc=wc,
                    geoBounds=None,
                    geo=None)

                # xMid = (wc[0] + wc[1]) / 2.0
                # yMid = (wc[2] + wc[3]) / 2.0
                # dw = abs(wc[1] - wc[0]) / 2.0
                # dh = abs(wc[3] - wc[2]) / 2.0
                # dw *= xScale
                # dh *= yScale

                # newWc = [xMid - dw, xMid + dw, yMid - dh, yMid + dh]
                newWc = [wc[0] * xScale, wc[1] * xScale, wc[2] * yScale, wc[3] * yScale]

                # if wc[1] < wc[0]:
                #     tmp = newWc[0]
                #     newWc[0] = newWc[1]
                #     newWc[1] = tmp

                # if wc[3] < wc[2]:
                #     tmp = newWc[2]
                #     newWc[2] = newWc[3]
                #     newWc[3] = tmp

                # print('plotting markers')
                # print('  computed viewport scaling: {0}'.format([xScale, yScale]))
                # print('  original wc: {0}'.format(wc))
                # print('  scaled wc: {0}'.format(newWc))

                rect = vtk.vtkRectd(newWc[0], newWc[2], newWc[1] - newWc[0], newWc[3] - newWc[2])
                vcs2vtk.configureContextArea(area, rect, geom)

                cam = view.GetRenderer().GetActiveCamera()
                cam.ParallelProjectionOn()
                # We increase the parallel projection parallelepiped with 1/1000 so that
                # it does not overlap with the outline of the dataset. This resulted in
                # system dependent display of the outline.
                cam.SetParallelScale(yd * 1.001)
                cd = cam.GetDistance()
                cam.SetPosition(xc, yc, cd)
                cam.SetFocalPoint(xc, yc, 0.)
                if flipY:
                    cam.Elevation(180.)
                    cam.Roll(180.)
                    pass
                if flipX:
                    cam.Azimuth(180.)


                # actors = vcs2vtk.prepMarker(ren, gm, cmap=self.canvas.colormap)
                actors = vcs2vtk.prepMarker(gm, [geom[2], geom[3]], scale=[xScale, yScale], cmap=self.canvas.colormap)
                returned["vtk_backend_marker_actors"] = actors
                glyphBounds = [100000000.0, -100000000.0, 100000000.0, -100000000.0]
                for g, pd, geo in actors:
                    # data = g.GetInput()
                    # mapper = act.GetMapper()
                    # # scale the data not the markers
                    # mapper.SetInputData(data)
                    # ren, xScale, yScale = self.fitToViewport(
                    #     act,
                    #     gm.viewport,
                    #     wc=gm.worldcoordinate,
                    #     geoBounds=None,
                    #     geo=None,
                    #     priority=gm.priority,
                    #     create_renderer=False)
                    # # get the scaled data
                    # scaledData = mapper.GetInput()
                    # g.SetInputData(scaledData)
                    # g.Update()
                    # data = g.GetOutput()

                    # import pdb
                    # pdb.set_trace()

                    # bounds = g.GetBounds()
                    # glyphBounds = vcs2vtk.growBounds(glyphBounds, bounds)

                    item = vtk.vtkPolyDataItem()
                    item.SetPolyData(g)

                    item.SetScalarMode(vtk.VTK_SCALAR_MODE_USE_CELL_DATA)
                    colorArray = g.GetCellData().GetArray('Colors')

                    item.SetMappedColors(colorArray)
                    area.GetDrawAreaItem().AddItem(item)

                    # set the markers to be rendered
                    # mapper.SetInputData(g.GetOutput())

                # rect = vtk.vtkRectd(glyphBounds[0],
                #                     glyphBounds[2],
                #                     glyphBounds[1] - glyphBounds[0],
                #                     glyphBounds[3] - glyphBounds[2])
                # vcs2vtk.configureContextArea(area, rect, geom)

        elif gtype == "fillarea":
            if gm.priority != 0:
                actors = vcs2vtk.prepFillarea(self, self.renWin, gm,
                                              cmap=self.canvas.colormap)
                returned["vtk_backend_fillarea_actors"] = actors
        else:
            raise Exception(
                "Graphic type: '%s' not re-implemented yet" %
                gtype)
        self.scaleLogo()

        if not kargs.get("donotstoredisplay", False) and kargs.get(
                "render", True):
            self.renWin.Render()
        return returned

    def setLayer(self, renderer, priority):
        n = self.numberOfPlotCalls + (priority - 1) * 200 + 1
        nMax = max(self.renWin.GetNumberOfLayers(), n + 1)
        self.renWin.SetNumberOfLayers(nMax)
        renderer.SetLayer(n)

    def plot3D(self, data1, data2, tmpl, gm, ren, **kargs):
        from DV3D.Application import DV3DApp
        requiresFileVariable = True
        self.canvas.drawLogo = False
        if (data1 is None) or (requiresFileVariable and not (isinstance(
                data1, cdms2.fvariable.FileVariable) or isinstance(data1, cdms2.tvariable.TransientVariable))):
            traceback.print_stack()
            raise Exception(
                "Error, must pass a cdms2 variable object as the first input to the dv3d gm ( found '%s')" %
                (data1.__class__.__name__))
        g = self.plotApps.get(gm, None)
        if g is None:
            g = DV3DApp(self.canvas, self.cell_coordinates)
            n_overview_points = 500000
            roi = None  # ( 0, 0, 50, 50 )
            g.gminit(
                data1,
                data2,
                roi=roi,
                axes=gm.axes,
                n_overview_points=n_overview_points,
                n_cores=gm.NumCores,
                renwin=ren.GetRenderWindow(),
                plot_attributes=gm.getPlotAttributes(),
                gmname=gm.g_name,
                cm=gm.cfgManager,
                **kargs)  # , plot_type = PlotType.List  )
            self.plotApps[gm] = g
            self.plotRenderers.add(g.plot.renderer)
        else:
            g.update(tmpl)
        return {}

    def onClosing(self, cell):
        for plot in list(self.plotApps.values()):
            if hasattr(plot, 'onClosing'):
                plot.onClosing(cell)

    def plotContinents(self, continentType, wc, projection, wrap, vp, priority, **kargs):
        if continentType in [0, None]:
            return
        continents_path = self.canvas._continentspath(continentType)
        if continents_path is None:
            return (None, 1, 1)
        xforward = vcs.utils.axisConvertFunctions[kargs.get('xaxisconvert', 'linear')]['forward']
        yforward = vcs.utils.axisConvertFunctions[kargs.get('yaxisconvert', 'linear')]['forward']
        contData = vcs2vtk.prepContinents(continents_path, xforward, yforward)
        contData = vcs2vtk.doWrapData(contData, wc, fastClip=False)

        vcs2vtk.debugWriteGrid(contData, 'raw_continents')

        if projection.type != "linear":
            cpts = contData.GetPoints()
            # we use plotting coordinates for doing the projection so
            # that parameters such that central meridian are set correctly.
            geo, gcpts = vcs2vtk.project(cpts, projection, wc)
            contData.SetPoints(gcpts)
        else:
            geo = None

        vtk_dataset_bounds_no_mask = kargs.get(
            "vtk_dataset_bounds_no_mask", None)

        contLine = self.canvas.getcontinentsline()

        # Color
        if contLine.colormap:
            cmap = vcs.getcolormap(contLine.colormap)
        else:
            cmap = self.canvas.getcolormap()

        if type(contLine.color[0]) in (float, int):
            c_index = int(contLine.color[0])
            color = cmap.index[c_index]
        else:
            color = contLine.color[0]

        color = [int((c / 100.0) * 255) for c in color]

        # vtk_dataset_bounds_no_mask = kargs.get(
        #     "vtk_dataset_bounds_no_mask", None)
        # return self.fitToViewport(contActor,
        #                           vp,
        #                           wc=wc, geo=geo,
        #                           geoBounds=vtk_dataset_bounds_no_mask,
        #                           priority=priority,
        #                           create_renderer=True)

        # view and interactive area
        view = self.contextView
        # area = kargs.get("vtk_backend_pipeline_context_area", None)
        viewportScale = kargs.get("vtk_backend_viewport_scale", None)
        contBounds = kargs.get("vtk_backend_draw_area_bounds", None)

        print('plotting continents')
        print('  projection type is {0}'.format(projection.type))
        print('  vtk_dataset_bounds_no_mask = {0}'.format(vtk_dataset_bounds_no_mask))
        print('  vtk_backend_viewport_scale = {0}'.format(viewportScale))
        print('  vtk_backend_draw_area_bounds = {0}'.format(contBounds))

        area = vtk.vtkContextArea()
        view.GetScene().AddItem(area)

        # viewportFittedProjections = ['lambert conformal c', 'linear']

        # if not projection.type in viewportFittedProjections:
        #     # # Here we need to get the xscale and yscale computed in pipeline2d
        #     # # and use them to scale the viewport
        #     vpCenterX = (vp[1] + vp[0]) / 2.0
        #     vpCenterY = (vp[3] + vp[2]) / 2.0
        #     vpWidth = vp[1] - vp[0]
        #     vpHeight = vp[3] - vp[2]

        #     vpWidth *= viewportScale[0]
        #     vpHeight *= viewportScale[1]

        #     vp[0] = vpCenterX - (vpWidth / 2.0)
        #     vp[1] = vpCenterX + (vpWidth / 2.0)
        #     vp[2] = vpCenterY - (vpHeight / 2.0)
        #     vp[3] = vpCenterY + (vpHeight / 2.0)
        # else:
        #     print('     ^^^^^^^^^     FITTING CONTINENTS TO VIEWPORT     ^^^^^^^^^     ')
        #     xScale, yScale, xc, yc, yd, flipX, flipY = self.computeScaleToFitViewport(
        #         vp,
        #         wc=wc,
        #         geoBounds=vtk_dataset_bounds_no_mask)

        #     # Transform the input data
        #     T = vtk.vtkTransform()
        #     T.Scale(xScale, yScale, 1.)
        #     contData = vcs2vtk.applyTransformationToDataset(T, contData)

        [renWinWidth, renWinHeight] = self.renWin.GetSize()
        geom = vtk.vtkRecti(int(vp[0] * renWinWidth), int(vp[2] * renWinHeight), int((vp[1] - vp[0]) * renWinWidth), int((vp[3] - vp[2]) * renWinHeight))

        vcs2vtk.configureContextArea(area, contBounds, geom)

        color_arr = vtk.vtkUnsignedCharArray()
        color_arr.SetNumberOfComponents(4)
        color_arr.SetName("Colors")

        for i in range(contData.GetNumberOfCells()):
            if len(color) == 4:
                color_arr.InsertNextTypedTuple(color)
            else:
                color_arr.InsertNextTypedTuple([color[0], color[1], color[2], 255])

        contData.GetCellData().AddArray(color_arr)

        vcs2vtk.debugWriteGrid(contData, 'projected_fitted_continents')

        # Handle line drawing properties (line width + stipple)
        intValue = vtk.vtkIntArray()
        intValue.SetNumberOfComponents(1)
        intValue.SetName("StippleType")
        intValue.InsertNextValue(vcs2vtk.getStipple(contLine.type[0]))
        contData.GetFieldData().AddArray(intValue)

        floatValue = vtk.vtkFloatArray()
        floatValue.SetNumberOfComponents(1)
        floatValue.SetName("LineWidth")
        floatValue.InsertNextValue(contLine.width[0])
        contData.GetFieldData().AddArray(floatValue)

        item = vtk.vtkPolyDataItem()
        item.SetPolyData(contData)
        item.SetScalarMode(vtk.VTK_SCALAR_MODE_USE_CELL_DATA)
        item.SetMappedColors(color_arr)
        area.GetDrawAreaItem().AddItem(item)

    def renderTemplate(self, tmpl, data, gm, taxis,
                       zaxis, X=None, Y=None, draw_attributes=False, **kargs):
        # view and interactive area
        view = self.contextView

        area = vtk.vtkContextArea()
        view.GetScene().AddItem(area)

        vp = self.canvas._viewport
        wc = self.canvas._worldcoordinate

        [renWinWidth, renWinHeight] = self.renWin.GetSize()
        geom = vtk.vtkRecti(int(vp[0] * renWinWidth), int(vp[2] * renWinHeight), int((vp[1] - vp[0]) * renWinWidth), int((vp[3] - vp[2]) * renWinHeight))

        rect = vtk.vtkRectd(0.0, 0.0, float(renWinWidth), float(renWinHeight))

        vcs2vtk.configureContextArea(area, rect, geom)

        # ok first basic template stuff, let's store the displays
        # because we need to return actors for min/max/mean
        if draw_attributes:
            savedVp = self.canvas._viewport
            savedWc = self.canvas._worldcoordinate
            self.canvas._viewport = [0, 1, 0, 1]
            self.canvas._worldcoordinate = [0, 1, 0, 1]
            displays = tmpl.drawAttributes(
                self.canvas,
                data,
                gm,
                bg=self.bg,
                **kargs)
            self.canvas._viewport = savedVp
            self.canvas._worldcoordinate = savedWc
        else:
            displays = tmpl.plot(
                self.canvas,
                data,
                gm,
                bg=self.bg,
                X=X,
                Y=Y,
                **kargs)
        returned = {}
        for d in displays:
            if d is None:
                continue
            texts = d.backend.get("vtk_backend_text_actors", [])
            for t in texts:
                # ok we had a text actor, let's see if it's min/max/mean
                txt = t.GetInput()
                s0 = txt.split()[0]
                if s0 in ["Min", "Max", "Mean"]:
                    returned["vtk_backend_%s_text_actor" % s0] = t
                else:
                    returned[
                        "vtk_backend_%s_text_actor" %
                        d.backend["vtk_backend_template_attribute"]] = t
            self.canvas.display_names.remove(d.name)
            del(vcs.elements["display"][d.name])
        # Sometimes user passes "date" as an attribute to replace date
        if hasattr(data, "user_date"):
            taxis = cdms2.createAxis(
                [cdtime.s2r(data.user_date, "days since 1900").value])
            taxis.designateTime()
            taxis.units = "days since 1900"
            if zaxis is not None and zaxis.isTime():
                zaxis = taxis
        if taxis is not None:
            try:
                tstr = str(
                    cdtime.reltime(
                        taxis[0],
                        taxis.units).tocomp(
                        taxis.getCalendar()))
                # ok we have a time axis let's display the time
                crdate = vcs2vtk.applyAttributesFromVCStmpl(tmpl, "crdate")
                crdate.string = tstr.split()[0].replace("-", "/")
                crtime = vcs2vtk.applyAttributesFromVCStmpl(tmpl, "crtime")
                crtime.string = tstr.split()[1]
                # if not (None, None, None) in list(self._renderers.keys()):
                #     ren = self.createRenderer()
                #     self.renWin.AddRenderer(ren)
                #     self.setLayer(ren, 1)
                #     self._renderers[(None, None, None)] = (ren, 1, 1)
                # else:
                #     ren, xratio, yratio = self._renderers[(None, None, None)]
                tt, to = crdate.name.split(":::")
                tt = vcs.elements["texttable"][tt]
                to = vcs.elements["textorientation"][to]
                if crdate.priority > 0:
                    actors = vcs2vtk.genTextActor(area, to=to, tt=tt)
                    returned["vtk_backend_crdate_text_actor"] = actors[0]
                del(vcs.elements["texttable"][tt.name])
                del(vcs.elements["textorientation"][to.name])
                del(vcs.elements["textcombined"][crdate.name])
                tt, to = crtime.name.split(":::")
                tt = vcs.elements["texttable"][tt]
                to = vcs.elements["textorientation"][to]
                if crtime.priority > 0:
                    actors = vcs2vtk.genTextActor(area, to=to, tt=tt)
                    returned["vtk_backend_crtime_text_actor"] = actors[0]
                del(vcs.elements["texttable"][tt.name])
                del(vcs.elements["textorientation"][to.name])
                del(vcs.elements["textcombined"][crtime.name])
            except:  # noqa
                pass
        if zaxis is not None:
            try:
                # ok we have a zaxis to draw
                zname = vcs2vtk.applyAttributesFromVCStmpl(tmpl, "zname")
                zname.string = zaxis.id
                zvalue = vcs2vtk.applyAttributesFromVCStmpl(tmpl, "zvalue")
                if zaxis.isTime():
                    zvalue.string = str(zaxis.asComponentTime()[0])
                else:
                    zvalue.string = "%g" % zaxis[0]
                # if not (None, None, None) in list(self._renderers.keys()):
                #     ren = self.createRenderer()
                #     self.renWin.AddRenderer(ren)
                #     self.setLayer(ren, 1)
                #     self._renderers[(None, None, None)] = (ren, 1, 1)
                # else:
                #     ren, xratio, yratio = self._renderers[(None, None, None)]
                tt, to = zname.name.split(":::")
                tt = vcs.elements["texttable"][tt]
                to = vcs.elements["textorientation"][to]
                if zname.priority > 0:
                    vcs2vtk.genTextActor(area, to=to, tt=tt)
                del(vcs.elements["texttable"][tt.name])
                del(vcs.elements["textorientation"][to.name])
                del(vcs.elements["textcombined"][zname.name])
                if hasattr(zaxis, "units"):
                    zunits = vcs2vtk.applyAttributesFromVCStmpl(tmpl, "zunits")
                    zunits.string = zaxis.units
                    if zunits.priority > 0:
                        tt, to = zunits.name.split(":::")
                        tt = vcs.elements["texttable"][tt]
                        to = vcs.elements["textorientation"][to]
                        vcs2vtk.genTextActor(area, to=to, tt=tt)
                        del(vcs.elements["texttable"][tt.name])
                        del(vcs.elements["textorientation"][to.name])
                        del(vcs.elements["textcombined"][zunits.name])
                tt, to = zvalue.name.split(":::")
                tt = vcs.elements["texttable"][tt]
                to = vcs.elements["textorientation"][to]
                if zvalue.priority > 0:
                    actors = vcs2vtk.genTextActor(area, to=to, tt=tt)
                    returned["vtk_backend_zvalue_text_actor"] = actors[0]
                del(vcs.elements["texttable"][tt.name])
                del(vcs.elements["textorientation"][to.name])
                del(vcs.elements["textcombined"][zvalue.name])
            except:  # noqa
                pass
        return returned

    def renderColorBar(self, tmpl, levels, colors, legend, cmap,
                       style=['solid'], index=[1], opacity=[],
                       pixelspacing=[15, 15], pixelscale=12):
        if tmpl.legend.priority > 0:
            tmpl.drawColorBar(
                colors,
                levels,
                x=self.canvas,
                legend=legend,
                cmap=cmap,
                style=style,
                index=index,
                opacity=opacity,
                pixelspacing=pixelspacing,
                pixelscale=pixelscale)
        return {}

    def cleanupData(self, data):
        data[:] = numpy.ma.masked_invalid(data, numpy.nan)
        return data

    def trimData1D(self, data):
        if data is None:
            return None
        while len(data.shape) > 1:
            data = data[0]
        return self.cleanupData(data)

    # ok now trying to figure the actual data to plot
    def trimData2D(self, data):
        if data is None:
            return None
        try:
            g = data.getGrid()
            gaxes = list(g.getAxisList())
            daxes = list(data.getAxisList())
            if daxes[len(daxes) - len(gaxes):] == gaxes:
                # Ok it is gridded and the grid axes are last
                return self.cleanupData(
                    data(*(slice(0, 1),) * (len(daxes) - len(gaxes)), squeeze=1))
            else:
                # Ok just return the last two dims
                return self.cleanupData(
                    data(*(slice(0, 1),) * (len(daxes) - 2), squeeze=1))
        except Exception:
            daxes = list(data.getAxisList())
            if cdms2.isVariable(data):
                return self.cleanupData(
                    data(*(slice(0, 1),) * (len(daxes) - 2)))
            else:  # numpy arrays are not callable
                op = ()
                for i in range(numpy.rank(data) - 2):
                    op.append(slice(0, 1))
                return self.cleanupData(data[op])

    def put_png_on_canvas(
            self, filename, zoom=1, xOffset=0, yOffset=0,
            units="percent", fitToHeight=True, *args, **kargs):
        return self.put_img_on_canvas(
            filename, zoom, xOffset, yOffset, units, fitToHeight, *args, **kargs)

    def put_img_on_canvas(
            self, filename, zoom=1, xOffset=0, yOffset=0,
            units="percent", fitToHeight=True, *args, **kargs):
        print('I am in put_img_on_canvas(), filename = {0}'.format(filename))
        self.createRenWin()
        winSize = self.renWin.GetSize()
        self.hideGUI()
        readerFactory = vtk.vtkImageReader2Factory()
        reader = readerFactory.CreateImageReader2(filename)
        reader.SetFileName(filename)
        reader.Update()
        imageData = reader.GetOutput()
        a = vtk.vtkImageActor()
        a.GetMapper().SetInputConnection(reader.GetOutputPort())
        origin = imageData.GetOrigin()
        spc = imageData.GetSpacing()
        ext = imageData.GetExtent()
        ren = self.createRenderer()
        cam = ren.GetActiveCamera()
        cam.ParallelProjectionOn()
        width = (ext[1] - ext[0]) * spc[0]
        height = (ext[3] - ext[2]) * spc[1]
        if fitToHeight:
            yd = height
        else:
            yd = winSize[1]
        d = cam.GetDistance()
        heightInWorldCoord = yd / zoom
        # window pixel in world (image) coordinates
        pixelInWorldCoord = heightInWorldCoord / winSize[1]
        if units[:7].lower() == "percent":
            xoff = winSize[0] * (xOffset / 100.) * pixelInWorldCoord
            yoff = winSize[1] * (yOffset / 100.) * pixelInWorldCoord
        elif units[:6].lower() == "pixels":
            xoff = xOffset * pixelInWorldCoord
            yoff = yOffset * pixelInWorldCoord
        else:
            raise RuntimeError(
                "vtk put image does not understand %s for offset units" %
                units)
        xc = origin[0] + .5 * width
        yc = origin[1] + .5 * height
        cam.SetParallelScale(heightInWorldCoord * 0.5)
        cam.SetFocalPoint(xc - xoff, yc - yoff, 0.)
        cam.SetPosition(xc - xoff, yc - yoff, d)

        ren.AddActor(a)
        layer = max(self.renWin.GetNumberOfLayers() - 2, 0)
        ren.SetLayer(layer)
        self.renWin.AddRenderer(ren)
        self.showGUI(render=False)
        self.renWin.Render()
        return

    def hideGUI(self):
        plot = self.get3DPlot()

        if plot:
            plot.hideWidgets()
        elif not self.bg:
            from .vtk_ui.manager import get_manager, manager_exists
            if manager_exists(self.renWin.GetInteractor()):
                manager = get_manager(self.renWin.GetInteractor())
                manager.showing = False
                self.renWin.RemoveRenderer(manager.renderer)
                self.renWin.RemoveRenderer(manager.actor_renderer)

    def showGUI(self, render=True):
        plot = self.get3DPlot()

        if plot:
            plot.showWidgets()
        elif not self.bg:
            from .vtk_ui.manager import get_manager, manager_exists
            if manager_exists(self.renWin.GetInteractor()):
                manager = get_manager(self.renWin.GetInteractor())
                self.renWin.AddRenderer(manager.renderer)
                self.renWin.AddRenderer(manager.actor_renderer)
                manager.showing = True
                # Bring the manager's renderer to the top of the stack
                manager.elevate()
            if render:
                self.renWin.Render()

    def get3DPlot(self):
        from .dv3d import Gfdv3d
        plot = None
        for key in list(self.plotApps.keys()):
            if isinstance(key, Gfdv3d):
                plot = self.plotApps[key]
                break
        return plot

    def vectorGraphics(self, output_type, file, width=None, height=None,
                       units=None, textAsPaths=True):
        """Export vector graphics to PDF, Postscript, SVG and EPS format.

       Reasoning for textAsPaths as default:
       The output formats supported by gl2ps which VTK uses for postscript/pdf/svg/etc
       vector exports) handle text objects inconsistently. For example, postscript mangles
       newlines, pdf doesn't fully support rotation and alignment, stuff like that.
       These are limitations in the actual format specifications themselves.

       On top of that, embedding text objects then relies on the viewer to locate
       a similar font and render the text, and odds are good that the fonts used
       by the viewer will have different characteristics than the ones used in the
       original rendering. So, for instance, you have some right-justified lines of
       text, like the data at the top of the VCS plots. If the font used by the viewer
       uses different widths for any of glyphs composing the text, the text will be
       unaligned along the right-hand side, since the text is always anchored on
       it's left side due to how these formats represent text objects. This just looks bad.
       Exporting text as paths eliminates all of these problems with portability across
       viewers and inconsistent text object handling between output formats.
       """

        if self.renWin is None:
            raise Exception("Nothing on Canvas to dump to file")

        self.hideGUI()

        gl = vtk.vtkOpenGLGL2PSExporter()

        # This is the size of the initial memory buffer that holds the transformed
        # vertices produced by OpenGL. If you start seeing a lot of warnings:
        # GL2PS info: OpenGL feedback buffer overflow
        # increase it to save some time.
        # ParaView lags so we need a try/except around this
        # in case it is a ParaView build
        try:
            gl.SetBufferSize(50 * 1024 * 1024)  # 50MB
        except Exception:
            pass

        # Since the vcs layer stacks renderers to manually order primitives, sorting
        # is not needed and will only slow things down and introduce artifacts.
        gl.SetSortToOff()
        gl.DrawBackgroundOff()
        gl.SetInput(self.renWin)
        if (output_type == "pdf"):
            gl.SetCompress(1)
        else:
            gl.SetCompress(0)
        gl.SetFilePrefix(".".join(file.split(".")[:-1]))

        if textAsPaths:
            gl.TextAsPathOn()
        else:
            gl.TextAsPathOff()

        if output_type == "svg":
            gl.SetFileFormatToSVG()
        elif output_type == "ps":
            gl.SetFileFormatToPS()
        elif output_type == "pdf":
            gl.SetFileFormatToPDF()
        else:
            raise Exception("Unknown format: %s" % output_type)
        gl.Write()
        plot = self.get3DPlot()
        if plot:
            plot.showWidgets()

        self.showGUI()

    def postscript(self, file, width=None, height=None,
                   units=None, textAsPaths=True):
        return self.vectorGraphics("ps", file, width, height,
                                   units, textAsPaths)

    def pdf(self, file, width=None, height=None, units=None, textAsPaths=True):
        # return self.vectorGraphics("pdf", file, width, height,
        #                            units, textAsPaths)
        self.hideGUI()

        exporter = vtk.vtkPDFExporter()
        exporter.SetRenderWindow(self.contextView.GetRenderWindow())
        exporter.SetFileName(file)
        exporter.Write()

        plot = self.get3DPlot()
        if plot:
            plot.showWidgets()

        self.showGUI()

    def svg(self, file, width=None, height=None, units=None, textAsPaths=True):
        # return self.vectorGraphics("svg", file, width,
        #                            height, units, textAsPaths)
        self.hideGUI()

        exporter = vtk.vtkSVGExporter()
        exporter.SetRenderWindow(self.contextView.GetRenderWindow())
        exporter.SetFileName(file)
        # For large polydata, we can limit the number of triangles emitted during gradient subdivision.
        exporter.SetSubdivisionThreshold(10.0)
        exporter.Write()

        plot = self.get3DPlot()
        if plot:
            plot.showWidgets()

        self.showGUI()

    def gif(self, filename='noname.gif', merge='r', orientation=None,
            geometry='1600x1200'):
        raise RuntimeError("gif method not implemented in VTK backend yet")

    def png(self, file, width=None, height=None,
            units=None, draw_white_background=True, **args):

        if self.renWin is None:
            raise Exception("Nothing to dump aborting")

        if not file.split('.')[-1].lower() in ['png']:
            file += '.png'

        try:
            os.remove(file)
        except Exception:
            pass

        user_dims = None

        sz = self.renWin.GetSize()
        if width is not None and height is not None:
            if sz != (width, height):
                wrn = """You are saving to png of size different from the current canvas.
It is recommended to set the windows size before plotting or at init time.
This will lead to faster execution as well.
e.g
x=vcs.init(geometry=(1200,800))
#or
x=vcs.init()
x.geometry(1200,800)
"""
                warnings.warn(wrn)
                user_dims = (sz[0], sz[1])
                self.canvas.width = width
                self.canvas.height = height
                self.setsize(self.canvas.width, self.canvas.height)

        imgfiltr = vtk.vtkWindowToImageFilter()
        imgfiltr.SetInput(self.renWin)
        ignore_alpha = args.get('ignore_alpha', False)
        if ignore_alpha or draw_white_background:
            imgfiltr.SetInputBufferTypeToRGB()
        else:
            imgfiltr.SetInputBufferTypeToRGBA()

        self.hideGUI()
        self.renWin.Render()
        self.showGUI(render=False)

        writer = vtk.vtkPNGWriter()
        compression = args.get('compression', 5)  # get compression from user
        writer.SetCompressionLevel(compression)  # set compression level
        writer.SetInputConnection(imgfiltr.GetOutputPort())
        writer.SetFileName(file)
        # add text chunks to the writer
        m = args.get('metadata', {})
        for k, v in m.items():
            writer.AddText(k, v)
        writer.Write()
        if user_dims is not None:
            self.canvas.width, self.canvas.height = user_dims
            self.setsize(self.canvas.width, self.canvas.height)
            self.renWin.Render()

    def cgm(self, file):
        if self.renWin is None:
            raise Exception("Nothing to dump aborting")

        self.hideGUI()

        if not file.split('.')[-1].lower() in ['cgm']:
            file += '.cgm'

        try:
            os.remove(file)
        except Exception:
            pass

        plot = self.get3DPlot()
        if plot:
            plot.hideWidgets()

        writer = vtk.vtkIOCGM.vtkCGMWriter()
        writer.SetFileName(file)
        R = self.renWin.GetRenderers()
        r = R.GetFirstRenderer()
        A = r.GetActors()
        A.InitTraversal()
        a = A.GetNextActor()
        while a is not None:
            m = a.GetMapper()
            m.Update()
            writer.SetInputData(m.GetInput())
            writer.Write()
            a = A.GetNextActor()

        self.showGUI()

    def Animate(self, *args, **kargs):
        return VTKAnimate.VTKAnimate(*args, **kargs)

    def gettextextent(self, textorientation, texttable, angle=None):
        # Ensure renwin exists
        self.createRenWin()

        if isinstance(textorientation, str):
            textorientation = vcs.gettextorientation(textorientation)
        if isinstance(texttable, str):
            texttable = vcs.gettexttable(texttable)

        from .vtk_ui.text import text_box

        text_property = vtk.vtkTextProperty()
        info = self.canvasinfo()
        win_size = info["width"], info["height"]
        vcs2vtk.prepTextProperty(
            text_property,
            win_size,
            to=textorientation,
            tt=texttable)

        dpi = self.renWin.GetDPI()

        length = max(len(texttable.string), len(texttable.x), len(texttable.y))

        strings = texttable.string + \
            [texttable.string[-1]] * (length - len(texttable.string))
        xs = texttable.x + [texttable.x[-1]] * (length - len(texttable.x))
        ys = texttable.y + [texttable.y[-1]] * (length - len(texttable.y))

        labels = list(zip(strings, xs, ys))

        extents = []

        for s, x, y in labels:
            if angle is None:
                coords = text_box(
                    s, text_property, dpi, -textorientation.angle)
            else:
                coords = text_box(s, text_property, dpi, -angle)
            vp = texttable.viewport
            coords[0] = x +\
                (texttable.worldcoordinate[1] - texttable.worldcoordinate[0]) *\
                float(coords[0]) / win_size[0] / abs(vp[1] - vp[0])
            coords[1] = x +\
                (texttable.worldcoordinate[1] - texttable.worldcoordinate[0]) *\
                float(coords[1]) / win_size[0] / abs(vp[1] - vp[0])
            coords[2] = y +\
                (texttable.worldcoordinate[3] - texttable.worldcoordinate[2]) *\
                float(coords[2]) / win_size[1] / abs(vp[3] - vp[2])
            coords[3] = y +\
                (texttable.worldcoordinate[3] - texttable.worldcoordinate[2]) *\
                float(coords[3]) / win_size[1] / abs(vp[3] - vp[2])
            extents.append(coords)
        return extents

    def getantialiasing(self):
        if self.renWin is None:
            return self.antialiasing
        else:
            return self.renWin.GetMultiSamples()

    def setantialiasing(self, antialiasing):
        self.antialiasing = antialiasing
        if self.renWin is not None:
            self.renWin.SetMultiSamples(antialiasing)

    def createLogo(self):
        if self.canvas.drawLogo:
            if self.logoRepresentation is None:
                defaultLogoFile = os.path.join(
                    sys.prefix,
                    "share",
                    "vcs",
                    "cdat.png")
                reader = vtk.vtkPNGReader()
                reader.SetFileName(defaultLogoFile)
                reader.Update()
                logo_input = reader.GetOutput()
                self.logoRepresentation = vtk.vtkLogoRepresentation()
                self.logoRepresentation.SetImage(logo_input)
                self.logoRepresentation.ProportionalResizeOn()
                self.logoRepresentation.SetPosition(0.895, 0.0)
                self.logoRepresentation.SetPosition2(0.10, 0.05)
                self.logoRepresentation.GetImageProperty().SetOpacity(.8)
                self.logoRepresentation.GetImageProperty(
                ).SetDisplayLocationToBackground()
            if (self.logoRenderer is None):
                self.logoRenderer = vtk.vtkRenderer()
                self.logoRenderer.AddViewProp(self.logoRepresentation)
            self.logoRepresentation.SetRenderer(self.logoRenderer)

    def scaleLogo(self):
        if self.canvas.drawLogo:
            if self.renWin is not None:
                self.createLogo()
                self.setLayer(self.logoRenderer, 1)
                self.renWin.AddRenderer(self.logoRenderer)

    def _applyTransformationToMapperInput(self, T, mapper):
        mapper.Update()
        data = mapper.GetInput()
        outputData = vcs2vtk.applyTransformationToDataset(T, data)
        mapper.SetInputData(outputData)

        planeCollection = mapper.GetClippingPlanes()

        # We have to transform the hardware clip planes as well
        if (planeCollection is not None):
            planeCollection.InitTraversal()
            plane = planeCollection.GetNextItem()
            while (plane):
                origin = plane.GetOrigin()
                inOrigin = [origin[0], origin[1], origin[2], 1.0]
                outOrigin = [origin[0], origin[1], origin[2], 1.0]

                normal = plane.GetNormal()
                inNormal = [normal[0], normal[1], normal[2], 0.0]
                outNormal = [normal[0], normal[1], normal[2], 0.0]

                T.MultiplyPoint(inOrigin, outOrigin)
                if (outOrigin[3] != 0.0):
                    outOrigin[0] /= outOrigin[3]
                    outOrigin[1] /= outOrigin[3]
                    outOrigin[2] /= outOrigin[3]
                plane.SetOrigin(outOrigin[0], outOrigin[1], outOrigin[2])

                # For normal matrix, compute the transpose of inverse
                normalTransform = vtk.vtkTransform()
                normalTransform.DeepCopy(T)
                mat = vtk.vtkMatrix4x4()
                normalTransform.GetTranspose(mat)
                normalTransform.GetInverse(mat)
                normalTransform.SetMatrix(mat)
                normalTransform.MultiplyPoint(inNormal, outNormal)
                if (outNormal[3] != 0.0):
                    outNormal[0] /= outNormal[3]
                    outNormal[1] /= outNormal[3]
                    outNormal[2] /= outNormal[3]
                plane.SetNormal(outNormal[0], outNormal[1], outNormal[2])
                plane = planeCollection.GetNextItem()

    def findOrCreateUniqueRenderer(self, Actor, vp, wc, geoBounds=None,
                                   geo=None, priority=None, create_renderer=False):
        # Data range in World Coordinates
        if priority == 0:
            return (None, 1, 1)
        vp = tuple(vp)
        if wc is None:
            if Actor is not None:
                Xrg = list(Actor.GetXRange())
                Yrg = list(Actor.GetYRange())
            else:
                raise Exception('Cannot find unique renderer without an actor or world coords range')
        else:
            Xrg = [float(wc[0]), float(wc[1])]
            Yrg = [float(wc[2]), float(wc[3])]

        wc_used = (float(Xrg[0]), float(Xrg[1]), float(Yrg[0]), float(Yrg[1]))
        sc = self.renWin.GetSize()

        # Ok at this point this is all the info we need
        # we can determine if it's a unique renderer or not
        # let's see if we did this already.
        if not create_renderer and\
                (vp, wc_used, sc, priority) in list(self._renderers.keys()):
            # yep already have one, we will use this Renderer
            Renderer, xScale, yScale = self._renderers[
                (vp, wc_used, sc, priority)]
        else:
            Renderer = self.createRenderer()
            self.renWin.AddRenderer(Renderer)
            Renderer.SetViewport(vp[0], vp[2], vp[1], vp[3])

            if Yrg[0] > Yrg[1]:
                # Yrg=[Yrg[1],Yrg[0]]
                # T.RotateY(180)
                Yrg = [Yrg[1], Yrg[0]]
                flipY = True
            else:
                flipY = False
            if Xrg[0] > Xrg[1]:
                Xrg = [Xrg[1], Xrg[0]]
                flipX = True
            else:
                flipX = False

            if geo is not None and geoBounds is not None:
                Xrg = geoBounds[0:2]
                Yrg = geoBounds[2:4]

            wRatio = float(sc[0]) / float(sc[1])
            dRatio = (Xrg[1] - Xrg[0]) / (Yrg[1] - Yrg[0])
            vRatio = float(vp[1] - vp[0]) / float(vp[3] - vp[2])

            if wRatio > 1.:  # landscape orientated window
                yScale = 1.
                xScale = vRatio * wRatio / dRatio
            else:
                xScale = 1.
                yScale = dRatio / (vRatio * wRatio)
            self.setLayer(Renderer, priority)
            self._renderers[
                (vp, wc_used, sc, priority)] = Renderer, xScale, yScale

            xc = xScale * float(Xrg[1] + Xrg[0]) / 2.
            yc = yScale * float(Yrg[1] + Yrg[0]) / 2.
            yd = yScale * float(Yrg[1] - Yrg[0]) / 2.
            cam = Renderer.GetActiveCamera()
            cam.ParallelProjectionOn()
            # We increase the parallel projection parallelepiped with 1/1000 so that
            # it does not overlap with the outline of the dataset. This resulted in
            # system dependent display of the outline.
            cam.SetParallelScale(yd * 1.001)
            cd = cam.GetDistance()
            cam.SetPosition(xc, yc, cd)
            cam.SetFocalPoint(xc, yc, 0.)
            if geo is None:
                if flipY:
                    cam.Elevation(180.)
                    cam.Roll(180.)
                    pass
                if flipX:
                    cam.Azimuth(180.)

            # print('VTKPlots.findOrCreateUniqueRenderer(): xScale = %f, yScale = %f, xc = %f, yc = %f, yd = %f, flipX = %s, flipY = %s' % (xScale, yScale, xc, yc, yd, flipX, flipY))

        return (Renderer, xScale, yScale)

    def computeScaleToFitViewport(self, vp, wc, geoBounds=None, geo=None):
        vp = tuple(vp)
        Xrg = [float(wc[0]), float(wc[1])]
        Yrg = [float(wc[2]), float(wc[3])]

        wc_used = (float(Xrg[0]), float(Xrg[1]), float(Yrg[0]), float(Yrg[1]))
        sc = self.renWin.GetSize()

        if Yrg[0] > Yrg[1]:
            # Yrg=[Yrg[1],Yrg[0]]
            # T.RotateY(180)
            Yrg = [Yrg[1], Yrg[0]]
            flipY = True
        else:
            flipY = False
        if Xrg[0] > Xrg[1]:
            Xrg = [Xrg[1], Xrg[0]]
            flipX = True
        else:
            flipX = False

        if geo is not None and geoBounds is not None:
            Xrg = geoBounds[0:2]
            Yrg = geoBounds[2:4]

        wRatio = float(sc[0]) / float(sc[1])
        dRatio = (Xrg[1] - Xrg[0]) / (Yrg[1] - Yrg[0])
        vRatio = float(vp[1] - vp[0]) / float(vp[3] - vp[2])

        if wRatio > 1.:  # landscape orientated window
            yScale = 1.
            xScale = vRatio * wRatio / dRatio
        else:
            xScale = 1.
            yScale = dRatio / (vRatio * wRatio)

        xc = xScale * float(Xrg[1] + Xrg[0]) / 2.
        yc = yScale * float(Yrg[1] + Yrg[0]) / 2.
        yd = yScale * float(Yrg[1] - Yrg[0]) / 2.

        return (xScale, yScale, xc, yc, yd, flipX, flipY)

    def fitToViewport(self, Actor, vp, wc=None, geoBounds=None, geo=None, priority=None,
                      create_renderer=False, add_actor=True):
        # import pdb
        # pdb.set_trace()
        (Renderer, xScale, yScale) = \
            self.findOrCreateUniqueRenderer(Actor, vp, wc, geoBounds, geo,
                                            priority, create_renderer)

        if Renderer is not None:
            T = vtk.vtkTransform()
            T.Scale(xScale, yScale, 1.)

            mapper = Actor.GetMapper()

            self._animationActorTransforms[Actor] = T
            self._applyTransformationToMapperInput(T, mapper)

            if add_actor:
                Renderer.AddActor(Actor)

        return (Renderer, xScale, yScale)

    def update_input(self, vtkobjects, array1, array2=None, update=True):
        if "vtk_backend_grid" in vtkobjects:
            # Ok ths is where we update the input data
            vg = vtkobjects["vtk_backend_grid"]
            vcs2vtk.setArray(vg, array1.filled(0).flat, "scalar",
                             isCellData=vg.GetCellData().GetScalars(),
                             isScalars=True)

            if "vtk_backend_filter" in vtkobjects:
                vtkobjects["vtk_backend_filter"].Update()
            if "vtk_backend_missing_mapper" in vtkobjects:
                missingMapper, color, cellData = vtkobjects[
                    "vtk_backend_missing_mapper"]
                missingMapper2 = vcs2vtk.putMaskOnVTKGrid(
                    array1,
                    vg,
                    color,
                    cellData,
                    deep=False)
            else:
                missingMapper = None
            if "vtk_backend_contours" in vtkobjects:
                for c in vtkobjects["vtk_backend_contours"]:
                    c.Update()
                ports = vtkobjects["vtk_backend_contours"]
            elif "vtk_backend_geofilters" in vtkobjects:
                ports = vtkobjects["vtk_backend_geofilters"]
            else:
                # Vector plot
                # TODO: this does not work with wrapping
                ports = vtkobjects["vtk_backend_glyphfilters"]
                w = vcs2vtk.generateVectorArray(array1, array2, vg)
                vg.GetPointData().AddArray(w)
                ports[0].SetInputData(vg)

            if "vtk_backend_actors" in vtkobjects:
                i = 0
                for a in vtkobjects["vtk_backend_actors"]:
                    beItem = a[0]
                    if a[1] is missingMapper:
                        i -= 1
                        mapper = missingMapper2
                    else:
                        # Labeled contours are a different kind
                        if "vtk_backend_luts" in vtkobjects:
                            lut, rg = vtkobjects["vtk_backend_luts"][i]
                            mapper = vtk.vtkPolyDataMapper()
                        elif "vtk_backend_labeled_luts" in vtkobjects:
                            lut, rg = vtkobjects["vtk_backend_labeled_luts"][i]
                            mapper = vtk.vtkLabeledContourMapper()

                        algo_i = ports[i]
                        coloring = None
                        scalarRange = None

                        if lut is not None:
                            if mapper.IsA("vtkPolyDataMapper"):
                                coloring = 'points'
                            else:
                                stripper = vtk.vtkStripper()
                                stripper.SetInputConnection(
                                    ports[i].GetOutputPort())
                                mapper.SetInputConnection(
                                    stripper.GetOutputPort())
                                algo_i = stripper
                                coloring = 'points'
                                scalarRange = rg

                            if rg[2]:
                                coloring = 'cells'

                            scalarRange = rg

                        algo_i.Update()
                        new_pd = algo_i.GetOutput()

                        beItem.SetPolyData(new_pd)

                        if coloring:
                            attrs = new_pd.GetPointData()
                            numColors = new_pd.GetNumberOfPoints()
                            beItem.SetScalarMode(vtk.VTK_SCALAR_MODE_USE_POINT_DATA)

                            if coloring == 'cells':
                                attrs = new_pd.GetCellData()
                                numColors = new_pd.GetNumberOfCells()
                                beItem.SetScalarMode(vtk.VTK_SCALAR_MODE_USE_CELL_DATA)

                            colorByArray = attrs.GetScalars()

                            if scalarRange:
                                lut.SetRange(scalarRange[0], scalarRange[1])

                            mappedColors = lut.MapScalars(colorByArray, vtk.VTK_COLOR_MODE_DEFAULT, 0)
                            beItem.SetMappedColors(mappedColors)
                            mappedColors.FastDelete()

                    i += 1

        taxis = array1.getTime()
        if taxis is not None:
            tstr = str(
                cdtime.reltime(
                    taxis[0],
                    taxis.units).tocomp(
                    taxis.getCalendar()))
        else:
            tstr = None
        # Min/Max/Mean
        for att in ["Min", "Max", "Mean", "crtime", "crdate", "zvalue"]:
            if "vtk_backend_%s_text_actor" % att in vtkobjects:
                t = vtkobjects["vtk_backend_%s_text_actor" % att]
                if att == "Min":
                    t.SetInput("Min %g" % array1.min())
                elif att == "Max":
                    t.SetInput("Max %g" % array1.max())
                elif att == "Mean":
                    if not inspect.ismethod(getattr(array1, 'mean')):
                        meanstring = "Mean: %s" % getattr(array1, "mean")
                    else:
                        try:
                            meanstring = 'Mean %.4g' % \
                                float(cdutil.averager(array1, axis=" ".join(["(%s)" %
                                                                             S for S in array1.getAxisIds()])))
                        except Exception:
                            try:
                                meanstring = 'Mean %.4g' % array1.mean()
                            except Exception:
                                meanstring = 'Mean %.4g' % numpy.mean(
                                    array1.filled())
                    t.SetInput(meanstring)
                elif att == "crdate" and tstr is not None:
                    t.SetInput(tstr.split()[0].replace("-", "/"))
                elif att == "crtime" and tstr is not None:
                    t.SetInput(tstr.split()[1])
                elif att == "zvalue":
                    if len(array1.shape) > 2:
                        tmp_l = array1.getAxis(-3)
                        if tmp_l.isTime():
                            t.SetInput(str(tmp_l.asComponentTime()[0]))
                        else:
                            t.SetInput("%g" % tmp_l[0])

        if update:
            self.renWin.Render()

    def png_dimensions(self, path):
        reader = vtk.vtkPNGReader()
        reader.SetFileName(path)
        reader.Update()
        img = reader.GetOutput()
        size = img.GetDimensions()
        return size[0], size[1]

    def raisecanvas(self):
        if self.renWin is None:
            warnings.warn("Cannot raise if you did not open the canvas yet.")
            return
        self.renWin.MakeCurrent()
