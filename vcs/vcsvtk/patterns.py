import vtk


class Pattern(object):
    def __init__(self, patternPolyData, scale, style):
        self.patternPolyData = patternPolyData
        self.scale = scale
        self.style = style
        self.glyph = None

    def render(self):
        """
        Glyphs the input polydata points with the requested shape and
        replaces the input polydata with glyphed output polydata with
        colored cells
        """
        self.glyph = vtk.vtkGlyphSource2D()
        self.glyph.SetGlyphTypeToSquare()
        self.glyph.SetScale(self.scale)
        self.glyph.FilledOff()
        self.glyph.DashOff()
        self.glyph.CrossOff()

        self.paint()

        self.glyph2D = vtk.vtkGlyph2D()
        self.glyph2D.OrientOff()
        self.glyph2D.ScalingOff()
        self.glyph2D.SetScaleModeToDataScalingOff()
        self.glyph2D.SetInputData(self.patternPolyData)
        self.glyph2D.SetSourceConnection(self.glyph.GetOutputPort())
        self.glyph2D.Update()
        self.patternPolyData.DeepCopy(self.glyph2D.GetOutput())

    def paint(self):
        raise NotImplementedError(
            "paint() not implemented for %s" % str(
                type(self)))


class Triangle(Pattern):

    def paint(self):
        self.glyph.SetGlyphTypeToTriangle()


class FilledTriangle(Triangle):

    def paint(self):
        Triangle.paint(self)
        self.glyph.FilledOn()


class Dot(Pattern):

    def paint(self):
        self.glyph.SetGlyphTypeToCircle()


class FilledDot(Dot):

    def paint(self):
        Dot.paint(self)
        self.glyph.FilledOn()


class HorizStripe(Pattern):

    def paint(self):
        self.glyph.SetGlyphTypeToDash()
        self.glyph.FilledOn()
        self.glyph.SetScale(self.scale * 1.2)


class VertStripe(HorizStripe):

    def paint(self):
        HorizStripe.paint(self)
        self.glyph.SetRotationAngle(90)


class DiagStripe(HorizStripe):

    def paint(self):
        HorizStripe.paint(self)
        self.glyph.SetRotationAngle(45)


class ReverseDiagStripe(DiagStripe):

    def paint(self):
        DiagStripe.paint(self)
        self.glyph.SetRotationAngle(-45)


class HorizDash(Pattern):

    def paint(self):
        self.glyph.SetGlyphTypeToDash()
        self.glyph.FilledOn()


class VertDash(HorizDash):

    def paint(self):
        HorizDash.paint(self)
        self.glyph.SetRotationAngle(90)


class Cross(Pattern):

    def paint(self):
        self.glyph.CrossOn()
        self.glyph.SetScale2(0.1)


class FilledCross(Cross):

    def paint(self):
        self.glyph.SetGlyphTypeToThickCross()
        self.glyph.FilledOn()


class XCross(Cross):

    def paint(self):
        Cross.paint(self)
        self.glyph.SetScale(self.scale * 2.0)
        self.glyph.SetRotationAngle(45.0)


class Diamond(Pattern):

    def paint(self):
        self.glyph.SetGlyphTypeToDiamond()


class FilledDiamond(Diamond):

    def paint(self):
        Diamond.paint(self)
        self.glyph.FilledOn()


class Square(Pattern):

    def paint(self):
        self.glyph.SetGlyphTypeToSquare()


class FilledSquare(Square):

    def paint(self):
        Square.paint(self)
        self.glyph.FilledOn()


class CircleCross(Pattern):

    def paint(self):
        self.glyph.SetGlyphTypeToCircle()
        self.glyph.SetScale2(1.5)
        self.glyph.CrossOn()


class EdgeArrow(Pattern):

    def paint(self):
        self.glyph.SetGlyphTypeToEdgeArrow()


class EdgeArrowInverted(EdgeArrow):

    def paint(self):
        EdgeArrow.paint(self)
        self.glyph.SetRotationAngle(180)


# Patterns are 1-indexed, so we always skip the 0th element in this list
pattern_list = [Pattern, Triangle, FilledTriangle, Dot, FilledDot,
                HorizStripe, VertStripe, HorizDash, VertDash,
                DiagStripe, ReverseDiagStripe,
                Cross, FilledCross, XCross, Diamond, FilledDiamond,
                Square, FilledSquare, CircleCross, EdgeArrow, EdgeArrowInverted]
