import basevcstest


class TestVCSDrawMarkerLeg(basevcstest.VCSBaseTest):
    def testDrawMarkerLegend(self):
        t = self.x.gettemplate("deftaylor")
        t.legend.x1 = .5
        t.legend.x2 = .6
        t.legend.y1 = .2
        t.legend.y2 = .65
        ids = ["Sea Level Pressure (ERA-Interim)","SW Cloud Forcing (CERES-EBAF 4.0)","LW Cloud Forcing (CERES-EBAF 4.0)","Land Precipitation (GPCP 2.2)","Ocean Precipitation (GPCP 2.2)","2-m temperature","More"]
        #ids = ["SLP(ERA-Interim)","A2","A3","B1","C1","C2","C3"]
        id_sizes = [1.8, 1.8, 1.8, 1.8, 1.8, 1.8, 1.8,]
        id_colors = ["red","orange","green","cyan","blue","purple","black"]
        symbols = ["diamond","square_fill","circle","triangle_right_fill","triangle_left_fill","triangle_up_fill","triangle_down_fill"]
        n = 7
        t.drawLinesAndMarkersLegend(self.x, linecolors=[[0,0,0,0]]*n, linetypes=['solid',]*n, linewidths=[0,]*n, markercolors=id_colors, markertypes=symbols, markersizes=id_sizes, strings=ids, scratched=None, stringscolors=id_colors, stacking='vertical', bg=False, render=True)

        fnm = "test_drawLinesAndMarkersLegend_noscale.png"
        self.checkImage(fnm)
        self.x.clear()
        t.drawLinesAndMarkersLegend(self.x, linecolors=[[0,0,0,0]]*n, linetypes=['solid',]*n, linewidths=[0,]*n, markercolors=id_colors, markertypes=symbols, markersizes=id_sizes, strings=ids, scratched=None, stringscolors=id_colors, stacking='vertical', bg=False, render=True, smallestfontsize=6)

        fnm = "test_drawLinesAndMarkersLegend_limit_size.png"
        self.checkImage(fnm)
        self.x.clear()
        t.drawLinesAndMarkersLegend(self.x, linecolors=[[0,0,0,0]]*n, linetypes=['solid',]*n, linewidths=[0,]*n, markercolors=id_colors, markertypes=symbols, markersizes=id_sizes, strings=ids, scratched=None, stringscolors=id_colors, stacking='vertical', bg=False, render=True, smallestfontsize=0)

        fnm = "test_drawLinesAndMarkersLegend_original.png"
        self.checkImage(fnm)




