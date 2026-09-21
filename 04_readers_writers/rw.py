"""Readers/writers access control.

Many readers may read in parallel, but a writer needs exclusive access. Plain
mutual exclusion cannot express that -- it would serialise the readers too.

The invariants maintained here:

    active_writers is 0 or 1
    if active_writers == 1 then active_readers == 0
    if waiting_writers > 0 then no new reader is let in

The last rule gives writers priority. Without it a steady stream of readers
would starve every writer; with it, a steady stream of writers starves the
readers instead. Which one you want depends on the application.

Only the access protocol lives here; what a read or a write actually does is
left to a subclass, which fills in do_read() and do_write().
"""

import threading
from abc import ABC, abstractmethod


class RW(ABC):
    """Entry/exit protocols for readers and writers; the work is a subclass's."""

    def __init__(self):
        self._active_readers = 0  # threads currently reading
        self._active_writers = 0  # always zero or one
        self._waiting_readers = 0  # threads waiting to read
        self._waiting_writers = 0  # same for writing
        self._cond = threading.Condition()

    @abstractmethod
    def do_read(self):
        """The actual read -- implemented by the subclass."""

    @abstractmethod
    def do_write(self):
        """The actual write -- implemented by the subclass."""

    def read(self):
        """Entry protocol, read, exit protocol. Arbitrarily many readers."""
        self._before_read()
        try:
            self.do_read()
        finally:
            # Without the try/finally an exception in do_read() would leave
            # active_readers too high and block every writer for good.
            self._after_read()

    def write(self):
        """Entry protocol, write, exit protocol. Exactly one writer."""
        self._before_write()
        try:
            self.do_write()
        finally:
            self._after_write()

    # --- conditions -------------------------------------------------------
    # Called with the lock held.

    def _allow_reader(self):
        return self._waiting_writers == 0 and self._active_writers == 0

    def _allow_writer(self):
        return self._active_readers == 0 and self._active_writers == 0

    # --- entry and exit protocols ----------------------------------------

    def _before_read(self):
        with self._cond:
            self._waiting_readers += 1
            while not self._allow_reader():
                self._cond.wait()
            self._waiting_readers -= 1
            self._active_readers += 1

    def _after_read(self):
        with self._cond:
            self._active_readers -= 1
            self._cond.notify_all()

    def _before_write(self):
        with self._cond:
            self._waiting_writers += 1
            while not self._allow_writer():
                self._cond.wait()
            self._waiting_writers -= 1
            self._active_writers += 1

    def _after_write(self):
        with self._cond:
            self._active_writers -= 1
            self._cond.notify_all()

    # --- for inspection in demos -----------------------------------------

    @property
    def active_readers(self):
        return self._active_readers
