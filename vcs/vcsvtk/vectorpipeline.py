from .pipeline2d import Pipeline2D

import vcs
from vcs import vcs2vtk
import vtk


class VectorPipeline(Pipeline2D):

    """Implementation of the Pipeline interface for VCS vector plots."""

    def __init__(self, gm, context_, plot_keyargs):
        super(VectorPipeline, self).__init__(gm, context_, plot_keyargs)
        self._needsCellData = False
        self._needsVectors = True

    def _plotInternal(self):
        """Overrides baseclass implementation."""
        # Preserve time and z axis for plotting these inof in rendertemplate
        projection = vcs.elements["projection"][self._gm.projection]
        taxis = self._originalData1.getTime()
        scaleFactor = 1.0

        if self._originalData1.ndim > 2:
            zaxis = self._originalData1.getAxis(-3)
        else:
            zaxis = None

        scale = 1.0
        lat = None
        lon = None

        latAccessor = self._data1.getLatitude()
        lonAccessor = self._data1.getLongitude()
        if latAccessor:
            lat = latAccessor[:]
        if lonAccessor:
            lon = lonAccessor[:]

        if self._vtkGeoTransform is not None:
            newv = vtk.vtkDoubleArray()
            newv.SetNumberOfComponents(3)
            newv.InsertTypedTuple(0, [lon.min(), lat.min(), 0])
            newv.InsertTypedTuple(1, [lon.max(), lat.max(), 0])

            vcs2vtk.projectArray(newv, projection, self._vtkDataSetBounds)
            dimMin = [0, 0, 0]
            dimMax = [0, 0, 0]

            newv.GetTypedTuple(0, dimMin)
            newv.GetTypedTuple(1, dimMax)

            maxDimX = max(dimMin[0], dimMax[0])
            maxDimY = max(dimMin[1], dimMax[1])

            if lat.max() != 0.0:
                scale = abs((maxDimY / lat.max()))

            if lon.max() != 0.0:
                temp = abs((maxDimX / lon.max()))
                if scale < temp:
                    scale = temp
        else:
            scale = 1.0

        # Vector attempt
        ltp_tmp = self._gm.linetype
        if ltp_tmp is None:
            ltp_tmp = "default"
        try:
            ltp_tmp = vcs.getline(ltp_tmp)
            lwidth = ltp_tmp.width[0]  # noqa
            lcolor = ltp_tmp.color[0]
            lstyle = ltp_tmp.type[0]  # noqa
        except Exception:
            lstyle = "solid"  # noqa
            lwidth = 1.  # noqa
            lcolor = [0., 0., 0., 100.]
        if self._gm.linewidth is not None:
            lwidth = self._gm.linewidth  # noqa
        if self._gm.linecolor is not None:
            lcolor = self._gm.linecolor

        arrow = vtk.vtkGlyphSource2D()
        arrow.SetGlyphTypeToArrow()
        arrow.SetOutputPointsPrecision(vtk.vtkAlgorithm.DOUBLE_PRECISION)
        arrow.FilledOff()

        polydata = self._vtkPolyDataFilter.GetOutput()
        vectors = polydata.GetPointData().GetVectors()

        if self._gm.scaletype == 'constant' or\
           self._gm.scaletype == 'constantNNormalize' or\
           self._gm.scaletype == 'constantNLinear':
            scaleFactor = scale * self._gm.scale
        else:
            scaleFactor = 1.0

        glyphFilter = vtk.vtkGlyph2D()
        glyphFilter.SetInputData(polydata)
        glyphFilter.SetInputArrayToProcess(1, 0, 0, 0, "vector")
        glyphFilter.SetSourceConnection(arrow.GetOutputPort())
        glyphFilter.SetVectorModeToUseVector()

        # Rotate arrows to match vector data:
        glyphFilter.OrientOn()
        glyphFilter.ScalingOn()

        glyphFilter.SetScaleModeToScaleByVector()

        maxNormInVp = None
        minNormInVp = None
        # Find the min and max vector magnitudes
        (minNorm, maxNorm) = vectors.GetRange(-1)
        if maxNorm == 0:
            maxNorm = 1.0

        if self._gm.scaletype == 'normalize' or self._gm.scaletype == 'linear' or\
           self._gm.scaletype == 'constantNNormalize' or self._gm.scaletype == 'constantNLinear':
            if self._gm.scaletype == 'normalize' or self._gm.scaletype == 'constantNNormalize':
                scaleFactor /= maxNorm

            if self._gm.scaletype == 'linear' or self._gm.scaletype == 'constantNLinear':
                noOfComponents = vectors.GetNumberOfComponents()
                scalarArray = vtk.vtkDoubleArray()
                scalarArray.SetNumberOfComponents(1)
                scalarArray.SetNumberOfValues(vectors.GetNumberOfTuples())

                oldRange = maxNorm - minNorm
                oldRange = 1.0 if oldRange == 0.0 else oldRange

                # New range min, max.
                newRangeValues = self._gm.scalerange
                newRange = newRangeValues[1] - newRangeValues[0]

                for i in range(0, vectors.GetNumberOfTuples()):
                    norm = vtk.vtkMath.Norm(vectors.GetTuple(i), noOfComponents)
                    newValue = (((norm - minNorm) * newRange) / oldRange) + newRangeValues[0]
                    scalarArray.SetValue(i, newValue)
                    polydata.GetPointData().SetScalars(scalarArray)
                maxNormInVp = newRangeValues[1] * scaleFactor
                minNormInVp = newRangeValues[0] * scaleFactor

                # Scale to vector magnitude:
                # NOTE: Currently we compute our own scaling factor since VTK does
                # it by clamping the values > max to max  and values < min to min
                # and not remap the range.
                glyphFilter.SetScaleModeToScaleByScalar()

        glyphFilter.SetScaleFactor(scaleFactor)
        if (maxNormInVp is None):
            maxNormInVp = maxNorm * scaleFactor
            # minNormInVp is left None, as it is displayed only for linear scaling.

        mapper = vtk.vtkPolyDataMapper()

        glyphFilter.Update()
        data = glyphFilter.GetOutput()

        mapper.SetInputData(data)
        mapper.ScalarVisibilityOff()
        act = vtk.vtkActor()
        act.SetMapper(mapper)

        cmap = self.getColorMap()
        if isinstance(lcolor, (list, tuple)):
            r, g, b, a = lcolor
        else:
            r, g, b, a = cmap.index[lcolor]
        act.GetProperty().SetColor(r / 100., g / 100., b / 100.)

        plotting_dataset_bounds = self.getPlottingBounds()
        vp = self._resultDict.get('ratio_autot_viewport',
                                  [self._template.data.x1, self._template.data.x2,
                                   self._template.data.y1, self._template.data.y2])
        dataset_renderer, xScale, yScale = self._context().fitToViewport(
            act, vp,
            wc=plotting_dataset_bounds,
            geoBounds=self._vtkDataSetBoundsNoMask,
            geo=self._vtkGeoTransform,
            priority=self._template.data.priority,
            create_renderer=True)
        kwargs = {'vtk_backend_grid': self._vtkDataSet,
                  'dataset_bounds': self._vtkDataSetBounds,
                  'plotting_dataset_bounds': plotting_dataset_bounds,
                  "vtk_dataset_bounds_no_mask": self._vtkDataSetBoundsNoMask,
                  'vtk_backend_geo': self._vtkGeoTransform}
        if ('ratio_autot_viewport' in self._resultDict):
            kwargs["ratio_autot_viewport"] = vp
        self._resultDict.update(self._context().renderTemplate(
            self._template, self._data1,
            self._gm, taxis, zaxis, **kwargs))

        # assume that self._data1.units has the proper vector units
        unitString = None
        if (hasattr(self._data1, 'units')):
            unitString = self._data1.units

        worldToViewportXScale = (vp[1] - vp[0]) /\
            (self._vtkDataSetBoundsNoMask[1] - self._vtkDataSetBoundsNoMask[0])
        maxNormInVp *= worldToViewportXScale
        if (minNormInVp):
            minNormInVp *= worldToViewportXScale
        vcs.utils.drawVectorLegend(
            self._context().canvas, self._template.legend, lcolor, lstyle, lwidth,
            unitString, maxNormInVp, maxNorm, minNormInVp, minNorm)

        kwargs['xaxisconvert'] = self._gm.xaxisconvert
        kwargs['yaxisconvert'] = self._gm.yaxisconvert
        if self._data1.getAxis(-1).isLongitude() and self._data1.getAxis(-2).isLatitude():
            self._context().plotContinents(self._plot_kargs.get("continents", 1),
                                           plotting_dataset_bounds, projection,
                                           self._dataWrapModulo, vp,
                                           self._template.data.priority, **kwargs)
        self._resultDict["vtk_backend_actors"] = [[act, plotting_dataset_bounds]]
        self._resultDict["vtk_backend_glyphfilters"] = [glyphFilter]
        self._resultDict["vtk_backend_luts"] = [[None, None]]

    def _updateContourLevelsAndColors(self):
        """Overrides baseclass implementation."""
        pass
