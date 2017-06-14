import basevcstest
import vcs
import time

class TestVCSSlowDown(basevcstest.VCSBaseTest):
    def __init__(self, *args, **kwargs):
        data1d = [1,2,3,4,5,4,3,2,1]
        data2d = [[1,2,3],[4,5,6]]
        data2d_b = [[3,2,1],[5,6,4]]
        data_mesh = [1,2]
        mesh = [[[0,0,1],[0,2,1]],
                [[2,1,2],[0,1,2]]]
        self.gmtypes = { "1d" : (data1d,),
                "boxfill": (data2d,),
                "isofill": (data2d,),
                "isoline": (data2d,),
                "vector": (data2d, data2d_b),
                "meshfill": (data_mesh,mesh),
                "streamline": (data2d, data2d_b),
                }
        kwargs['geometry'] = {"width": 500, "height": 250}
        super(TestVCSSlowDown, self).__init__(*args, **kwargs)
    def isSlowingDown(self,gmtype):
        n = 100
        print "Testing slow down for:",gmtype
        maxpct = 100.
        fastest = 100000.
        avg = 0.
        for i in range(n):
            print i,
            start = time.time()
            gm = vcs.creategraphicsmethod(gmtype)
            gm.datawc_x1 = 0.
            gm.datawc_x2 = 2.
            gm.datawc_y1 = 0.
            gm.datawc_y2 = 2.
            self.x.plot(gm,*self.gmtypes[gmtype])
            end = time.time()
            elapsed = end - start
            if elapsed < fastest:
                fastest = elapsed
            pct = (elapsed/fastest*100.)
            print "Time:", elapsed, "%.2i" % pct
            if i>5 and pct>maxpct: # skip the first 5 times to make sure system gets in groovy mode
                maxpct = pct
            avg += elapsed
            self.x.clear()
            self.x.removeobject(gm)
        print "\tMax percentage",maxpct
        print "\tFastest time:",fastest
        print "\tAvg time:",avg/n
        if maxpct>150.:
            return True
        return False
    def testSlowingDown(self):
        for gmtype in self.gmtypes:
            self.assertFalse(self.isSlowingDown(gmtype))

