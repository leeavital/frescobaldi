# This file is part of the qpopplerview package.
#
# Copyright (c) 2010, 2011 by Wilbert Berendsen
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
# See http://www.gnu.org/licenses/ for more information.


"""
Caching of generated images.
"""

import time
import weakref
import popplerqt4

from PyQt4.QtCore import QThread


__all__ = ['maxsize', 'setmaxsize', 'image', 'generate', 'clear']


_cache = weakref.WeakKeyDictionary()
_schedulers = weakref.WeakKeyDictionary()


# cache size
_maxsize = 104857600 # 100M
_currentsize = 0


def setmaxsize(maxsize):
    """Sets the maximum cache size in Megabytes."""
    global _maxsize
    _maxsize = maxsize * 1048576
    purge()
    

def maxsize():
    """Returns the maximum cache size in Megabytes."""
    return _maxsize / 1048576


def clear(document=None):
    """Clears the whole cache or the cache for the given Poppler.Document."""
    if document:
        try:
            del _cache[document]
        except KeyError:
            pass
    else:
        _cache.clear()
        global _currentsize
        _currentsize = 0


def image(page, exact=True):
    """Returns a rendered image for given Page if in cache.
    
    If exact is True (default), the function returns None if the exact size was
    not in the cache. If exact is False, the function may return a temporary
    rendering of the page scaled from a different size, if that was available.
    
    """
    document = page.document()
    pageKey = (page.pageNumber(), page.rotation())
    sizeKey = (page.width(), page.height())
    
    if exact:
        try:
            entry = _cache[document][pageKey][sizeKey]
        except KeyError:
            return
        else:
            entry[1] = time.time()
            return entry[0]
    try:
        sizes = _cache[document][pageKey].keys()
    except KeyError:
        return
    # find the closest size (assuming aspect ratio has not changed)
    if sizes:
        sizes.sort(key=lambda s: abs(1 - s[0] / float(page.width())))
        return _cache[document][pageKey][sizes[0]][0]


def generate(page):
    """Schedule an image to be generated for the cache."""
    # Poppler-Qt4 crashes when different pages from a Document are rendered at the same time,
    # so we schedule them to be run in sequence.
    document = page.document()
    try:
        scheduler = _schedulers[document]
    except KeyError:
        scheduler = _schedulers[document] = Scheduler()
    scheduler.schedulejob(page)


def add(image, document, pageNumber, rotation, width, height):
    """(Internal) Adds an image to the cache."""
    pageKey = (pageNumber, rotation)
    sizeKey = (width, height)
    _cache.setdefault(document, {}).setdefault(pageKey, {})[sizeKey] = [image, time.time()]
    
    # maintain cache size
    global _maxsize, _currentsize
    _currentsize += image.byteCount()
    if _currentsize > _maxsize:
        purge()


def purge():
    """Removes old images from the cache to limit the space used.
    
    (Not necessary to call, as the cache will monitor its size automatically.)
    
    """
    # make a list of the images, sorted on time, newest first
    images = iter(sorted((
        (time, document, pageKey, sizeKey, image.byteCount())
            for document, pageKeys in _cache.items()
            for pageKey, sizeKeys in pageKeys.items()
            for sizeKey, (image, time) in sizeKeys.items()),
                reverse=True))

    # sum the size of the newest images
    global _maxsize, _currentsize
    byteCount = 0
    for item in images:
        byteCount += item[4]
        if byteCount > _maxsize:
            break
    _currentsize = byteCount
    # delete the other images
    for time, document, pageKey, sizeKey, byteCount in images:
        del _cache[document][pageKey][sizeKey]


class Scheduler(object):
    """Manages running rendering jobs in sequence for a Document."""
    def __init__(self):
        self._schedule = []     # order
        self._jobs = {}         # jobs on key
        self._running = None
        
    def schedulejob(self, page):
        """Creates or retriggers an existing Job.
        
        The page's update() method will be called when the Job has completed.
        
        """
        # uniquely identify the image to be generated
        key = (page.pageNumber(), page.rotation(), page.width(), page.height())
        try:
            job = self._jobs[key]
        except KeyError:
            job = self._jobs[key] = Job(page)
            job.key = key
        else:
            self._schedule.remove(job)
            job.notify(page)
        self._schedule.append(job)
        self.checkStart()
        
    def checkStart(self):
        """Starts a job if none is running and at least one is waiting."""
        if self._schedule and not self._running:
            job = self._schedule[-1]
            document = job.document()
            if document:
                self._running = Runner(self, document, job)
            else:
                self.done(job)
            
    def done(self, job):
        """Called when the job has completed."""
        del self._jobs[job.key]
        self._schedule.remove(job)
        self._running = None
        for page in job.pages():
            page.update()
        self.checkStart()


class Job(object):
    """Simply contains data needed to create an image later."""
    def __init__(self, page):
        self._pages = []
        self.document = weakref.ref(page.document())
        self.pageNumber = page.pageNumber()
        self.rotation = page.rotation()
        self.width = page.width()
        self.height = page.height()
        self.notify(page)
        
    def notify(self, page):
        """Add a Page to the list to be notified when the job has completed."""
        pageref = weakref.ref(page)
        if pageref not in self._pages:
            self._pages.append(pageref)
        
    def pages(self):
        """Yields the pages that want to update() when this Job is done."""
        for pageref in self._pages:
            page = pageref()
            if page:
                yield page


class Runner(QThread):
    """Immediately runs a Job in a background thread."""
    def __init__(self, scheduler, document, job):
        super(Runner, self).__init__()
        self.scheduler = scheduler
        self.job = job
        self.document = document # keep reference now so that it does not die during this thread
        self.finished.connect(self.slotFinished)
        self.start()
        
    def run(self):
        """Main method of this thread, called by Qt on start()."""
        page = self.document.page(self.job.pageNumber)
        pageSize = page.pageSize()
        if self.job.rotation & 1:
            pageSize.transpose()
        xres = 72.0 * self.job.width / pageSize.width()
        yres = 72.0 * self.job.height / pageSize.height()
        self.image = page.renderToImage(xres, yres, 0, 0, self.job.width, self.job.height, self.job.rotation)
        
    def slotFinished(self):
        """Called when the thread has completed."""
        add(self.image, self.document, self.job.pageNumber, self.job.rotation, self.job.width, self.job.height)
        self.scheduler.done(self.job)


