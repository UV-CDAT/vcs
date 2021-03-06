import vcs
import cdms2
import os

x = vcs.init()
f = cdms2.open(os.path.join(vcs.sample_data, 'clt.nc'))
u = f("u")
v = f("v")

V = x.createvector()
V.linecolor = 242
V.scale = 5.
V.type = "arrows"
V.reference = 6.
V.list()

x.plot(u[::2], v[::2], V)

x.png("vectors")
x.interact()
