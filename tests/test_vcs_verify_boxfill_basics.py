import basevcstest
import cdtime
import numpy


class TestVCSVerifyBoxfill(basevcstest.VCSBaseTest):
    def testVCSVerifyBoxfillBasics(self):
        b = self.x.createboxfill()
        assert(b.projection == "linear")
        assert(b.xticlabels1 == "*")
        assert(b.xticlabels2 == "*")
        assert(b.xmtics1 == "")
        assert(b.xmtics2 == "")
        assert(b.yticlabels1 == "*")
        assert(b.yticlabels2 == "*")
        assert(b.ymtics1 == "")
        assert(b.ymtics2 == "")
        assert(numpy.allclose(b.datawc_x1, 1e+20))
        assert(numpy.allclose(b.datawc_x2, 1e+20))
        assert(numpy.allclose(b.datawc_y1, 1e+20))
        assert(numpy.allclose(b.datawc_y2, 1e+20))
        assert(b.datawc_timeunits == 'days since 2000')
        assert(b.datawc_calendar == 135441)
        assert(b.xaxisconvert == "linear")
        assert(b.yaxisconvert == "linear")
        assert(b.boxfill_type == "linear")
        assert(numpy.allclose(b.level_1, 1e+20))
        assert(numpy.allclose(b.level_2, 1e+20))
        assert(numpy.allclose(b.levels, 1e+20))
        assert(b.color_1 == 0)
        assert(b.color_2 == 255)
        assert(b.fillareacolors is None)
        assert(b.legend is None)
        assert(b.ext_1 == False)
        assert(b.ext_2 == False)
        assert(b.missing == (0.0, 0.0, 0.0, 100.0))

        # Now test setting attributes correctly and incorrectly
        b.projection = 'linear'
        assert(b.projection == "linear")
        p = self.x.createprojection("test_bfill")
        b.projection = p
        assert(b.projection == p.name)
        try:
            b.projection = "not_a_valid_projection"
            raise Exception(
                "Should have been able to set boxfill projection to a projection that does not exists")
        except BaseException:
            pass
        self.check_values_setting(b,
                                  ["xticlabels1",
                                   "xticlabels2",
                                   "xmtics1",
                                   "xmtics2",
                                   "yticlabels1",
                                   "yticlabels2",
                                   "ymtics1",
                                   "ymtics2",
                                   ],
                                  ["*",
                                   "",
                                   None,
                                   "lon20",
                                   {23.: "Hi",
                                    }],
                                  ["bla",
                                      10,
                                      10.,
                                      [],
                                      ()])
        self.check_values_setting(b, ["datawc_x1", "datawc_x2", "datawc_y1", "datawc_y2"], [
                                  56, 56.7, ], ["bla", [4, 5, 6], None, {}])
        self.check_values_setting(
            b, "datawc_timeunits", [
                "months since 1800", "years since 234", ], [
                1, "bla", 2., {}, [], (), None])
        self.check_values_setting(b,
                                  "datawc_calendar",
                                  [cdtime.GregorianCalendar,
                                   cdtime.JulianCalendar,
                                   cdtime.MixedCalendar,
                                   cdtime.NoLeapCalendar,
                                   cdtime.StandardCalendar],
                                  [4,
                                   "bla",
                                   {},
                                      [],
                                      (),
                                      None])
        self.check_values_setting(b, ['xaxisconvert', 'yaxisconvert'], [
                                  'linear', 'log10', 'ln', 'exp', 'area_wt'], ['log', 'bla', [], (), {}, 8, 0, 1, None])
        self.check_values_setting(
            b, "boxfill_type", [
                'linear', 'log10', 'custom', 0, 1, 2], [
                'bla', 45, (), [], {}, None])
        self.check_values_setting(b, ["level_1", "level_2"], [2, 2., 1.e20, ], [
                                  '1', [1, 2, 3, 4], [1, ], {3: "3"}, None])
        self.check_values_setting(b, "levels", [[1, 2, 3, 4], [1, 2., 45.], [[1, 2], [
                                  4, 5], [6, 7]]], [1, [1, 2, '4'], [], {}, {1: '1'}, None, [[1, 2], [1, 2, 3]]])
        self.check_values_setting(b, ["color_1", "color_2", "missing"], [2, "red", [100, 5., 4], [
                                  23, 4, 5, 50], 242], ["foo", -5, 345, [56, ], [1, 2, 3, 4, 5], [], {}, None])
        self.check_values_setting(b, "fillareacolors", [[1, 2, 3], [
                                  1, "red", "blue"], None], ['1', {}, [-3, -5, -6], [1, 2, "foo"]])
        fa = self.x.createfillarea()
        self.check_values_setting(b, "fillareaindices", [[1, 2, 3], [1, fa], None], [
                                  '1', {}, [-3, -5, -6], [1, 2, "foo"], [0, 1, 2], [1, 23]])
        self.check_values_setting(b,
                                  "fillareastyle",
                                  [0,
                                   1,
                                   2,
                                   3,
                                   fa,
                                   "solid",
                                   "hatch",
                                   "pattern",
                                   "hallow"],
                                  [-1,
                                   4,
                                   "bla",
                                   [],
                                      {},
                                      b,
                                      None])
        self.check_values_setting(b, "legend", [None, {}, {1: "23"}, [
                                  1, 2, 3], 6], [["bla", 1, 2], ])
        self.check_values_setting(b,
                                  ["ext_1",
                                   "ext_2"],
                                  ["y",
                                   "n",
                                   0,
                                   1,
                                   True,
                                   False,
                                   "yes",
                                   "no",
                                   "Y",
                                   "N",
                                   "YES",
                                   "NO",
                                   None,
                                   " y ",
                                   "yes ",
                                   ],
                                  [2,
                                      'maybe',
                                      'foo',
                                      'nope',
                                      'yesish',
                                      "no and yes"])

        b = self.x.createboxfill("test_b_ok", b.name)
        assert(b.name == "test_b_ok")
        assert(b.projection == "test_bfill")
        assert(b.xticlabels1 == {23: "Hi"})
        assert(b.xticlabels2 == {23: "Hi"})
        assert(b.xmtics1 == {23: "Hi"})
        assert(b.xmtics2 == {23: "Hi"})
        assert(b.yticlabels1 == {23: "Hi"})
        assert(b.yticlabels2 == {23: "Hi"})
        assert(b.ymtics1 == {23: "Hi"})
        assert(b.ymtics2 == {23: "Hi"})
        assert(numpy.allclose(b.datawc_x1, 56.7))
        assert(numpy.allclose(b.datawc_x2, 56.7))
        assert(numpy.allclose(b.datawc_y1, 56.7))
        assert(numpy.allclose(b.datawc_y2, 56.7))
        assert(b.datawc_timeunits == 'years since 234')
        assert(b.datawc_calendar == cdtime.StandardCalendar)
        assert(b.xaxisconvert == "area_wt")
        assert(b.yaxisconvert == "area_wt")
        assert(b.boxfill_type == "custom")
        assert(numpy.allclose(b.level_1, 1e+20))
        assert(numpy.allclose(b.level_2, 1e+20))
        assert(b.levels == [[-1e20, 1], [1, 2], [4, 5], [6, 7], [7, 1.e20]])
        assert(b.color_1 == 242)
        assert(b.color_2 == 242)
        assert(b.fillareacolors is None)
        assert(b.fillareacolors is None)
        assert(b.fillareastyle == 'hallow')
        assert(b.legend == {6: '6'})
        assert(b.ext_1 == True)
        assert(b.ext_2 == True)
        assert(b.missing == 242)
