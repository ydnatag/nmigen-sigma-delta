from .interfaces import Stream
from .pipeline import _PipeElement
from math import log2, ceil, floor, comb
from nmigen import Module, Signal, Elaboratable


class Comb(_PipeElement):
    def elaborate(self, platform):
        m = self.module
        sync = m.d[self.domain]
        delayed = Signal(self.width)

        with m.If(self.input.accepted()):
            sync += delayed.eq(self.input.data)

        self.add_handshake(self.input.data - delayed)
        return m


class Integrator(_PipeElement):
    def elaborate(self, platform):
        self.add_handshake(self.input.data + self.output.data)
        return self.module


class DownSampler(Elaboratable):
    def __init__(self, width, n, domain='sync'):
        self.n = n - 1
        self.width = width
        self.domain = domain
        self.input = Stream(width, name='input')
        self.output = Stream(width, name='output')

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        sync = m.d[self.domain]

        cnt = Signal(range(self.n))

        i_rdy = (~self.output.valid) | self.output.accepted()
        comb += self.input.ready.eq(i_rdy)

        with m.If(self.output.accepted()):
            sync += self.output.valid.eq(0)

        with m.If(self.input.accepted()):
            sync += cnt.eq(cnt + 1)
            with m.If(cnt >= self.n):
                sync += [
                    cnt.eq(0),
                    self.output.data.eq(self.input.data),
                    self.output.valid.eq(1),
                ]
        return m


"""
    CIC filter from:
    An Economical  Class of Digital  Filters for Decimation and  Interpolation,
    Eugene B. Hogenauer, 1981
    https://www.researchgate.net/publication/3176890_An_economical_class_of_digital_filters_for_decimation_and_interpolation
"""


class CIC(Elaboratable):
    def __init__(self, order, decimation, input_width, output_width, domain='sync'):
        self.i_width = input_width
        self.o_width = output_width
        self.order = order
        self.decimation = decimation
        self.domain = domain
        self.input = Stream(input_width, name='i_cic_')
        self.output = Stream(output_width, name='o_cic')
        self._R = self.decimation
        self._N = self.order
        self._M = 1
        self.b_max = ceil(self.order * log2(self._R * self._M) + self.i_width - 1)

    def get_discared_bits(self):
        R = self._R
        N = self._N
        M = self._M

        b_2n_1 = self.b_max - self.o_width + 1  # total discared bits (20)
        e_2n_1 = 2 ** b_2n_1  # (12)
        total_variance = e_2n_1**2 / 12  # (20) and (16.a)

        f_N = lambda j, k, l: (-1)**l * comb(N, l) * comb(N - j + k - R * M * l, k - R * M * l)
        f_2N = lambda j, k: (-1)**k * comb(2 * N + 1 - j, k)

        # h_j for j <= N
        h_j_N = lambda j: [sum([f_N(j, k, l)
                           for l in range(int(k / (R * M) + 1))])
                           for k in range((R * M - 1) * N + 1)]

        # h_j for j > N
        h_j_2N = lambda j: [f_2N(j, k) for k in range((R * M - 1) * N + 1)]

        # impulsive response from stage j to N+1 (9.b)
        h_j = lambda j: h_j_N(j) if j <= N else h_j_2N(j)

        # variance error gain (16.b)
        f_j = lambda j: 1 if j == 2 * N + 1 else sum([h**2 for h in h_j(j)])

        # discared bits (21)
        b_j = lambda j: -log2(f_j(j)) / 2 + log2(total_variance) / 2 + log2(6 / N) / 2

        # B_j j:[1, 2N]
        rv = [floor(b_j(j)) for j in range(1, 2 * N + 1)]
        rv = [r if r >= 0 else 0 for r in rv]
        return rv

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        # Discaring bits without losing SNR
        discared = self.get_discared_bits()
        width = [self.b_max - d for d in [0] + discared]

        # I don't know why i'm having x2 gain. Adding another bit solves that.
        width = [w + 1 for w in width]

        # adding width for the downsampler
        width = width[:self.order] + [width[self.order - 1]] + width[self.order:]

        _signals = [Signal(w) for w in width]

        integrators = [Integrator(width[i], domain=self.domain) for i in range(self.order)]
        combs = [Comb(width[i + self.order + 1], domain=self.domain) for i in range(self.order)]
        downsampler = DownSampler(width[self.order], self.decimation)

        elements = integrators + [downsampler] + combs
        for n, element in enumerate(elements):
            name = element.__class__.__name__.lower() + f'_stage_{n}'
            m.submodules[name] = element
            w = len(_signals[n + 1])
            comb += [
                element.input.data.eq(_signals[n]),
                _signals[n + 1].eq(element.output.data[-w:])
            ]

        # connecting handshake
        for i in range(1, len(elements)):
            comb += [
                elements[i].input.valid.eq(elements[i - 1].output.valid),
                elements[i - 1].output.ready.eq(elements[i].input.ready)
            ]

        comb += [
            self.input.ready.eq(elements[0].input.ready),
            elements[0].input.valid.eq(self.input.valid),
            elements[0].input.data.eq(self.input.data),
            self.output.valid.eq(elements[-1].output.valid),
            elements[-1].output.ready.eq(self.output.ready),
            self.output.data.eq(elements[-1].output.data[-self.o_width:])
        ]

        return m
