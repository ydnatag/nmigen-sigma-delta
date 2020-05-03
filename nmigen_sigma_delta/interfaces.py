from nmigen import *

class Stream(Record):
    def __init__(self, width, name, last=False):
        self._last = last
        self.layout = [
            ('data', width),
            ('valid', 1),
            ('ready', 1),
        ]

        if self._last:
            self.layout += [('last', 1)]

        Record.__init__(self, self.layout, name=name)

        # For simulation
        self._sent = []
        self._received = []

    def get_signals(self):
        return [self[field[0]] for field in self.layout]


    def accepted(self):
        return self.valid & self.ready

    def connect(self, stream):
        cmd = [
            stream.data.eq(self.data),
            stream.valid.eq(self.valid),
            self.ready.eq(stream.ready)
        ]
        if self._last:
            cmd += [stream.last.eq(self.last)]
        return cmd

    def send_driver(self, data):
        def process():
            yield self.valid.eq(1)
            for d in data:
                yield self.data.eq(d)
                yield
                accepted = yield self.accepted()
                while not accepted:
                    yield
                    accepted = yield self.accepted()
                self._sent.append(d)
            yield self.valid.eq(0)
        return process

    def recv_driver(self, count):
        def process():
            yield self.ready.eq(1)
            cnt = 0
            while cnt < count:
                yield
                accepted = yield self.accepted()
                if accepted:
                    data = yield self.data
                    self._received.append(data)
                    cnt += 1
        return process
