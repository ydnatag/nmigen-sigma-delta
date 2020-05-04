from nmigen import Elaboratable, Module
from .interfaces import Stream


class _PipeElement(Elaboratable):
    def __init__(self, width, domain='sync'):
        self.width = width
        self.domain = domain
        self.input = Stream(width, name='input')
        self.output = Stream(width, name='output')
        self.module = Module()

    def add_handshake(self, output):
        m = self.module
        comb = m.d.comb
        sync = m.d[self.domain]

        i_rdy = (~self.output.valid) | self.output.accepted()
        comb += self.input.ready.eq(i_rdy)

        with m.If(self.output.accepted()):
            sync += self.output.valid.eq(0)

        with m.If(self.input.accepted()):
            sync += [
                self.output.data.eq(output),
                self.output.valid.eq(1),
            ]
            try:
                sync += self.output.last.eq(self.input.last)
            except AttributeError:
                pass
